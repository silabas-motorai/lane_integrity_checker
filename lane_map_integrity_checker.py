from qgis.core import (QgsProject, QgsGeometry, QgsFeature, QgsField,
                       QgsVectorLayer, QgsMarkerSymbol, QgsSingleSymbolRenderer,
                       QgsSpatialIndex, QgsRectangle)
from qgis.utils import iface
from PyQt5.QtCore import QVariant
from collections import defaultdict

WAY_PAIRS_MAP = {
    (2, 100): ([[100, 500]], [-1]),
    (2, 300): ([[300, 700]], [1]),
    (3, 200): ([[100, 200], [300, 200]], [-1, 1]),
    (3, 400): ([[100, 400], [400, 500]], [-1, -2]),
    (3, 800): ([[300, 800], [800, 700]], [2, 1]),
    (4, 101): ([[100, 101], [101, 202]], [2, 1]),
    (4, 202): ([[300, 202]], [-1]),
    (4, 200): ([[100, 200], [201, 200]], [-1, 1]),
    (4, 201): ([[300, 201]], [2]),
    (4, 400): ([[100, 400], [400, 401]], [-1, -2]),
    (4, 401): ([[401, 500]], [-3]),
    (4, 800): ([[300, 800], [800, 801]], [1, 2]),
    (4, 801): ([[801, 700]], [3]),
    (5, 101): ([[100, 101]], [-1]),
    (5, 200): ([[101, 200], [201, 200]], [-2, 1]),
    (5, 201): ([[300, 201]], [2]),
    (5, 400): ([[100, 400], [400, 401]], [-1, -2]),
    (5, 402): ([[401, 402], [402, 500]], [-3, -4]),
    (5, 800): ([[300, 800], [800, 801]], [1, 2]),
    (5, 802): ([[801, 802], [802, 700]], [3, 4]),
    (6, 101): ([[100, 101], [101, 102]], [-1, -2]),
    (6, 200): ([[102, 200], [201, 200]], [-3, 1]),
    (6, 201): ([[300, 201]], [2]),
    (6, 202): ([[203, 202]], [1]),
    (6, 204): ([[300, 204], [204, 203]], [3, 2]),
    (6, 1010): ([[100, 1010], [1010, 200]], [-1, -2]),
    (6, 2010): ([[2010, 200], [2020, 2010]], [1, 2]),
    (6, 2020): ([[300, 2020]], [3]),
    (6, 400): ([[100, 400], [400, 401]], [-1, -2]),
    (6, 402): ([[401, 402], [402, 403]], [-3, -4]),
    (6, 403): ([[403, 500]], [-5]),
    (6, 800): ([[300, 800], [800, 801]], [1, 2]),
    (6, 802): ([[801, 802], [802, 803]], [3, 4]),
    (6, 803): ([[803, 700]], [5]),
    (7, 101): ([[100, 101], [101, 102]], [-1, -2]),
    (7, 200): ([[102, 200], [201, 200]], [-3, 1]),
    (7, 202): ([[300, 202], [202, 201]], [2, 3]),
    (7, 400): ([[100, 400], [400, 401]], [-1, -2]),
    (7, 402): ([[401, 402], [402, 403]], [-3, -4]),
    (7, 404): ([[403, 404], [404, 500]], [-5, -6]),
    (7, 800): ([[300, 800], [800, 801]], [1, 2]),
    (7, 802): ([[801, 802], [802, 803]], [3, 4]),
    (7, 804): ([[803, 804], [804, 700]], [5, 6]),
}

def get_border_way_ids_for_centerline(roads_with_ref, cl_way_id):
    for (rwr, ref_wid), (pairs, _) in WAY_PAIRS_MAP.items():
        if rwr != roads_with_ref:
            continue
        for right_w, left_w in pairs:
            if min(right_w, left_w) * 100 + 12 == cl_way_id:
                return (right_w, left_w)
    return None

