"""
Export Drive Time Maps
======================

ArcGIS Pro script tool that exports a set of drive time maps to PDF, centered
on a point, one PDF per entry in MAPS_CONFIG.

By default it exports four PDFs:
  1. 5 min ring, zoomed in   -> "<State>_<Name>_5min zoom.pdf"
  2. 5 min ring, zoomed out  -> "<State>_<Name>_5min.pdf"
  3. 6.5 min ring, zoomed out -> "<State>_<Name>_6.5min.pdf"
  4. 7.5 min ring, zoomed out -> "<State>_<Name>_7.5min.pdf"

For each map it filters the drive time layer to one ring, centers and scales
the map frame, updates the title, legend label and legend symbol color, then
exports the layout. The layer's original definition query is restored at the
end, even if an export fails.

Requirements: ArcGIS Pro 3.x (uses CIM version "V3").

Script tool parameters:
  0  Center Point Layer   (Feature Layer, Required, Input)
  1  Drive Time Layer     (Feature Layer, Required, Input)
  2  Output Folder        (Folder, Required, Input)
  3  Zoom-In Scale (mi)   (Double, Required, Input)  e.g. 1  -> 1 inch = 1 mile
  4  Zoom-Out Scale (mi)  (Double, Required, Input)  e.g. 2  -> 1 inch = 2 miles
"""

import os
import time

import arcpy

# -----------------------
# Configuration
# Edit these to match your project.
# -----------------------
LAYOUT_NAME = None          # None = use the project's first layout
MAP_FRAME_NAME = None       # None = use the layout's first map frame

RING_FIELD = "RING_DEFN"    # Text field holding the ring size, e.g. "5", "6.5"
NAME_FIELDS = ["State", "Name"]  # Fields used to build the PDF file names

TITLE_ELEMENT_NAME = "Dynamic Drive Time"
RING_TEXT_ELEMENT_NAME = "Drive Time Ring Text"
RING_SYMBOL_ELEMENT_NAME = "Drive Time Ring Symbol"

TITLE_TEMPLATE = "{ring} Minute Drive Time"
RING_TEXT_TEMPLATE = "{ring} min drive time"

# Maps to export, in order. "zoom": "in" uses the zoom-in scale, "out" the
# zoom-out scale. "suffix" is added to the end of the file name.
MAPS_CONFIG = [
    {"ring": "5",   "zoom": "in",  "suffix": " zoom"},
    {"ring": "5",   "zoom": "out", "suffix": ""},
    {"ring": "6.5", "zoom": "out", "suffix": ""},
    {"ring": "7.5", "zoom": "out", "suffix": ""},
]

# Ring value ranges (minutes, inclusive) -> outline color (hex RGB).
# Values that fall outside every range use DEFAULT_COLOR.
RING_COLOR_RANGES = [
    (2.0, 6.5, "004DA8"),    # blue
    (7.0, 9.0, "73004C"),    # purple
    (9.5, 14.0, "FF0000"),   # red
    (14.5, 20.0, "38A800"),  # green
]
DEFAULT_COLOR = "004DA8"     # blue

RENDER_WAIT_SECONDS = 1     # Pause before each export so polygons can draw

INVALID_FILENAME_CHARS = '<>:"/\\|?*'
INCHES_PER_MILE = 63360


# -----------------------
# Helpers
# -----------------------
def pick_by_name(items, name, kind, where):
    """Return the item with the given name (or the first item if name is None)."""
    items = list(items)
    if name is None:
        if not items:
            raise arcpy.ExecuteError(f"No {kind} found in {where}.")
        return items[0]
    matches = [item for item in items if item.name == name]
    if not matches:
        available = [item.name for item in items]
        raise arcpy.ExecuteError(
            f"Could not find {kind} named '{name}' in {where}. Available: {available}"
        )
    return matches[0]


def miles_to_scale(miles):
    """Convert '1 inch = X miles' into a map scale denominator."""
    return float(miles) * INCHES_PER_MILE


def get_ring_rgb(ring_str):
    """Return an (R, G, B) tuple for the given ring value using RING_COLOR_RANGES."""
    try:
        val = float(ring_str)
    except (ValueError, TypeError):
        val = None
    hex_color = DEFAULT_COLOR
    if val is not None:
        for low, high, color in RING_COLOR_RANGES:
            if low <= val <= high:
                hex_color = color
                break
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def set_ring_symbol_color(graphic_element, ring_str):
    """
    Set the outline color of a layout graphic element by editing its CIM.
    Assumes symbolLayers[0] is the outline (stroke), which is the default
    for polygon graphics created in ArcGIS Pro.
    """
    r, g, b = get_ring_rgb(ring_str)
    cim = graphic_element.getDefinition("V3")
    try:
        cim.graphic.symbol.symbol.symbolLayers[0].color.values = [r, g, b, 100]
    except (AttributeError, IndexError):
        raise arcpy.ExecuteError(
            f"'{graphic_element.name}' does not have the expected symbol structure. "
            "It should be a polygon graphic with an outline."
        )
    graphic_element.setDefinition(cim)
    arcpy.AddMessage(f"Ring symbol outline set for ring '{ring_str}' -> RGB({r},{g},{b}).")


