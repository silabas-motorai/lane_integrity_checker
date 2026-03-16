# QGIS Lane Topology & Integrity Checker

This PyQGIS script is an automated validation tool designed to verify the geometric integrity and topological routing of GeoJSON lane maps directly within QGIS.

The tool analyzes LineString vector layers to detect snapping gaps, misaligned stop/wait lines, and logical routing mismatches where lane borders deviate from their guiding centerlines.

## 🚀 Features

* **Gap Detection (Snapping Checks):** Identifies floating lane endpoints that fail to connect to adjacent lanes, or endpoints that miss their logical group continuation.
* **Stop / Wait Line Validation:** Checks that every lane line (border, centerline, divider) crossing a regulatory stop or wait line (de294 / de341) has its start or end node exactly at the intersection point. Also verifies that the endpoints of the stop/wait line itself are precisely snapped to a lane geometry. Flags any crossing without a node at the intersection, and any hanging endpoint.
* **Topology Filtering:** Prevents false connections by forbidding blind snaps between `road` and pure `cycle` lanes, while safely handling shared `road_cycle` transitions.
* **Border Routing Verification:** Evaluates the path of right/left border lanes against their designated centerline. If a border lane connects to a different road than its centerline, it flags a `BORDER_MISMATCH`.
* **False Positive Elimination:** Differentiates between actual routing errors and innocent geometric friction (e.g., parallel snapped lane linestrings), and respects intentional dead-ends or map boundaries to avoid spamming errors.
* **Automated Visualization:** Generates a temporary in-memory point layer (`Integrity_Issues`) highlighting the exact coordinates of each detected issue.

## ⚙️ How to Use

1. Open your project in QGIS.
2. Click on your target lane map layer in the **Layers Panel** to make it the **Active Layer**.
3. Open the QGIS Python Console by navigating to `Plugins` > `Python Console` (or `Ctrl+Alt+P`).
4. Click the **Show Editor** icon (the notepad icon) in the console toolbar.
5. Open the `lane_integrity_checker.py` script in the editor.
6. Click the **Run script** button.

## 🔍 Understanding the Outputs

Upon execution, the script will push a success (green) or warning (yellow) message to the QGIS Message Bar. If issues are found, a new layer named `Integrity_Issues` will appear. Use the **Identify Features** tool on the generated points to read the `issue_type`:

* **`[TYPE]_GAP`:** The lane endpoint is unsnapped — either a near-miss vertex that just misses a neighbor, or a missing connection implied by the surrounding road group topology. `[TYPE]` reflects the lane type: `road`, `cycle`, `road_cycle`, or `centerline`.
* **`STOP_LINE_GAP`:** A stop or wait line endpoint is within snap range of a border geometry but not exactly coincident.
* **`BORDER_MISMATCH → road_id [X] (expected: road_id [Y])`:** The centerline successfully routed to road Y, but this specific border lane mistakenly connected to road X instead.