def check_lane_integrity(snap_tol=1e-15, graph_tol=1e-5):
    layer = iface.activeLayer()
    if not layer: return []

    features = list(layer.getFeatures())
    if not features: return []

    all_lines = []
    stop_wait_lines = []
    for f in features:
        l_type = str(f['lane_type']).lower() if f['lane_type'] else ""
        a_type = str(f['area_type']).lower() if f['area_type'] else ""
        l_sub  = str(f['line_sub']).lower()  if f['line_sub']  else ""
        if l_sub in ['de294', 'de341']:
            stop_wait_lines.append(f)
        elif l_type == 'centerline' or (l_type in ['road', 'cycle', 'road_cycle'] and a_type in ['', 'none', 'null']):
            all_lines.append(f)

    feat_by_id = {f.id(): f for f in all_lines}

    def get_group_type(feat):
        t = str(feat['lane_type']).lower()
        if 'cycle' in t: return 'cycle'
        return 'road_group'

    def get_flow_info(feat):
        geom = feat.geometry()
        if not geom: return None, None, None
        try:
            line = geom.asPolyline() if not geom.isMultipart() else geom.asMultiPolyline()[0]
        except:
            return None, None, None
        if not line: return None, None, None
        
        try: way_id = int(str(feat["way_id"])[:3])
        except: way_id = 0
            
        greater_x = {100, 101, 102, 400, 401, 402, 403, 500}
        is_eastbound = way_id in greater_x
        if (is_eastbound and line[0].x() > line[-1].x()) or \
           (not is_eastbound and line[0].x() < line[-1].x()):
            return line[-1], line[0], is_eastbound
        return line[0], line[-1], is_eastbound

    spatial_index = QgsSpatialIndex()
    for f in all_lines:
        spatial_index.insertFeature(f)

    def get_nearby_ids(point, radius):
        search_rect = QgsRectangle(
            point.x() - radius, point.y() - radius,
            point.x() + radius, point.y() + radius
        )
        return spatial_index.intersects(search_rect)

    flow_cache  = {f.id(): get_flow_info(f)  for f in all_lines}
    group_cache = {f.id(): get_group_type(f) for f in all_lines}

    def is_cycle_endpoint_on_road(point, feat_id, tol=0.5):
        pt_geom = QgsGeometry.fromPointXY(point)
        for fid in get_nearby_ids(point, tol):
            if fid == feat_id or fid not in feat_by_id: continue
            if group_cache[fid] != 'road_group': continue
            if pt_geom.distance(feat_by_id[fid].geometry()) < tol:
                return True
        return False

    # --- Connection graph (Keep robust is_confirmed logic to prevent 1520 false positive) ---
    successors   = defaultdict(set)
    predecessors = defaultdict(set)
    raw_succ = defaultdict(lambda: defaultdict(list))
    raw_pred = defaultdict(lambda: defaultdict(list))
    group_counts = defaultdict(int)

    for f in all_lines:
        rid = f['road_id']
        f_entry, f_exit, f_east = flow_cache[f.id()]
        if not f_entry: continue
        
        f_group = group_cache[f.id()]
        key = (rid, f_east, f_group)
        group_counts[key] += 1

        for oid in get_nearby_ids(f_exit, graph_tol * 10):
            if oid == f.id() or oid not in feat_by_id: continue
            other = feat_by_id[oid]
            o_entry, o_exit, o_east = flow_cache[oid]
            if not o_entry: continue
            if f_east != o_east or f_group != group_cache[oid]: continue
            if f_exit.distance(o_entry) < graph_tol:
                raw_succ[key][other['road_id']].append(f.id())

        for oid in get_nearby_ids(f_entry, graph_tol * 10):
            if oid == f.id() or oid not in feat_by_id: continue
            other = feat_by_id[oid]
            o_entry, o_exit, o_east = flow_cache[oid]
            if not o_entry: continue
            if f_east != o_east or f_group != group_cache[oid]: continue
            if f_entry.distance(o_exit) < graph_tol:
                raw_pred[key][other['road_id']].append(f.id())

    for key, targets in raw_succ.items():
        for target_rid, f_ids in targets.items():
            is_confirmed = False
            if len(f_ids) > 1 or group_counts[key] == 1:
                is_confirmed = True
            else:
                l_type = str(feat_by_id[f_ids[0]]['lane_type']).lower()
                if l_type == 'centerline' or key[2] == 'cycle':
                    is_confirmed = True
            if is_confirmed: successors[key].add(target_rid)

    for key, targets in raw_pred.items():
        for target_rid, f_ids in targets.items():
            is_confirmed = False
            if len(f_ids) > 1 or group_counts[key] == 1:
                is_confirmed = True
            else:
                l_type = str(feat_by_id[f_ids[0]]['lane_type']).lower()
                if l_type == 'centerline' or key[2] == 'cycle':
                    is_confirmed = True
            if is_confirmed: predecessors[key].add(target_rid)

    issues = []

    # --- 1. Snapping checks ---
    for f in all_lines:
        f_entry, f_exit, f_east = flow_cache[f.id()]
        if not f_entry: continue

        rid       = f['road_id']
        wid       = f['way_id']
        my_l_type = str(f['lane_type']).lower()
        l_type    = my_l_type.upper()
        f_group   = group_cache[f.id()]
        is_cycle  = (f_group == 'cycle')
        key       = (rid, f_east, f_group)

        # Entry
        start_snapped = False
        for oid in get_nearby_ids(f_entry, snap_tol + graph_tol):
            if oid == f.id() or oid not in feat_by_id: continue
            other = feat_by_id[oid]
            o_l_type = str(other['lane_type']).lower()
            
            if (my_l_type == 'road' and o_l_type == 'cycle') or \
               (my_l_type == 'cycle' and o_l_type == 'road'):
                continue
            
            o_entry, o_exit, _ = flow_cache[oid]
            if (o_entry and f_entry.distance(o_entry) < snap_tol) or \
               (o_exit  and f_entry.distance(o_exit) < snap_tol):
                start_snapped = True; break

        if not start_snapped:
            if is_cycle and is_cycle_endpoint_on_road(f_entry, f.id()):
                pass
            else:
                is_prox_error = False
                for oid in get_nearby_ids(f_entry, 0.0001):
                    if oid == f.id() or oid not in feat_by_id: continue
                    other = feat_by_id[oid]
                    if other['road_id'] == rid and other['lane_type'] == f['lane_type']:
                        if QgsGeometry.fromPointXY(f_entry).distance(other.geometry()) < 0.00001:
                            is_prox_error = True; break
                if is_prox_error:
                    issues.append({"way_id": wid, "road_id": rid, "point": f_entry,
                                   "type": f"{l_type}_GAP"})
                elif len(predecessors[key]) > 0:
                    has_nearby = False
                    for oid in get_nearby_ids(f_entry, graph_tol * 200):
                        if oid == f.id() or oid not in feat_by_id: continue
                        if group_cache[oid] != f_group: continue
                        _, o_exit_pt, o_east = flow_cache[oid]
                        if o_east != f_east: continue
                        if o_exit_pt and f_entry.distance(o_exit_pt) < graph_tol * 100:
                            has_nearby = True; break
                    if has_nearby:
                        issues.append({"way_id": wid, "road_id": rid, "point": f_entry,
                                       "type": f"{l_type}_GAP"})

        # Exit
        end_snapped = False
        for oid in get_nearby_ids(f_exit, snap_tol + graph_tol):
            if oid == f.id() or oid not in feat_by_id: continue
            other = feat_by_id[oid]
            o_l_type = str(other['lane_type']).lower()
            
            if (my_l_type == 'road' and o_l_type == 'cycle') or \
               (my_l_type == 'cycle' and o_l_type == 'road'):
                continue
            
            o_entry, o_exit, _ = flow_cache[oid]
            if (o_entry and f_exit.distance(o_entry) < snap_tol) or \
               (o_exit  and f_exit.distance(o_exit) < snap_tol):
                end_snapped = True; break

        if not end_snapped:
            if is_cycle and is_cycle_endpoint_on_road(f_exit, f.id()):
                pass
            else:
                is_prox_error = False
                for oid in get_nearby_ids(f_exit, 0.0001):
                    if oid == f.id() or oid not in feat_by_id: continue
                    other = feat_by_id[oid]
                    if other['road_id'] == rid and other['lane_type'] == f['lane_type']:
                        if QgsGeometry.fromPointXY(f_exit).distance(other.geometry()) < 0.00001:
                            is_prox_error = True; break
                if is_prox_error:
                    issues.append({"way_id": wid, "road_id": rid, "point": f_exit,
                                   "type": f"{l_type}_GAP"})
                elif len(successors[key]) > 0:
                    has_nearby = False
                    for oid in get_nearby_ids(f_exit, graph_tol * 200):
                        if oid == f.id() or oid not in feat_by_id: continue
                        if group_cache[oid] != f_group: continue
                        o_entry_pt, _, o_east = flow_cache[oid]
                        if o_east != f_east: continue
                        if o_entry_pt and f_exit.distance(o_entry_pt) < graph_tol * 100:
                            has_nearby = True; break
                    if has_nearby:
                        issues.append({"way_id": wid, "road_id": rid, "point": f_exit,
                                       "type": f"{l_type}_GAP"})


    # --- 2. Border routing consistency checks ---
    roads_with_ref_map = defaultdict(int)
    for f in all_lines:
        if str(f['lane_type']).lower() in ['road', 'cycle', 'road_cycle']:
            roads_with_ref_map[str(f['road_id'])] += 1

    borders_by_rid_wid = defaultdict(list)
    for f in all_lines:
        if str(f['lane_type']).lower() in ['road', 'cycle', 'road_cycle']:
            try: borders_by_rid_wid[(str(f['road_id']), int(f['way_id']))].append(f)
            except: pass

    centerlines = [f for f in all_lines if str(f['lane_type']).lower() == 'centerline']
    border_constraints = defaultdict(list)

    for cl in centerlines:
        cl_entry, cl_exit, cl_east = flow_cache[cl.id()]
        if not cl_entry: continue

        try:
            cl_rid = str(cl['road_id'])
            cl_wid = int(cl['way_id'])
        except: continue

        succ_rids = set()
        pred_rids = set()

        for oid in get_nearby_ids(cl_exit, graph_tol * 10):
            if oid == cl.id() or oid not in feat_by_id: continue
            other = feat_by_id[oid]
            if str(other['lane_type']).lower() != 'centerline': continue
            o_entry, _, o_east = flow_cache[oid]
            if not o_entry or o_east != cl_east: continue
            if cl_exit.distance(o_entry) < graph_tol:
                succ_rids.add(str(other['road_id']))

        for oid in get_nearby_ids(cl_entry, graph_tol * 10):
            if oid == cl.id() or oid not in feat_by_id: continue
            other = feat_by_id[oid]
            if str(other['lane_type']).lower() != 'centerline': continue
            _, o_exit, o_east = flow_cache[oid]
            if not o_exit or o_east != cl_east: continue
            if cl_entry.distance(o_exit) < graph_tol:
                pred_rids.add(str(other['road_id']))

        if not succ_rids and not pred_rids: continue

        rwr = roads_with_ref_map.get(cl_rid, 0)
        if rwr == 0: continue

        border_pair = get_border_way_ids_for_centerline(rwr, cl_wid)
        if not border_pair: continue
        
        right_wid, left_wid = border_pair
        pair_wids = {right_wid, left_wid}

        for border_wid in (right_wid, left_wid):
            border_constraints[(cl_rid, border_wid)].append((succ_rids, pred_rids, pair_wids, cl_east))

    for (cl_rid, border_wid), constraints in border_constraints.items():
        for border_f in borders_by_rid_wid.get((cl_rid, border_wid), []):
            b_entry, b_exit, b_east = flow_cache[border_f.id()]
            if not b_entry: continue
            b_wid = border_f['way_id']

            all_succ      = set()
            all_pred      = set()
            all_pair_wids = set()
            for succ_rids, pred_rids, pair_wids, cl_east_c in constraints:
                if cl_east_c != b_east: continue
                all_succ      |= succ_rids
                all_pred      |= pred_rids
                all_pair_wids |= pair_wids

            # Exit
            if all_succ:
                exit_road_rids = set()
                for oid in get_nearby_ids(b_exit, graph_tol * 10):
                    if oid == border_f.id() or oid not in feat_by_id: continue
                    other = feat_by_id[oid]
                    o_entry, _, o_east = flow_cache[oid]
                    if not o_entry or o_east != b_east: continue
                    if b_exit.distance(o_entry) >= graph_tol: continue
                    if str(other['lane_type']).lower() == 'cycle': continue
                    
                    o_rid = str(other['road_id'])
                    o_wid = int(other['way_id'])
                    if o_wid in all_pair_wids and o_rid not in all_succ: continue
                    exit_road_rids.add(o_rid)

                if exit_road_rids and not exit_road_rids.intersection(all_succ):
                    issues.append({
                        "way_id": b_wid, "road_id": cl_rid, "point": b_exit,
                        "type": f"BORDER_MISMATCH → road_id {sorted(list(exit_road_rids))} (expected: road_id {sorted(list(all_succ))})"
                    })

            # Entry
            if all_pred:
                entry_road_rids = set()
                for oid in get_nearby_ids(b_entry, graph_tol * 10):
                    if oid == border_f.id() or oid not in feat_by_id: continue
                    other = feat_by_id[oid]
                    _, o_exit_pt, o_east = flow_cache[oid]
                    if not o_exit_pt or o_east != b_east: continue
                    if b_entry.distance(o_exit_pt) >= graph_tol: continue
                    if str(other['lane_type']).lower() == 'cycle': continue
                    
                    o_rid = str(other['road_id'])
                    o_wid = int(other['way_id'])
                    if o_wid in all_pair_wids and o_rid not in all_pred: continue
                    entry_road_rids.add(o_rid)

                if entry_road_rids and not entry_road_rids.intersection(all_pred):
                    issues.append({
                        "way_id": b_wid, "road_id": cl_rid, "point": b_entry,
                        "type": f"BORDER_MISMATCH → road_id {sorted(list(entry_road_rids))} (expected: road_id {sorted(list(all_pred))})"
                    })

