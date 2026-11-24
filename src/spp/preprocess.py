"""Extract the four SPP input columns from rheometer Excel exports into CSVs."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# Column names as they appear in the instrument export (header row = 2nd row,
# units row = 3rd row). Order matters: SPPplus expects Time, Strain, Rate, Stress.
REQUIRED = ["Step time", "Strain (step)", "Shear rate", "Stress (step)"]

# Sheets that hold one oscillation each, e.g. "Sine Strain - 1".
DEFAULT_SHEET_PATTERN = r"Sine Strain - \d+"


def csv_path_for(output_dir: Path, workbook_stem: str, sheet: str) -> Path:
    """Name of the CSV written for one sheet of one workbook."""
    return Path(output_dir) / f"{workbook_stem}_{sheet}.csv"


def find_extracted_csvs(
    output_dir: Path, workbook_stem: str, sheet_pattern: str = DEFAULT_SHEET_PATTERN
) -> list[Path]:
    """CSVs previously extracted from one workbook."""
    pattern = re.compile(rf"{re.escape(workbook_stem)}_{sheet_pattern}\.csv")
    return sorted(
        f for f in Path(output_dir).glob("*.csv") if pattern.fullmatch(f.name)
    )


def extract_columns_to_csv(
    file_path: str | Path,
    output_dir: str | Path = ".",
    sheet_pattern: str = DEFAULT_SHEET_PATTERN,
) -> list[Path]:
    """Write one header-less CSV (Time, Strain, Rate, Stress) per matching sheet.

    Returns the paths of the CSVs written. Sheets whose names don't match
    ``sheet_pattern``, or that lack any required column, are skipped.
    """
    file_path, output_dir = Path(file_path), Path(output_dir)
    sheet_re = re.compile(sheet_pattern)
    created: list[Path] = []

    with pd.ExcelFile(file_path, engine="calamine") as wb:
        for sheet in wb.sheet_names:
            if not sheet_re.fullmatch(sheet):
                continue
            df = wb.parse(
                sheet,
                header=1,  # 2nd row holds the column names
                skiprows=[2],  # 3rd row holds the units
                usecols=lambda c: c in REQUIRED,
            )
            missing = [c for c in REQUIRED if c not in df.columns]
            if missing:
                print(
                    f"  [WARN] Sheet '{sheet}' in '{file_path.name}' is missing "
                    f"{missing}; skipped."
                )
                continue
            out = csv_path_for(output_dir, file_path.stem, sheet)
            df[REQUIRED].to_csv(out, index=False, header=False)
            created.append(out)

    return created