def clean_for_filename(value):
    """Make a value safe to use in a Windows file name."""
    text = "" if value is None else str(value).strip()
    for char in INVALID_FILENAME_CHARS:
        text = text.replace(char, "_")
    return text or "Unknown"


def get_center_xy(point_layer):
    """Return the (X, Y) of the first point in the layer."""
    with arcpy.da.SearchCursor(point_layer, ["SHAPE@XY"]) as cursor:
        row = next(cursor, None)
    if row is None:
        raise arcpy.ExecuteError("The center point layer has no features.")
    return row[0]


def get_name_parts(layer):
    """Read the file-name fields from the first feature of the layer."""
    with arcpy.da.SearchCursor(layer, NAME_FIELDS) as cursor:
        row = next(cursor, None)
    if row is None:
        raise arcpy.ExecuteError(
            f"The drive time layer has no features to read {NAME_FIELDS} from."
        )
    return [clean_for_filename(v) for v in row]


# -----------------------
# Main
# -----------------------
def main():
    point_layer = arcpy.GetParameterAsText(0)
    drive_time_layer = arcpy.GetParameterAsText(1)
    output_folder = arcpy.GetParameterAsText(2)
    zoom_in_miles = arcpy.GetParameter(3)
    zoom_out_miles = arcpy.GetParameter(4)

    scales = {
        "in": miles_to_scale(zoom_in_miles),
        "out": miles_to_scale(zoom_out_miles),
    }
    arcpy.AddMessage(f"Zoom-in:  1 in = {zoom_in_miles} mi -> 1:{int(scales['in'])}")
    arcpy.AddMessage(f"Zoom-out: 1 in = {zoom_out_miles} mi -> 1:{int(scales['out'])}")

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    layout = pick_by_name(aprx.listLayouts(), LAYOUT_NAME, "layout", "the project")
    map_frame = pick_by_name(
        layout.listElements("MAPFRAME_ELEMENT"), MAP_FRAME_NAME,
        "map frame", f"layout '{layout.name}'"
    )
    map_obj = map_frame.map
    arcpy.AddMessage(f"Using layout: {layout.name}")
    arcpy.AddMessage(f"Using map frame: {map_frame.name}")

    # Find the drive time layer in the map frame's map
    lyr_name = arcpy.Describe(drive_time_layer).name
    lyr = pick_by_name(map_obj.listLayers(), lyr_name, "layer", f"map '{map_obj.name}'")

    title_element = pick_by_name(
        layout.listElements("TEXT_ELEMENT"), TITLE_ELEMENT_NAME,
        "text element", f"layout '{layout.name}'"
    )
    ring_text_element = pick_by_name(
        layout.listElements("TEXT_ELEMENT"), RING_TEXT_ELEMENT_NAME,
        "text element", f"layout '{layout.name}'"
    )
    ring_symbol_element = pick_by_name(
        layout.listElements("GRAPHIC_ELEMENT"), RING_SYMBOL_ELEMENT_NAME,
        "graphic element", f"layout '{layout.name}'"
    )

    center_x, center_y = get_center_xy(point_layer)
    name_prefix = "_".join(get_name_parts(lyr))

    original_query = lyr.definitionQuery
    try:
        for config in MAPS_CONFIG:
            ring = config["ring"]
            lyr.definitionQuery = f"{RING_FIELD} = '{ring}'"

            map_frame.camera.scale = scales[config["zoom"]]
            map_frame.camera.X = center_x
            map_frame.camera.Y = center_y

            title_element.text = TITLE_TEMPLATE.format(ring=ring)
            ring_text_element.text = RING_TEXT_TEMPLATE.format(ring=ring)
            set_ring_symbol_color(ring_symbol_element, ring)

            time.sleep(RENDER_WAIT_SECONDS)

            file_name = f"{name_prefix}_{ring}min{config['suffix']}.pdf"
            output_pdf = os.path.join(output_folder, file_name)
            layout.exportToPDF(output_pdf)
            arcpy.AddMessage(f"Exported: {output_pdf}")
    finally:
        # Put the layer back the way it was, even if something failed
        lyr.definitionQuery = original_query

    arcpy.AddMessage("All maps exported successfully.")


if __name__ == "__main__":
    main()
