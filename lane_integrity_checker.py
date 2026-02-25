import json
import matplotlib.pyplot as plt
from shapely.geometry import shape, Point

def load_map_data(file_path):
    """Loads geojson features from a file path."""
    with open(file_path, 'r') as f:
        return json.load(f)['features']

def check_lane_integrity(features, snap_tol=1e-7, strict_radius=0.00001): # ~1 meter
    """
    Checks for physical gaps (magenta/red) and logical road ID mismatches (yellow).
    """
    centerlines = [f for f in features if str(f['properties'].get('lane_type')).lower() == 'centerline']
    border_types = ['road', 'cycle', 'road_cycle']
    
    borders = []
    for f in features:
        l_type = str(f['properties'].get('lane_type')).lower()
        a_type = f['properties'].get('area_type')
        if l_type in border_types:
            if a_type is None or str(a_type).lower() in ['null', 'none', '']:
                borders.append(f)
    
    issues = []

    def check_snapping(elements, label, color):
        for i, feat in enumerate(elements):
            geom = shape(feat['geometry'])
            way_id = feat['properties'].get('way_id')
            road_id = feat['properties'].get('road_id')
            l_type = str(feat['properties'].get('lane_type')).lower()
            coords = list(geom.coords)
            
            for idx in [0, -1]:
                node = Point(coords[idx])
                
                # 1. Physical Snapping check
                snapped = False
                for j, other in enumerate(elements):
                    if i == j: continue
                    other_geom = shape(other['geometry'])
                    if node.distance(Point(other_geom.coords[0])) < snap_tol or \
                       node.distance(Point(other_geom.coords[-1])) < snap_tol:
                        snapped = True
                        break
                
                # 2. Continuity check
                if not snapped:
                    expected_connection = False
                    for ref in elements:
                        if ref['properties'].get('way_id') == way_id: continue
                        ref_type = str(ref['properties'].get('lane_type')).lower()
                        
                        is_type_match = False
                        if l_type == 'centerline' and ref_type == 'centerline':
                            is_type_match = True
                        elif 'cycle' in l_type and 'cycle' in ref_type:
                            is_type_match = True
                        elif l_type == 'road' and ref_type == 'road':
                            is_type_match = True
                            
                        if is_type_match and node.distance(shape(ref['geometry'])) < strict_radius:
                            expected_connection = True
                            break
                            
                    if expected_connection:
                        issues.append({
                            "way_id": way_id, "road_id": road_id,
                            "coord": (node.x, node.y),
                            "type": f"{label} ({l_type})", "color": color
                        })

    check_snapping(centerlines, "CENTERLINE_GAP", "magenta")
    check_snapping(borders, "BORDER_GAP", "red")
    return issues

def visualize(features, issues):
    """Draws the map and markers for issues."""
    fig, ax = plt.subplots(figsize=(14, 12), dpi=90, constrained_layout=True)
    
    for f in features:
        geom = shape(f['geometry'])
        x, y = geom.xy
        l_type = str(f['properties'].get('lane_type')).lower()
        
        if l_type == 'centerline':
            color, alpha, lw = 'blue', 0.8, 2.0
        elif 'cycle' in l_type:
            color, alpha, lw = 'orange', 0.7, 1.5
        else:
            color, alpha, lw = 'green', 0.6, 1.2
        ax.plot(x, y, color=color, alpha=alpha, linewidth=lw)

    for issue in issues:
        ax.scatter(issue['coord'][0], issue['coord'][1], color=issue['color'], 
                   s=250, edgecolors='black', linewidth=2, zorder=25)
        ax.text(issue['coord'][0], issue['coord'][1] + 0.000008,
                f"{issue['type']}\nroad_id:{issue['road_id']}\nway_id:{issue['way_id']}",
                color='black', fontsize=8, weight='bold', ha='center', zorder=30,
                bbox=dict(facecolor='white', alpha=0.9, edgecolor=issue['color'], boxstyle='round,pad=0.3'))

    ax.set_aspect('equal')
    plt.title("Lane Integrity Check", fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.4)
    plt.xlabel("Longitude", fontsize=10)
    plt.ylabel("Latitude", fontsize=10)
    plt.show()

if __name__ == "__main__":
    path = "/home/user1/Downloads/LUP1_HD_lane_map_4326_ETRS89_20260220_2105.geojson"
    geojson_features = load_map_data(path)
    detected_issues = check_lane_integrity(geojson_features)
    print(f"Number of issues detected: {len(detected_issues)}")
    visualize(geojson_features, detected_issues)