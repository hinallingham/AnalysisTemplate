"""Shared helpers for the NoiseMasking / Prealignment / Alignment /
run_analysis step scripts: run corry, then plot the result in the MALTA2
house ROOT style (scripts/style/plot_style.py, from the root-plot-polish
skill) instead of matplotlib.

Run these scripts with the project venv's interpreter so ROOT (via the
shared PYTHONPATH) is available, e.g.:

    ../.venv/bin/python3 NoiseMasking.py 1 --data-dir ../data
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import ROOT

ROOT.gROOT.SetBatch(True)

TELESCOPE_DIR = Path(__file__).resolve().parent.parent
CORRY_BIN = os.environ.get("CORRY_BIN", "/home/hinata/package/corryvreckan/bin/corry")

sys.path.insert(0, str(TELESCOPE_DIR / "scripts" / "style"))
import plot_style as ps  # noqa: E402

ps.set_global_style()

DETECTORS = ["MALTA_0", "MALTA_1", "MALTA_2", "MALTA_3", "MALTA_4", "MALTA_5", "MALTA_6"]

# geometry chain: step -> (input geometry, output geometry), names of geometry/[<setup>/]<name>.conf
STEP_GEOMETRY = {
    "mask": ("init", "masked"),
    "prealign": ("masked", "prealigned"),
    "align": ("prealigned", "aligned"),
    "align_dut": ("aligned", "aligned_dut"),
    "analysis": ("aligned_dut", None),
}


def _read_ini_like(path: Path) -> dict[str, dict[str, str]]:
    """Minimal parser for corry's INI-like config/geometry files: returns
    {section_name: {key: value_without_quotes}}."""
    sections: dict[str, dict[str, str]] = {}
    current = None
    for raw_line in path.read_text().splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            sections[current] = {}
            continue
        if current is None or "=" not in line:
            continue
        key, _, value = line.partition("=")
        sections[current][key.strip()] = value.strip().strip('"')
    return sections


def geometry_path_for(config_path: Path) -> Path:
    """Resolve the detectors_file a corry config points at, relative to the
    config's own directory -- matching run_corry's cwd=config.parent."""
    sections = _read_ini_like(config_path)
    detectors_file = sections.get("Corryvreckan", {}).get("detectors_file")
    if detectors_file is None:
        raise ValueError(f"{config_path}: no detectors_file in [Corryvreckan]")
    return (config_path.parent / detectors_file).resolve()


def dut_from_geometry(geometry_path: Path) -> str:
    """Name of the detector section with role = "dut" in a geometry file."""
    sections = _read_ini_like(geometry_path)
    duts = [name for name, kv in sections.items() if kv.get("role", "").lower() == "dut"]
    if not duts:
        raise ValueError(f'{geometry_path}: no detector with role = "dut"')
    if len(duts) > 1:
        raise ValueError(f'{geometry_path}: multiple detectors with role = "dut": {duts}')
    return duts[0]


def resolve_dut(config_path: Path, requested_dut: str | None,
                geometry_path: Path | None = None) -> tuple[str, dict[str, str], dict[str, str]]:
    """Figure out the DUT for this step and what corry needs to agree with it.

    With requested_dut=None (--dut not passed), the DUT already baked into
    the geometry file this config points at is used as-is -- no overrides,
    this just prints which detector that is.

    With requested_dut given and different from the geometry's current DUT,
    this moves the "dut" role via -g overrides (corry writes detector-level
    config back out from the live Detector object's role, so this correctly
    carries forward into the next chained geometry/*.conf too) and, for
    configs that run Tracking4D, regenerates require_detectors so tracking
    excludes the new DUT instead of the old one.

    Returns (dut_name, o_overrides, g_overrides) -- merge o_overrides into
    the normal -o overrides dict and pass g_overrides to run_corry's -g.
    geometry_path is the geometry corry will actually read (default: the config's own)."""
    geometry_path = geometry_path or geometry_path_for(config_path)
    current_dut = dut_from_geometry(geometry_path)

    if requested_dut is None:
        print(f'DUT (from geometry, {geometry_path.name}): {current_dut}')
        return current_dut, {}, {}

    if requested_dut not in DETECTORS:
        raise SystemExit(f"--dut '{requested_dut}': not a known detector, choose from {DETECTORS}")

    if requested_dut == current_dut:
        print(f'DUT (from geometry, matches --dut): {current_dut}')
        return current_dut, {}, {}

    print(f'DUT override: {current_dut} (in {geometry_path.name}) -> {requested_dut}')
    g_overrides = {f"{current_dut}.role": "none", f"{requested_dut}.role": "dut"}

    o_overrides: dict[str, str] = {}
    if "Tracking4D" in _read_ini_like(config_path):
        reference_planes = [d for d in DETECTORS if d != requested_dut]
        o_overrides["Tracking4D.require_detectors"] = ",".join(reference_planes)

    return requested_dut, o_overrides, g_overrides


def base_arg_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("run_number", help="Run number, e.g. 1 (zero-padded to run_000001_*.root internally)")
    parser.add_argument("--data-dir", default=str(TELESCOPE_DIR / "data"),
                         help="Directory with run_<NNNNNN>_<plane>.root files (default: Telescope/data)")
    parser.add_argument("--events", type=int, default=None, help="Override number_of_events from the config file")
    parser.add_argument("--sim-data", action="store_true",
                         help="Data comes from the Malta2TreeWriter Allpix sim (no hardware group offset) "
                              "-- sets EventLoaderMALTA.real_data=false instead of the true beam-test default")
    parser.add_argument("--dut", default=None, choices=DETECTORS,
                         help="Override which detector is the DUT for this step (default: whatever the input "
                              "geometry file already has as role = \"dut\"). Moves the dut role via corry -g "
                              "overrides and regenerates Tracking4D.require_detectors to match; the change is "
                              "written into this step's output geometry, so later steps inherit it automatically "
                              "without needing --dut again.")
    parser.add_argument("--setup", default=None,
                        help="Use geometry/<SETUP>/ (starting from geometry/<SETUP>/init.conf) and "
                             "output/<SETUP>/run<N>/<step>/ instead of geometry/*.conf and output/<step>/, "
                             "so several telescope layouts can be analysed side by side")
    return parser


def step_dir(args, step: str) -> Path:
    """Where a step's corry histograms, log and summary plots go: output/<setup>/run<N>/<step>/
    with --setup (one directory per run, N = the run this step reads), else output/<step>/."""
    if args.setup:
        return TELESCOPE_DIR / "output" / args.setup / f"run{args.run_number}" / step
    return TELESCOPE_DIR / "output" / step


def geometry_file(args, name: str) -> Path:
    """geometry/[<setup>/]<name>.conf"""
    return TELESCOPE_DIR / "geometry" / (args.setup or "") / f"{name}.conf"


def setup_overrides(args, step: str, out_dir: Path) -> dict[str, str]:
    """With --setup, point this step's geometry chain and output_directory at the setup's own
    directories (the configs themselves keep the plain geometry/*.conf defaults). Without
    --setup this is empty, i.e. the configs run exactly as written."""
    if not args.setup:
        return {}
    setup_geo = TELESCOPE_DIR / "geometry" / args.setup
    if not (setup_geo / "init.conf").exists():
        raise SystemExit(f"--setup {args.setup}: {setup_geo}/init.conf not found "
                         f"(copy geometry/template/ to geometry/{args.setup}/ first)")
    geo_in, geo_out = STEP_GEOMETRY[step]
    overrides = {"detectors_file": str(geometry_file(args, geo_in)), "output_directory": str(out_dir)}
    if geo_out:
        overrides["detectors_file_updated"] = str(geometry_file(args, geo_out))
    return overrides


def standard_overrides(args) -> dict[str, str]:
    """The -o overrides every step script needs from base_arg_parser's args.

    NOTE: a truly global [Corryvreckan] option (like number_of_events) must
    be passed unprefixed ("number_of_events=...") -- corry's OptionParser
    treats anything before a '.' as a module/detector identifier to match,
    and "Corryvreckan" is not a module, so "Corryvreckan.number_of_events"
    silently matches nothing and is dropped.
    """
    overrides = {
        "EventLoaderMALTA.run_number": args.run_number,
        "EventLoaderMALTA.base_path": str(Path(args.data_dir).resolve()),
    }
    if args.events is not None:
        overrides["number_of_events"] = str(args.events)
    if args.sim_data:
        overrides["EventLoaderMALTA.real_data"] = "false"
    return overrides


def run_corry(config: Path, overrides: dict[str, str], log_path: Path, dut: str | None = None) -> str:
    """Run corry with the given config and -o overrides, tee'd to log_path.

    dut is the --dut CLI value (None unless the user overrides it); the
    resolved DUT name for this run is returned so the caller can use it
    for plot labels/histogram paths instead of a hardcoded constant."""
    geometry = Path(overrides["detectors_file"]) if "detectors_file" in overrides else None
    resolved_dut, dut_o_overrides, dut_g_overrides = resolve_dut(config, dut, geometry)

    cmd = [CORRY_BIN, "-c", str(config)]
    for key, value in {**overrides, **dut_o_overrides}.items():
        if value is not None:
            cmd += ["-o", f"{key}={value}"]
    for key, value in dut_g_overrides.items():
        cmd += ["-g", f"{key}={value}"]

    print("+ " + " ".join(cmd))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    wrote_histograms = finished = False
    with open(log_path, "w") as log_file, subprocess.Popen(
        cmd, cwd=config.parent, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    ) as proc:
        for line in proc.stdout:
            print(line, end="")
            log_file.write(line)
            wrote_histograms |= "Wrote histogram output file" in line
            finished |= "Wall-clock timing" in line
    if proc.returncode != 0:
        # corry occasionally aborts in its teardown ("double free or corruption") after the
        # run is complete: histograms and the updated geometry are already written and the
        # final timing table printed. Rerunning the same step then passes, so keep the output.
        if wrote_histograms and finished:
            print(f"[warn] corry exited with {proc.returncode} AFTER finishing the run "
                  f"(crash at teardown) -- output kept, continuing")
        else:
            raise subprocess.CalledProcessError(proc.returncode, cmd)
    print(f"(corry log saved to {log_path})")
    return resolved_dut


def get_hist(root_file, path: str):
    """Fetch a histogram by path, returning None (with a warning) if missing."""
    obj = root_file.Get(path)
    if not obj:
        print(f"  [warn] histogram not found: {path}")
        return None
    return obj


def fit_gaussian(hist, n_sigma=2.5, options="QR"):
    """Fit a Gaussian around a 1D histogram's peak (mean +/- n_sigma*RMS as
    the fit window) and leave the function attached to the histogram so it
    is drawn along with it. Returns a dict of mean/sigma (+ errors) and the
    TF1, or None if the histogram is empty."""
    if hist is None or hist.GetEntries() == 0:
        return None
    mean0, rms0 = hist.GetMean(), hist.GetRMS()
    if rms0 <= 0:
        rms0 = hist.GetXaxis().GetBinWidth(1) * 5
    lo, hi = mean0 - n_sigma * rms0, mean0 + n_sigma * rms0
    func = ROOT.TF1(f"f_{hist.GetName()}_gaus", "gaus", lo, hi)
    func.SetLineWidth(2)
    hist.Fit(func, options, "", lo, hi)
    return {
        "mean": func.GetParameter(1),
        "mean_err": func.GetParError(1),
        "sigma": func.GetParameter(2),
        "sigma_err": func.GetParError(2),
        "func": func,
    }


def make_grid_canvas(name: str, ncols: int, nrows: int, width=2000, height=1000):
    """Plain TCanvas::Divide grid for one-pad-per-detector summaries; the
    house style (fonts/colors/no stat box) still applies via set_global_style()."""
    canvas = ROOT.TCanvas(name, name, width, height)
    canvas.Divide(ncols, nrows)
    return canvas


def save(canvas, outdir: Path, basename: str):
    """Save both PDF and PNG via the house style's save(), returns the PNG path."""
    _, png_path = ps.save(canvas, str(outdir), basename)
    return Path(png_path)
