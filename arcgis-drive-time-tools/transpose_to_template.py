# -*- coding: utf-8 -*-
"""
Transpose to Excel Template
===========================

ArcGIS Pro script tool (also usable from ModelBuilder) that copies attribute
data from an Excel export of a feature class into an existing Excel template.

Each field in the input becomes a row in the template: the field's values are
written left to right starting at the cell given in the column mapping, one
column per input record (for example, one column per drive time ring). Records
are sorted by a sort field (such as ring size) first.

It also sets the center page header of a summary sheet to:

    <NAME>, <STATE>
    <LOCATION>          (first non-empty location field, e.g. address or intersection)
    <today's date>

Which fields go where, and the sheet names, are read from a JSON mapping file,
so the script itself contains nothing specific to one template.
See column_mapping.example.json.

Script tool parameters:
  0  Input Excel        (File, Required, Input)    e.g. output of Table To Excel
  1  Template Excel     (File, Required, Input)
  2  Output Excel       (File, Required, Output)
  3  Column Mapping     (File, Optional, Input)    JSON; defaults to
                                                   column_mapping.json next to this script
"""

import json
import os
from datetime import datetime

import openpyxl
import pandas as pd

try:
    import arcpy
except ImportError:  # Allows running and testing outside ArcGIS Pro
    arcpy = None

DEFAULT_MAPPING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "column_mapping.json")


# -----------------------
# Messaging (works inside or outside ArcGIS Pro)
# -----------------------
def message(text):
    arcpy.AddMessage(text) if arcpy else print(text)


def warning(text):
    arcpy.AddWarning(text) if arcpy else print(f"WARNING: {text}")


# -----------------------
# Helpers
# -----------------------
def load_mapping(path):
    """Load and check the JSON mapping file."""
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Column mapping file not found: {path}. "
            "Copy column_mapping.example.json to column_mapping.json and edit it."
        )
    with open(path, encoding="utf-8") as f:
        mapping = json.load(f)
    for key in ("data_sheet", "header_sheet", "columns"):
        if key not in mapping:
            raise ValueError(f"Column mapping file is missing '{key}'.")
    return mapping


def is_blank(value):
    """True for None, NaN and empty or whitespace-only strings."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() == ""


def first_value(df, field):
    """Return the first record's value for a field, or '' if missing or blank."""
    if field and field in df.columns and len(df):
        value = df[field].iloc[0]
        return "" if is_blank(value) else value
    return ""


def build_header_text(df, header_cfg):
    """Build the center header text from the first record."""
    name = str(first_value(df, header_cfg.get("name_field"))).upper()
    state = str(first_value(df, header_cfg.get("state_field"))).upper()

    location = ""
    for field in header_cfg.get("location_fields", []):
        location = first_value(df, field)
        if location != "":
            break
    # "&" is a formatting code in Excel headers; "&&" prints a literal "&"
    location = str(location).upper().replace("&", "&&")
    name = name.replace("&", "&&")

    today = datetime.today()
    date_text = f"{today.month}/{today.day}/{today.year}"

    # The leading blank lines push the text down below the top margin
    return f"\n\n{name}, {state}\n{location}\n{date_text}"


# -----------------------
# Main logic
# -----------------------
def transpose_into_template(input_excel, template_excel, output_excel, mapping):
    output_excel = os.path.splitext(output_excel)[0] + ".xlsx"

    if not os.path.isfile(input_excel):
        raise FileNotFoundError(f"Input Excel not found: {input_excel}")
    if not os.path.isfile(template_excel):
        raise FileNotFoundError(f"Template Excel not found: {template_excel}")

    # Read input and drop fully empty rows
    df = pd.read_excel(input_excel).dropna(how="all").reset_index(drop=True)

    # Sort records (e.g. by ring size) so columns come out in order
    sort_field = mapping.get("sort_field")
    if sort_field:
        if sort_field in df.columns:
            df[sort_field] = pd.to_numeric(df[sort_field], errors="coerce")
            df = df.sort_values(by=sort_field).reset_index(drop=True)
        else:
            warning(f"Sort field '{sort_field}' not found in input; records left unsorted.")

    # Replace NaN/NaT with None so Excel gets truly empty cells
    df = df.astype(object).where(pd.notna(df), None)

    wb = openpyxl.load_workbook(template_excel)
    for sheet_key in ("data_sheet", "header_sheet"):
        if mapping[sheet_key] not in wb.sheetnames:
            raise ValueError(
                f"Sheet '{mapping[sheet_key]}' not found in template. "
                f"Available sheets: {wb.sheetnames}"
            )
    ws = wb[mapping["data_sheet"]]
    header_ws = wb[mapping["header_sheet"]]

    # Write each field's values across a row, one column per record
    missing = []
    for field, start_cell in mapping["columns"].items():
        if field not in df.columns:
            missing.append(field)
            continue
        start = ws[start_cell]
        for i, value in enumerate(df[field].tolist()):
            ws.cell(row=start.row, column=start.column + i, value=value)
    if missing:
        warning(f"These mapped fields were not in the input and were skipped: {missing}")

    header_ws.oddHeader.center.text = build_header_text(df, mapping.get("header", {}))

    wb.save(output_excel)
    wb.close()

    message(f"Wrote {len(df)} record(s) to: {output_excel}")
    return output_excel


# -----------------------
# Script tool entry point
# -----------------------
def main():
    input_excel = arcpy.GetParameterAsText(0)
    template_excel = arcpy.GetParameterAsText(1)
    output_excel = arcpy.GetParameterAsText(2)
    mapping_file = arcpy.GetParameterAsText(3) or DEFAULT_MAPPING_FILE

    if not output_excel:
        raise arcpy.ExecuteError("Output Excel is required.")

    try:
        mapping = load_mapping(mapping_file)
        output_excel = transpose_into_template(input_excel, template_excel,
                                               output_excel, mapping)
    except Exception as e:
        arcpy.AddError(str(e))
        raise

    # Pass the final path forward for the next ModelBuilder step
    arcpy.SetParameterAsText(2, output_excel)


if __name__ == "__main__":
    main()
