from qgis.core import QgsProject, QgsGeometry, QgsFeature, QgsField, QgsVectorLayer
from qgis.utils import iface
from PyQt5.QtCore import QVariant

def check_active_layer_integrity(snap_tol=1e-15, strict_radius=0.00001):
    # Get the active layer selected in QGIS
    layer = iface.activeLayer()
    if not layer:
        print("Please select a layer first!")
        return

    features = list(layer.getFeatures())
    centerlines = []
    borders = []
    
    # Categorize features
    for f in features:
        l_type = str(f['lane_type']).lower() if f['lane_type'] else ""
        a_type = str(f['area_type']).lower() if f['area_type'] else ""
        
        if l_type == 'centerline':
            centerlines.append(f)
        elif l_type in ['road', 'cycle', 'road_cycle'] and a_type in ['', 'none', 'null']:
            borders.append(f)

    issues = []

    def check_snapping(elements, label):
        for i, feat in enumerate(elements):
            geom = feat.geometry()
            if not geom or not geom.asPolyline(): continue
            
            # Start and End points of the line
            nodes = [geom.asPolyline()[0], geom.asPolyline()[-1]]
            way_id = feat['way_id']
            road_id = feat['road_id']
            l_type = str(feat['lane_type']).lower()

            for node_pt in nodes:
                node_geom = QgsGeometry.fromPointXY(node_pt)
                snapped = False
                
                # Step 1: Check if physically touching another line (1cm)
                for j, other in enumerate(elements):
                    if i == j: continue
                    other_pts = other.geometry().asPolyline()
                    if not other_pts: continue
                    if node_pt.compare(other_pts[0], snap_tol) or \
                       node_pt.compare(other_pts[-1], snap_tol):
                        snapped = True
                        break
                
                # Step 2: If not touching, check if it's "too close" to a different road
                if not snapped:
                    is_problematic_gap = False
                    for ref in elements:
                        if ref['way_id'] == way_id: continue
                        
                        ref_type = str(ref['lane_type']).lower()
                        ref_road_id = ref['road_id']
                        
                        # Type matching logic
                        is_type_match = False
                        if l_type == 'centerline' and ref_type == 'centerline':
                            is_type_match = True
                        elif 'cycle' in l_type and 'cycle' in ref_type:
                            is_type_match = True
                        elif l_type == 'road' and ref_type == 'road':
                            is_type_match = True
                        
                        # If close (<1m) and has different road_id, then it is an issue
                        if is_type_match and node_geom.distance(ref.geometry()) < strict_radius:
                            if road_id != ref_road_id:
                                is_problematic_gap = True
                                break
                    
                    if is_problematic_gap:
                        issues.append({
                            "way_id": way_id, "road_id": road_id,
                            "point": node_pt, "type": f"{label} ({l_type})"
                        })

    check_snapping(centerlines, "CENTERLINE_GAP")
    check_snapping(borders, "BORDER_GAP")
    return issues

# --- Execute and Show Results in QGIS ---
existing_layers = QgsProject.instance().mapLayersByName("Integrity_Issues")
for old_layer in existing_layers:
    QgsProject.instance().removeMapLayer(old_layer.id())
    
detected_issues = check_active_layer_integrity()

if detected_issues:
    # Create a temporary result layer
    crs = iface.activeLayer().crs().authid()
    temp_layer = QgsVectorLayer(f"Point?crs={crs}", "Integrity_Issues", "memory")
    provider = temp_layer.dataProvider()
    provider.addAttributes([QgsField("way_id", QVariant.String), 
                            QgsField("road_id", QVariant.String),
                            QgsField("issue_type", QVariant.String)])
    temp_layer.updateFields()

    for issue in detected_issues:
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromPointXY(issue['point']))
        f.setAttributes([issue['way_id'], issue['road_id'], issue['type']])
        provider.addFeature(f)

    QgsProject.instance().addMapLayer(temp_layer)
    iface.messageBar().pushMessage("Warning", f"{len(detected_issues)} issues detected. Review Integrity_Issues layer.", level=1)
else:
    iface.messageBar().pushMessage("Success", "No issues found!", level=0)