# --- 3. Stop/Wait line hanging checks ---
    if stop_wait_lines:
        lane_index, lane_by_id = QgsSpatialIndex(), {}
        for bf in all_lines:
            lane_index.insertFeature(bf)
            lane_by_id[bf.id()] = bf

        endpoint_r = 0.00005  # search radius to find nearby lanes

        for f in stop_wait_lines:
            sl_geom = f.geometry()
            if not sl_geom: continue
            try:
                sl_line = sl_geom.asPolyline() if not sl_geom.isMultipart() else sl_geom.asMultiPolyline()[0]
            except:
                continue
            if not sl_line: continue
            wid = f['way_id']
            rid = f['road_id']

            bbox = sl_geom.boundingBox()
            bbox.grow(endpoint_r * 3)
            nearby_ids = lane_index.intersects(bbox)

            # 1. Crossing check: every lane that crosses stop line
            #    must have its start or end node exactly at the intersection
            for lid in nearby_ids:
                if lid not in lane_by_id: continue
                lane_f    = lane_by_id[lid]
                lane_geom = lane_f.geometry()
                if not lane_geom: continue
                if not sl_geom.crosses(lane_geom) and not sl_geom.intersects(lane_geom):
                    continue
                intersection = sl_geom.intersection(lane_geom)
                if not intersection or intersection.isEmpty(): continue
                wkb = intersection.wkbType()
                if wkb in (1, 0x80000001):
                    int_pts = [intersection.asPoint()]
                elif wkb in (4, 0x80000004):
                    int_pts = intersection.asMultiPoint()
                else:
                    continue
                try:
                    l_line = lane_f.geometry().asPolyline() if not lane_f.geometry().isMultipart() else lane_f.geometry().asMultiPolyline()[0]
                except:
                    continue
                if not l_line: continue
                endpoints = [l_line[0], l_line[-1]]
                for int_pt in int_pts:
                    int_geom = QgsGeometry.fromPointXY(int_pt)
                    if not any(int_geom.distance(QgsGeometry.fromPointXY(ep)) == 0
                               for ep in endpoints):
                        issues.append({"way_id": lane_f['way_id'],
                                       "road_id": lane_f['road_id'],
                                       "point": int_pt, "type": "STOP_LINE_GAP"})

            # 2. Endpoint hanging check: stop line endpoints must have
            #    distance == 0 to a lane line
            for pt in (sl_line[0], sl_line[-1]):
                pt_geom = QgsGeometry.fromPointXY(pt)
                r = QgsRectangle(pt.x()-endpoint_r, pt.y()-endpoint_r,
                                 pt.x()+endpoint_r, pt.y()+endpoint_r)
                snapped = close_miss = False
                for bid in lane_index.intersects(r):
                    if bid not in lane_by_id: continue
                    d = pt_geom.distance(lane_by_id[bid].geometry())
                    if d == 0:           snapped = True; break
                    elif d < endpoint_r: close_miss = True
                if not snapped and close_miss:
                    issues.append({"way_id": wid, "road_id": rid,
                                   "point": pt, "type": "STOP_LINE_GAP"})


