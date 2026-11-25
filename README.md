# spp-pipeline

Batch-process oscillatory rheometer exports with the **Sequence of Physical
Processes (SPP)** method. The pipeline:

1. reads every Excel export in a folder,
2. writes one CSV (time, strain, rate, stress) per oscillation sheet, and
3. runs **SPPplus v2** (MATLAB, Fourier mode) on each CSV in a single MATLAB session.

Files that are already up to date are skipped, so re-running a folder is cheap.

## Requirements

- MATLAB (tested with **R2024b**) — SPPplus itself needs no extra toolboxes
- **SPPplus v2.1** by the Rogers group (not included, see below)
- [pixi](https://pixi.sh) (recommended) or Python 3.10–3.12 with pip

### Getting SPPplus

SPPplus is distributed by the Rogers Soft Matter group and is **not** included
in this repository. Request a copy from Prof. Simon Rogers via the
[SPP page](https://publish.illinois.edu/rogerssoftmatter/?p=173) and
unzip it anywhere, e.g. `C:\tools\SPPplus_v2`. This pipeline was tested with
SPPplus v2.1 (May 2021). It needs these files from that folder:
`SPPplus_read_v2.m`, `SPPplus_fourier_v2.m`, `SPPplus_print_v2.m`,
`SPPplus_figures_v2.m`.

## Install

```bash
git clone https://github.com/alanhze/spp-pipeline.git
cd spp-pipeline
pixi install
```

**MATLAB:** The MATLAB engine version must match your MATLAB.
For example, for R2025a:

```bash
pixi add --pypi --feature matlab "matlabengine==25.1.*"
```

See the [PyPI release history](https://pypi.org/project/matlabengine/#history)
for the version that matches your release, and MathWorks'
[Python compatibility table](https://www.mathworks.com/support/requirements/python-compatibility.html).

**Without pixi:**

```bash
pip install -e .
pip install "matlabengine==24.2.*"   # match your MATLAB release
```

**Linux/macOS:** if MATLAB is not in its default location and the engine can't
find it, add MATLAB's library folder to your shell startup file:

```bash
# Linux
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:<matlabroot>/bin/glnxa64
# macOS (Apple silicon: maca64, Intel: maci64)
export DYLD_LIBRARY_PATH=$DYLD_LIBRARY_PATH:<matlabroot>/bin/maca64
```

## Usage

Start from Excel exports:

```bash
pixi run spp excel data/raw data/processed --spp-dir C:/tools/SPPplus_v2 --omega 0.628
```

Re-run SPP on CSVs you already extracted:

```bash
pixi run spp csv data/processed --spp-dir C:/tools/SPPplus_v2 --omega 0.628
```

Set the `SPP_DIR` environment variable to skip `--spp-dir` every time.
Run `pixi run spp excel --help` for all options.

| Option | Default | Meaning |
|---|---|---|
| `--omega` | *required* | Angular frequency in rad/s (2π × Hz; 0.1 Hz → 0.628) |
| `--harmonics` | 7 | Odd number of stress harmonics kept in the Fourier reconstruction |
| `--cycles` | 1 | Whole number of oscillation cycles in each sheet |
| `--strain-percent` | off | Use if your export gives strain in %, so it's converted to [-] |
| `--truncate FIRST LAST` | off | Keep only data rows FIRST..LAST of each sheet |
| `--prefix` | none | Only process files whose names start with this text |
| `--sheet-pattern` | `Sine Strain - \d+` | Regex for the sheet names that hold oscillation data |
| `--force` | off | Re-run MATLAB even if results look up to date |

The command exits with code 1 and lists the failed files if anything fails.

### Disable SPPplus plotting (recommended)

SPPplus draws several figures for every file, which slows down batch runs
considerably and doesn't affect the results files. To turn plotting off, open
`SPPplus_fourier_v2.m` in your SPPplus folder, find the call to
`SPPplus_figures_v2` at the end of the file (lines 175–176 in v2.1), and
comment out both lines:

```matlab
% SPPplus_figures_v2(spp_data_in,spp_params,spp_data_out,ft_out,out_set(3),...
%     'FOURIER',fname,getfigs)
```

This also disables plots when you run SPPplus directly in MATLAB, so keep an
unmodified copy if you want the figures there.

## Input format

Each workbook has one sheet per oscillation, named like `Sine Strain - 1`
(this is how TRIOS exports). In each sheet:

- row 1: step name (ignored)
- row 2: column names, which must include `Step time`, `Strain (step)`,
  `Shear rate`, `Stress (step)` (other columns are ignored)
- row 3: units (ignored)
- row 4 onward: data

Fourier mode needs each sheet to contain a **whole number of cycles**
(`--cycles`), ideally with an even number of points per cycle.

## Output

Next to each CSV, SPPplus writes `<name>_SPP_FOURIER.txt` with time, strain,
rate, stress, G′ₜ, G″ₜ, |G*ₜ|, tan δₜ, δₜ, displacement stress, estimated
equilibrium strain, dG′ₜ/dt, dG″ₜ/dt, speed and normalized PAV.

**Sanity check:** for a small-amplitude (linear) sheet, G′ₜ and G″ₜ should be
nearly constant and close to the G′ and G″ your instrument reports. If they are
off by ~100×, your strain units are wrong; toggle `--strain-percent`.

## Development

```bash
pixi run test     # unit tests (no MATLAB needed)
pixi run check    # lint + tests
```

## Citing

Also cite the papers the SPPplus
authors ask for in their run script:

- Rogers, S. A. (2017). In search of physical meaning: defining transient
  parameters for nonlinear viscoelasticity. *Rheologica Acta*, 56, 501–525.
- Donley, G. J., et al. (2019). Time-resolved dynamics of the yielding
  transition in soft materials. *Journal of Non-Newtonian Fluid Mechanics*.

## License

MIT for the code in this repository. SPPplus is distributed separately by its
authors under their own terms.
