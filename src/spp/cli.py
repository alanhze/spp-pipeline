"""Command-line entry point: ``spp-pipeline excel ...`` or ``spp-pipeline csv ...``."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from spp.preprocess import (
    DEFAULT_SHEET_PATTERN,
    extract_columns_to_csv,
    find_extracted_csvs,
)
from spp.wrapper import SPPMatlabProcessor, SPPOptions


def needs_processing(csv_path: Path, options: SPPOptions) -> bool:
    """True if the SPP output is missing, empty, or older than the CSV."""
    out = options.output_path(csv_path)
    if not out.is_file() or out.stat().st_size == 0:
        return True
    return out.stat().st_mtime < Path(csv_path).stat().st_mtime


def extract_excel_folder(
    input_dir: Path, output_dir: Path, prefix: str, sheet_pattern: str
) -> tuple[list[Path], list[str]]:
    """Extract CSVs from every Excel file in ``input_dir``.

    Returns (csv files, names of workbooks that failed).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    workbooks = sorted(
        f
        for f in input_dir.iterdir()
        if f.is_file()
        and f.suffix.lower() in {".xls", ".xlsx"}
        and f.name.startswith(prefix)
        and not f.name.startswith("~$")  # Excel lock files
    )
    print(f"Found {len(workbooks)} Excel files.")

    csvs: list[Path] = []
    failed: list[str] = []
    for wb in workbooks:
        existing = find_extracted_csvs(output_dir, wb.stem, sheet_pattern)
        if existing and all(c.stat().st_mtime >= wb.stat().st_mtime for c in existing):
            print(f"  [SKIP EXTRACT] {wb.name} ({len(existing)} CSVs up to date)")
            csvs.extend(existing)
            continue
        try:
            created = extract_columns_to_csv(wb, output_dir, sheet_pattern)
        except Exception as e:  # unreadable workbook: report and keep going
            print(f"  [ERROR] {wb.name}: {e}")
            failed.append(wb.name)
            continue
        print(f"  [EXTRACT] {wb.name} -> {len(created)} CSVs")
        if not created:
            print(f"  [WARN] No sheets matching '{sheet_pattern}' in {wb.name}")
        csvs.extend(created)

    return sorted(set(csvs)), failed


def find_csv_folder(input_dir: Path, prefix: str, sheet_pattern: str) -> list[Path]:
    pattern = re.compile(rf"{re.escape(prefix)}.*_{sheet_pattern}\.csv")
    return sorted(f for f in input_dir.glob("*.csv") if pattern.fullmatch(f.name))


def run_matlab(
    csvs: list[Path], spp_dir: Path, options: SPPOptions, force: bool
) -> list[str]:
    """Run SPPplus on CSVs that need it. Returns names of files that failed."""
    pending = [c for c in csvs if force or needs_processing(c, options)]
    print(f"\nMATLAB: {len(pending)} pending, {len(csvs) - len(pending)} up to date.")
    if not pending:
        return []

    failed: list[str] = []
    with SPPMatlabProcessor(spp_dir, options) as proc:
        for i, csv in enumerate(pending, 1):
            print(f"  [{i}/{len(pending)}] {csv.name}")
            if not proc.process_file(csv):
                failed.append(csv.name)
    return failed


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="spp-pipeline",
        description="Convert rheometer Excel exports to CSV and run SPPplus on them.",
    )
    sub = p.add_subparsers(dest="mode", required=True)

    excel = sub.add_parser("excel", help="Start from Excel exports.")
    excel.add_argument("input", type=Path, help="Folder of .xls/.xlsx files")
    excel.add_argument("output", type=Path, help="Folder for CSVs and SPP results")

    csv = sub.add_parser("csv", help="Start from CSVs that were already extracted.")
    csv.add_argument("input", type=Path, help="Folder of extracted CSVs")

    for s in (excel, csv):
        s.add_argument(
            "--spp-dir",
            type=Path,
            default=os.environ.get("SPP_DIR"),
            required="SPP_DIR" not in os.environ,
            help="Folder containing the SPPplus v2 .m files (or set SPP_DIR)",
        )
        s.add_argument(
            "--omega",
            type=float,
            required=True,
            help="Angular frequency in rad/s (0.1 Hz -> 0.6283)",
        )
        s.add_argument(
            "--harmonics",
            type=int,
            default=7,
            help="Odd number of stress harmonics kept (default 7)",
        )
        s.add_argument(
            "--cycles",
            type=int,
            default=1,
            help="Whole number of cycles in each sheet (default 1)",
        )
        s.add_argument(
            "--strain-percent",
            action="store_true",
            help="Strain in the export is in %% (multiply by 0.01)",
        )
        s.add_argument(
            "--truncate",
            type=int,
            nargs=2,
            metavar=("FIRST", "LAST"),
            help="Keep only data rows FIRST..LAST (1-based)",
        )
        s.add_argument(
            "--prefix",
            default="",
            help="Only process files whose names start with this",
        )
        s.add_argument(
            "--sheet-pattern",
            default=DEFAULT_SHEET_PATTERN,
            help="Regex for sheet names (default: Sine Strain - N)",
        )
        s.add_argument(
            "--force",
            action="store_true",
            help="Re-run MATLAB even if results are up to date",
        )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.harmonics % 2 != 1:
        print("error: --harmonics must be odd", file=sys.stderr)
        return 2

    options = SPPOptions(
        omega=args.omega,
        harmonics=args.harmonics,
        cycles=args.cycles,
        strain_scale=0.01 if args.strain_percent else 1.0,
        truncate=tuple(args.truncate) if args.truncate else None,
    )

    failed: list[str] = []
    if args.mode == "excel":
        csvs, failed = extract_excel_folder(
            args.input, args.output, args.prefix, args.sheet_pattern
        )
    else:
        csvs = find_csv_folder(args.input, args.prefix, args.sheet_pattern)
        print(f"Found {len(csvs)} CSV files.")

    failed += run_matlab(csvs, args.spp_dir, options, args.force)

    if failed:
        print(f"\n{len(failed)} file(s) failed:")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("\nDone. All files processed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
