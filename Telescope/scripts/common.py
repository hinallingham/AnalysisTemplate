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
DUT = "MALTA_3"


def base_arg_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("run_number", help="Run number, e.g. 1 (zero-padded to run_000001_*.root internally)")
    parser.add_argument("--data-dir", default=str(TELESCOPE_DIR / "data"),
                         help="Directory with run_<NNNNNN>_<plane>.root files (default: Telescope/data)")
    parser.add_argument("--events", type=int, default=None, help="Override number_of_events from the config file")
    parser.add_argument("--sim-data", action="store_true",
                         help="Data comes from the Malta2TreeWriter Allpix sim (no hardware group offset) "
                              "-- sets EventLoaderMALTA.real_data=false instead of the true beam-test default")
    return parser


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


def run_corry(config: Path, overrides: dict[str, str], log_path: Path) -> None:
    """Run corry with the given config and -o overrides, tee'd to log_path."""
    cmd = [CORRY_BIN, "-c", str(config)]
    for key, value in overrides.items():
        if value is not None:
            cmd += ["-o", f"{key}={value}"]

    print("+ " + " ".join(cmd))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w") as log_file, subprocess.Popen(
        cmd, cwd=config.parent, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    ) as proc:
        for line in proc.stdout:
            print(line, end="")
            log_file.write(line)
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    print(f"(corry log saved to {log_path})")


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
