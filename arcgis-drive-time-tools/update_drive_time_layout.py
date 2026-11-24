"""
Update Drive Time Layout
========================

ArcGIS Pro script tool that updates layout elements to match the drive time
ring shown in the map frame.

It reads the RING_DEFN value from the input drive time polygon layer (honoring
the layer's definition query and selection), then:

  * sets the layout title text  -> "<ring> Minute Modified Drive Time"
  * sets the legend ring text   -> "<ring> min drive time"
  * recolors the legend ring symbol's outline to match the ring's color range

Requirements: ArcGIS Pro 3.x (uses CIM version "V3").

Script tool parameter:
  0  Drive Time Layer  (Feature Layer, Required, Input)
"""

import arcpy

# -----------------------
# Configuration
# Edit these to match your project.
# -----------------------
LAYOUT_NAME = "Layout"
RING_FIELD = "RING_DEFN"

TITLE_ELEMENT_NAME = "Dynamic Drive Time"
RING_TEXT_ELEMENT_NAME = "Drive Time Ring Text"
RING_SYMBOL_ELEMENT_NAME = "Drive Time Ring Symbol"

TITLE_TEMPLATE = "{ring} Minute Modified Drive Time"
RING_TEXT_TEMPLATE = "{ring} min drive time"

# Ring value ranges (minutes, inclusive) -> outline color (hex RGB).
# Values that fall outside every range use DEFAULT_COLOR.
RING_COLOR_RANGES = [
    (2.0, 6.5, "004DA8"),    # blue
    (7.0, 9.0, "73004C"),    # purple
    (9.5, 14.0, "FF0000"),   # red
    (14.5, 20.0, "38A800"),  # green
]
DEFAULT_COLOR = "004DA8"     # blue


# -----------------------
# Helpers
# -----------------------
def get_layout(aprx, name):
    """Return the layout with the given name, or raise a helpful error."""
    layouts = aprx.listLayouts(name)
    if not layouts:
        available = [l.name for l in aprx.listLayouts()]
        raise arcpy.ExecuteError(
            f"Could not find a layout named '{name}'. Available layouts: {available}"
        )
    return layouts[0]


def get_element(layout, element_type, name):
    """Return the named layout element of the given type, or raise a helpful error."""
    matches = [e for e in layout.listElements(element_type) if e.name == name]
    if not matches:
        raise arcpy.ExecuteError(
            f"Could not find {element_type} named '{name}' in layout '{layout.name}'."
        )
    return matches[0]


def to_float(value):
    """Convert a value to float, returning None if it isn't numeric."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def format_ring(value):
    """Format a ring value cleanly: 5.0 -> "5", 6.5 -> "6.5"."""
    num = to_float(value)
    return f"{num:g}" if num is not None else str(value).strip()


def get_ring_rgb(ring_str):
    """Return an (R, G, B) tuple for the given ring value using RING_COLOR_RANGES."""
    val = to_float(ring_str)
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


def read_ring_value(feature_layer):
    """
    Read the ring value from the layer. Cursors on a layer honor its
    definition query and selection. Warns if more than one ring is present.
    """
    ring_values = []
    with arcpy.da.SearchCursor(feature_layer, [RING_FIELD]) as cursor:
        for (ring_defn,) in cursor:
            if ring_defn is not None:
                ring_values.append(format_ring(ring_defn))

    if not ring_values:
        raise arcpy.ExecuteError(f"No {RING_FIELD} value found in the input layer.")

    ring = ring_values[0]
    unique_rings = sorted(set(ring_values), key=lambda v: to_float(v) or 0)

    if len(unique_rings) > 1:
        arcpy.AddWarning(
            f"Layer contains multiple ring values {unique_rings}. Using the first: '{ring}'. "
            "Apply a definition query or selection to control which ring is used."
        )

    return ring


# -----------------------
# Main
# -----------------------
def main():
    feature_layer = arcpy.GetParameterAsText(0)

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    layout = get_layout(aprx, LAYOUT_NAME)
    arcpy.AddMessage(f"Using layout: {layout.name}")

    title_element = get_element(layout, "TEXT_ELEMENT", TITLE_ELEMENT_NAME)
    ring_text_element = get_element(layout, "TEXT_ELEMENT", RING_TEXT_ELEMENT_NAME)
    ring_symbol_element = get_element(layout, "GRAPHIC_ELEMENT", RING_SYMBOL_ELEMENT_NAME)

    ring = read_ring_value(feature_layer)
    arcpy.AddMessage(f"Ring value: {ring}")

    title_element.text = TITLE_TEMPLATE.format(ring=ring)
    ring_text_element.text = RING_TEXT_TEMPLATE.format(ring=ring)
    set_ring_symbol_color(ring_symbol_element, ring)

    arcpy.AddMessage("Layout elements updated successfully.")


if __name__ == "__main__":
    main()