# --- Layer management and rendering ---
existing = QgsProject.instance().mapLayersByName("Integrity_Issues")
if existing: QgsProject.instance().removeMapLayers([l.id() for l in existing])

detected = check_lane_integrity()

if detected:
    temp_layer = QgsVectorLayer(
        f"Point?crs={iface.activeLayer().crs().authid()}",
        "Integrity_Issues", "memory"
    )
    provider = temp_layer.dataProvider()
    provider.addAttributes([
        QgsField("road_id",    QVariant.String),
        QgsField("way_id",     QVariant.String),
        QgsField("issue_type", QVariant.String)
    ])
    temp_layer.updateFields()
    
    seen_issues = set()
    for issue in detected:
        issue_sig = (round(issue['point'].x(), 5), round(issue['point'].y(), 5), issue['type'])
        if issue_sig not in seen_issues:
            seen_issues.add(issue_sig)
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromPointXY(issue['point']))
            feat.setAttributes([str(issue['road_id']), str(issue['way_id']), issue['type']])
            provider.addFeature(feat)
            
    temp_layer.updateExtents()
    symbol = QgsMarkerSymbol.createSimple({
        'name': 'circle', 'color': 'transparent',
        'outline_color': 'blue', 'outline_width': '0.6', 'size': '4.5'
    })
    temp_layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    QgsProject.instance().addMapLayer(temp_layer)
    iface.messageBar().pushMessage("Warning", f"{temp_layer.featureCount()} Lane Topology Issues Found.", level=1)
else:
    iface.messageBar().pushMessage("Success", "All Lane Groups are Perfectly Snapped & Routed!", level=0)
