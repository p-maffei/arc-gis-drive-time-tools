# ArcGIS Pro Drive Time Tools

Python script tools for ArcGIS Pro that keep a drive time map layout in sync with the drive time polygon it shows, batch-export a set of drive time maps to PDF, and copy drive time ring attributes into an Excel template.

| Tool | Script | What it does |
|---|---|---|
| Update Drive Time Layout | `update_drive_time_layout.py` | Updates the layout title, legend label and legend symbol color to match the ring currently shown in the map |
| Export Drive Time Maps | `export_drive_time_maps.py` | Exports a set of drive time maps to PDF, centered on a point, with the layout updated for each ring |
| Transpose to Excel Template | `transpose_to_template.py` | Copies drive time ring attributes into an Excel template, one column per ring, and sets the page header |

## Requirements

- ArcGIS Pro 3.x
- A drive time polygon layer with a text field `RING_DEFN` holding the ring size in minutes (for example `5`, `6.5`, `7.5`)
- A layout containing:
  - a text element named **`Dynamic Drive Time`** (the title)
  - a text element named **`Drive Time Ring Text`** (the legend label)
  - a polygon graphic element named **`Drive Time Ring Symbol`** (the legend swatch)

You can rename an element in the layout's **Contents** pane or in its **Element** properties. All names can be changed in the **Configuration** section at the top of each script.

## Ring colors

Both tools recolor the legend swatch's outline based on the ring size:

| Ring (minutes) | Color | Hex |
|---|---|---|
| 2 – 6.5 | Blue | `#004DA8` |
| 7 – 9 | Purple | `#73004C` |
| 9.5 – 14 | Red | `#FF0000` |
| 14.5 – 20 | Green | `#38A800` |
| Anything else | Blue (default) | `#004DA8` |

Ranges assume rings come in 0.5-minute steps. Edit `RING_COLOR_RANGES` in each script to change them.

## Adding a tool to ArcGIS Pro

1. Download the script.
2. In the **Catalog** pane, right-click a toolbox and choose **New > Script**.
3. On the **General** tab, give it a name.
4. On the **Parameters** tab, add the parameters listed for that tool below, in the same order.
5. On the **Execution** tab, point the script file to the downloaded `.py` file.
6. Click **OK**.

---

## Update Drive Time Layout

Filter a drive time layer down to one ring, run the tool, and the layout updates to match.

| Layout element | Example result |
|---|---|
| Title text | `7.5 Minute Modified Drive Time` |
| Legend ring label | `7.5 min drive time` |
| Legend ring symbol outline | Recolored to that ring's color |

This tool looks for a layout named **`Layout`** (change `LAYOUT_NAME` to use another).

**Parameters**

| Label | Data Type | Type | Direction |
|---|---|---|---|
| Drive Time Layer | Feature Layer | Required | Input |

**Usage**

1. Use a definition query or a selection on the drive time layer so that only one ring is shown.
2. Run the tool and choose that layer as the input.

If the layer still contains more than one ring value, the tool uses the first one it reads and shows a warning listing all of them.

---

## Export Drive Time Maps

Exports one PDF per map in `MAPS_CONFIG`, each centered on the first feature of a point layer. By default it exports four:

| # | Ring | Zoom | File name |
|---|---|---|---|
| 1 | 5 min | In | `<State>_<Name>_5min zoom.pdf` |
| 2 | 5 min | Out | `<State>_<Name>_5min.pdf` |
| 3 | 6.5 min | Out | `<State>_<Name>_6.5min.pdf` |
| 4 | 7.5 min | Out | `<State>_<Name>_7.5min.pdf` |

`State` and `Name` are read from the first feature of the drive time layer (change `NAME_FIELDS` to use other fields). To export different rings or more or fewer maps, edit `MAPS_CONFIG` at the top of the script.

For each map, the tool filters the drive time layer to that ring, centers and scales the map frame, updates the title (for example `6.5 Minute Drive Time`), legend label and legend symbol color, and exports the layout. When it finishes, or if an export fails, it restores the layer's original definition query.

This tool uses the project's first layout and that layout's first map frame. Set `LAYOUT_NAME` or `MAP_FRAME_NAME` to choose specific ones.

**Parameters**

| Label | Data Type | Type | Direction | Notes |
|---|---|---|---|---|
| Center Point Layer | Feature Layer | Required | Input | Maps are centered on its first point |
| Drive Time Layer | Feature Layer | Required | Input | Must be in the map shown in the map frame |
| Output Folder | Folder | Required | Input | Where the PDFs are saved |
| Zoom-In Scale (miles) | Double | Required | Input | `1` means 1 inch on the page = 1 mile |
| Zoom-Out Scale (miles) | Double | Required | Input | `2` means 1 inch on the page = 2 miles |

Existing PDFs with the same name in the output folder are overwritten.

---

## Transpose to Excel Template

Takes an Excel export of a feature class (for example, drive time rings after **Table To Excel**) and writes it into an existing Excel template. Each field becomes a row in the template, and each record becomes a column, so a site's rings sit side by side:

| | B | C | D |
|---|---|---|---|
| **Ring** | 5 | 6.5 | 7.5 |
| **Population** | 500 | 700 | 900 |

Records are sorted by the sort field (ring size by default) before writing. The tool also sets the center page header of a summary sheet to the site name and state, its address (or its intersection if the address is blank) and today's date.

Requires `pandas` and `openpyxl`, which are included with ArcGIS Pro's default Python environment.

**Column mapping**

Which fields go to which cells, and the sheet names, come from a JSON file, so the script works with any template. Copy `column_mapping.example.json` to `column_mapping.json`, put it next to the script and edit it:

| Key | Meaning |
|---|---|
| `data_sheet` | Sheet the data is written to |
| `header_sheet` | Sheet whose page header is set |
| `sort_field` | Field to sort records by before writing (optional) |
| `header` | Fields used for the header: `name_field`, `state_field`, and `location_fields` (the first non-empty one is used) |
| `columns` | Each input field and the cell where its first value goes; further values fill the cells to the right |

`column_mapping.json` and Excel files are listed in `.gitignore`, so your real mapping and templates stay on your computer.

**Parameters**

| Label | Data Type | Type | Direction | Notes |
|---|---|---|---|---|
| Input Excel | File | Required | Input | Excel export of the feature class |
| Template Excel | File | Required | Input | The workbook to fill in (not changed) |
| Output Excel | File | Required | Output | Always saved as `.xlsx` |
| Column Mapping | File | Optional | Input | JSON mapping; defaults to `column_mapping.json` next to the script |

In ModelBuilder, the Output Excel value is passed on, so the next tool can use the finished workbook.

---

## License

[MIT](LICENSE)
