# QGIS Lane Topology & Integrity Checker

This PyQGIS script is an automated validation tool designed to verify the geometric integrity and topological routing of road networks (lanes, centerlines, cycle paths) directly within QGIS. It is highly useful for QA/QC processes in High-Definition (HD) Mapping, autonomous driving datasets, and traffic simulation modeling.

The tool analyzes LineString vector layers to detect microscopic snapping gaps, orphan lanes, and logical routing mismatches where lane borders deviate from their guiding centerlines.

## 🚀 Features

* **Gap Detection (Snapping Checks):** Identifies floating lane endpoints that fail to connect to adjacent lanes (Strict Gaps) or endpoints that miss their logical group continuation (Missed Gaps).
* **Smart Topology Filtering:** Prevents false connections by forbidding blind snaps between pure `road` and pure `cycle` lanes, while safely handling shared `road_cycle` transitions. Cycle lanes are granted specific start/end tolerances.
* **Border Routing Verification:** Evaluates the path of right/left border lanes against their designated `centerline`. If a border lane connects to a different road than its centerline, it flags a `BORDER_ROUTING_MISMATCH`.
* **False Positive Elimination:** Smartly differentiates between actual routing errors and innocent geometric friction (e.g., parallel lanes with the same `way_id`), and respects intentional dead-ends or map boundaries to avoid spamming errors.
* **Automated Visualization:** Instantly generates a temporary in-memory point layer (`Integrity_Issues`) highlighting the exact coordinates of the detected issues.

## 📋 Prerequisites & Data Schema

To run this script, you must have a **LineString Vector Layer** actively selected in QGIS. The attribute table of this layer must contain the following fields:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `lane_type` | String | Type of the lane. Expected values: `centerline`, `road`, `cycle`, `road_cycle`. |
| `area_type` | String | Used to filter out polygons. Lines should have this as empty, `none`, or `null`. |
| `way_id` | Int/String | Unique identifier determining lane matching. The script uses the first 3 digits to infer East/West flow direction. |
| `road_id` | String | Grouping identifier that ties together all lanes belonging to the same road segment. |

## ⚙️ How to Use

1. Open your project in QGIS.
2. Click on your target lane network layer in the **Layers Panel** to make it the **Active Layer**.
3. Open the QGIS Python Console by navigating to `Plugins` > `Python Console` (or `Ctrl+Alt+P`).
4. Click the **Show Editor** icon (the notepad icon) in the console toolbar.
5. Paste the contents of `lane_integrity_checker.py` into the editor.
6. Click the **Run script** (Play) button.

## 🔍 Understanding the Outputs

Upon execution, the script will push a success (green) or warning (yellow) message to the QGIS Message Bar. If issues are found, a new layer named `Integrity_Issues` will appear. Use the **Identify Features** tool on the generated points to read the `issue_type`:

* **`[TYPE]_GAP (Strict Entry/Exit)`:** The lane endpoint is physically floating in the air and touches absolutely nothing.
* **`[TYPE]_GAP (Missed Entry/Exit)`:** The lane endpoint touches another geometry, but failed to connect to the logical continuation path that the rest of its road group took.
* **`BORDER_ROUTING_MISMATCH`:** The centerline successfully routed to Road A, but this specific border lane mistakenly routed to Road B.

## 🛠 Configuration (For Developers)

You can tweak the constants at the top of the script to match your specific dataset rules:

* **`WAY_PAIRS_MAP` Dictionary:** This maps a centerline to its exact expected right and left border `way_id`s. You must update this map if you introduce new junction types or change your ID logic.
* **Tolerances:** In the `check_lane_integrity` function definition:
  * `snap_tol=1e-15`: The maximum allowable distance between two vertices to be considered a perfect snap.
  * `graph_tol=1e-5`: The search radius used to logically group neighboring lanes and build the connection graph.
