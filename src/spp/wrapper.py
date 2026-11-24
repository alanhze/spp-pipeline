"""Persistent MATLAB engine that runs SPPplus on one CSV at a time."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True)
class SPPOptions:
    """Analysis settings passed to run_spp_analysis.m."""

    omega: float  # angular frequency [rad/s]
    harmonics: int = 7  # M: odd number of stress harmonics kept
    cycles: int = 1  # p: whole number of cycles in each CSV
    strain_scale: float = 1.0  # 0.01 if the export gives strain in %
    truncate: tuple[int, int] | None = None  # (first_row, last_row), 1-based

    def output_path(self, csv_path: Path) -> Path:
        """The main results file SPPplus writes for ``csv_path``."""
        csv_path = Path(csv_path)
        stem = csv_path.stem
        if self.truncate:
            stem += f"_trunc{self.truncate[0]}-{self.truncate[1]}"
        return csv_path.with_name(f"{stem}_SPP_FOURIER.txt")


def _import_engine():
    try:
        import matlab
        import matlab.engine
    except ImportError as e:
        raise ImportError(
            "MATLAB Engine for Python not found. Install the version matching "
            "your MATLAB release, e.g. pip install 'matlabengine==24.2.*' (R2024b). "
            "See the README."
        ) from e
    return matlab


class SPPMatlabProcessor:
    """Start MATLAB once and reuse it for every file.

    Use as a context manager::

        with SPPMatlabProcessor(spp_dir, options) as proc:
            ok = proc.process_file("sample_Sine Strain - 1.csv")
    """

    def __init__(self, spp_dir: str | Path, options: SPPOptions):
        self.spp_dir = Path(spp_dir).resolve()
        self.options = options
        self.eng = None
        self._matlab = None

    def __enter__(self):
        if not self.spp_dir.is_dir():
            raise FileNotFoundError(f"SPPplus folder not found: {self.spp_dir}")

        self._matlab = _import_engine()
        print("Starting MATLAB Engine (this may take a few seconds)...")
        self.eng = self._matlab.engine.start_matlab()

        bundled = str(files("spp") / "matlab")
        self.eng.addpath(bundled, nargout=0)
        self.eng.addpath(self.eng.genpath(str(self.spp_dir)), nargout=0)

        if self.eng.exist("SPPplus_fourier_v2", nargout=1) != 2:
            self.__exit__(None, None, None)
            raise FileNotFoundError(
                f"SPPplus_fourier_v2.m not found under {self.spp_dir}. "
                "Point --spp-dir at the folder containing the SPPplus v2 files."
            )

        # Figures are never shown in batch mode.
        self.eng.eval("set(0, 'DefaultFigureVisible', 'off');", nargout=0)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.eng is not None:
            self.eng.quit()
            self.eng = None
            print("MATLAB Engine stopped.")

    def _name_value_args(self) -> list:
        o = self.options
        args = [
            "omega", float(o.omega),
            "M", float(o.harmonics),
            "p", float(o.cycles),
            "strain_scale", float(o.strain_scale),
        ]  # fmt: skip
        if o.truncate:
            args += ["data_trunc", self._matlab.double([1.0, *map(float, o.truncate)])]
        return args

    def process_file(self, csv_path: str | Path) -> bool:
        """Run SPPplus on one CSV. Returns True on success, False on failure."""
        fname_no_ext = str(Path(csv_path).resolve().with_suffix(""))
        try:
            self.eng.run_spp_analysis(fname_no_ext, *self._name_value_args(), nargout=0)
            return True
        except self._matlab.engine.MatlabExecutionError as e:
            print(f"  [MATLAB ERROR] {Path(csv_path).name}:\n{e}")
            return False
        finally:
            # SPPplus draws ~5 hidden figures per file; close them so they
            # don't pile up in memory over a long batch.
            self.eng.close("all", "force", nargout=0)
