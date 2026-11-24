"""Unit tests that run without MATLAB."""

import os
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

from spp import cli
from spp.preprocess import REQUIRED, extract_columns_to_csv, find_extracted_csvs
from spp.wrapper import SPPOptions


def make_workbook(path: Path, sheets: dict[str, bool]) -> Path:
    """Mimic the instrument export: step name, headers, units, then data.

    ``sheets`` maps sheet name -> whether it has all required columns.
    """
    wb = Workbook()
    wb.remove(wb.active)
    for name, complete in sheets.items():
        ws = wb.create_sheet(name)
        cols = REQUIRED + ["Extra"] if complete else REQUIRED[:2]
        ws.append([name])
        ws.append(cols)
        ws.append(["s", "%", "1/s", "Pa", "-"][: len(cols)])
        for i in range(4):
            ws.append([float(i + 10 * j) for j in range(len(cols))])
    wb.save(path)
    return path


def test_extract_writes_matching_sheets_only(tmp_path):
    xlsx = make_workbook(
        tmp_path / "S1.xlsx",
        {"Sine Strain - 1": True, "Sine Strain - 2": False, "Summary": True},
    )
    out = tmp_path / "out"
    out.mkdir()

    created = extract_columns_to_csv(xlsx, out)

    assert [p.name for p in created] == ["S1_Sine Strain - 1.csv"]
    df = pd.read_csv(created[0], header=None)
    assert df.shape == (4, 4)  # 4 rows, Extra column dropped, units row skipped
    assert df.iloc[0].tolist() == [0.0, 10.0, 20.0, 30.0]
    assert find_extracted_csvs(out, "S1") == created


def test_output_path_accounts_for_truncation(tmp_path):
    csv = tmp_path / "a_Sine Strain - 1.csv"
    plain = SPPOptions(0.628).output_path(csv).name
    assert plain == "a_Sine Strain - 1_SPP_FOURIER.txt"
    assert (
        SPPOptions(0.628, truncate=(1, 287)).output_path(csv).name
        == "a_Sine Strain - 1_trunc1-287_SPP_FOURIER.txt"
    )


def test_needs_processing(tmp_path):
    opts = SPPOptions(0.628)
    csv = tmp_path / "a_Sine Strain - 1.csv"
    csv.write_text("1,2,3,4\n")
    assert cli.needs_processing(csv, opts)  # no output yet

    out = opts.output_path(csv)
    out.write_text("results")
    os.utime(csv, (1, 1))  # CSV older than output
    assert not cli.needs_processing(csv, opts)


class FakeProcessor:
    """Stands in for MATLAB: fails on files with 'bad' in the name."""

    def __init__(self, spp_dir, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def process_file(self, csv):
        if "bad" in Path(csv).name:
            return False
        self.options.output_path(csv).write_text("ok")
        return True


def test_cli_end_to_end_reports_failures(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "SPPMatlabProcessor", FakeProcessor)
    src, out = tmp_path / "in", tmp_path / "out"
    src.mkdir()
    make_workbook(src / "good.xlsx", {"Sine Strain - 1": True})
    make_workbook(src / "bad.xlsx", {"Sine Strain - 1": True})
    (src / "notes.txt").write_text("ignored")

    argv = ["excel", str(src), str(out), "--spp-dir", str(tmp_path), "--omega", "0.628"]
    assert cli.main(argv) == 1
    assert "bad_Sine Strain - 1.csv" in capsys.readouterr().out

    # Second run: extraction and good file are skipped; only the bad one retries.
    assert cli.main(argv) == 1
    printed = capsys.readouterr().out
    assert "1 pending, 1 up to date" in printed


def test_prefix_filter(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "SPPMatlabProcessor", FakeProcessor)
    src, out = tmp_path / "in", tmp_path / "out"
    src.mkdir()
    make_workbook(src / "TJC2_a.xlsx", {"Sine Strain - 1": True})
    make_workbook(src / "other.xlsx", {"Sine Strain - 1": True})

    argv = [
        "excel",
        str(src),
        str(out),
        "--spp-dir",
        str(tmp_path),
        "--omega",
        "0.628",
        "--prefix",
        "TJC2_",
    ]
    assert cli.main(argv) == 0
    assert [p.name for p in out.glob("*.csv")] == ["TJC2_a_Sine Strain - 1.csv"]


def test_even_harmonics_rejected(tmp_path):
    argv = [
        "csv",
        str(tmp_path),
        "--spp-dir",
        str(tmp_path),
        "--omega",
        "0.628",
        "--harmonics",
        "6",
    ]
    assert cli.main(argv) == 2


@pytest.mark.parametrize("flag", ["--help"])
def test_help_runs(flag):
    with pytest.raises(SystemExit) as e:
        cli.main([flag])
    assert e.value.code == 0
