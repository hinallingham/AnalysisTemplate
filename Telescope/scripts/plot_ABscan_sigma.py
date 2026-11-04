#!/usr/bin/env python3
"""DUT residual width vs A = B for one or more ABscans (C fixed per scan): Gaussian-fit
sigma of the AnalysisDUT global residuals of MALTA_3, 6-plane tracking vs upstream-3
tracking. With one C, x and y share one pad; with several C, x and y get a pad each and
the C values are overlaid in both.

Reads output/ABscan_C<C>/run<NNN>/{analysis,analysis_upstream3}/*.root as written by
scripts/run_ABscan.sh. The fit is the same as in run_analysis.py (common.fit_gaussian,
window mean +/- 2.5 RMS), so the numbers match the per-run residual plots.

    ../.venv/bin/python3 plot_ABscan_sigma.py --c 1.5
    ../.venv/bin/python3 plot_ABscan_sigma.py --c 1.5 5

Output (PDF + PNG + JSON with the numbers):
    /home/hinata/output/plot/MALTA2/simulation_analyze/residual/ABscan_C<C>[_C<C2>...]_dut_sigma_vs_AB.*
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

# The shared house style from the root-plot-polish skill; imported first so that
# common.py (which does "import plot_style" from scripts/style/) reuses this, newer copy.
sys.path.insert(0, "/home/hinata/.claude/skills/root-plot-polish/scripts/style")
import plot_style as ps  # noqa: E402

sys.path.insert(1, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import ROOT  # noqa: E402

GEN = "/home/hinata/MALTA2/Telescope/sim/config/ABscan_generate_configs.py"
OUT_DIR = Path("/home/hinata/output/plot/MALTA2/simulation_analyze/residual")
DUT = "MALTA_3"

# (key, result dir, legend label, color)
TRACKINGS = [
    ("6plane", "analysis", "6-plane tracking (RP1-6)", ROOT.kBlue + 2),
    ("upstream3", "analysis_upstream3", "upstream 3-plane tracking (RP1-3)", ROOT.kRed + 1),
]
AXES = ["X", "Y"]
# second-dataset convention: closed/solid = first, open/dashed = second
STYLES = [(20, 1), (24, 2), (21, 3), (25, 4)]  # (marker, line style) per C, or per axis for one C


def scan_name(c):
    return f"ABscan_C{c:g}".replace(".", "p")


def run_table(c):
    """[(run, s_cm)] for this C, from the same generator the simulation used."""
    out = subprocess.run([sys.executable, GEN, "--c", str(c), "--list-runs"],
                         check=True, capture_output=True, text=True).stdout
    return [(int(f[1]), float(f[2])) for f in (line.split() for line in out.splitlines())]


def dut_sigma(root_path, axis):
    f = ROOT.TFile.Open(str(root_path))
    h = f.Get(f"AnalysisDUT/{DUT}/global_residuals/residuals{axis}")
    fit = common.fit_gaussian(h) if h else None
    result = None if fit is None else {k: fit[k] for k in ("mean", "mean_err", "sigma", "sigma_err")}
    f.Close()
    return result


def collect(c):
    """values[tracking][axis] = [{s_cm, run, mean, sigma, ...}] for one scan."""
    scan_dir = common.TELESCOPE_DIR / "output" / scan_name(c)
    values = {}
    for key, subdir, _, _ in TRACKINGS:
        values[key] = {axis: [] for axis in AXES}
        for run, s in run_table(c):
            root_path = scan_dir / f"run{run:03d}" / subdir / f"{subdir}.root"
            if not root_path.exists():
                print(f"  [warn] missing {root_path}, skipped")
                continue
            for axis in AXES:
                fit = dut_sigma(root_path, axis)
                if fit:
                    values[key][axis].append({"s_cm": s, "run": run, **fit})
    return values


def make_graph(pts, color, marker, line_style):
    g = ROOT.TGraphErrors(len(pts))
    for i, p in enumerate(pts):
        g.SetPoint(i, p["s_cm"], p["sigma"])
        g.SetPointError(i, 0.0, p["sigma_err"])
    g.SetMarkerStyle(marker)
    g.SetMarkerSize(1.3)
    g.SetMarkerColor(color)
    g.SetLineColor(color)
    g.SetLineStyle(line_style)
    g.SetLineWidth(2)
    return g


def draw_pad(pad, series, xmax, ymax, header, sub, legend_size, legend_box):
    """series = [(graph, legend text)] drawn into one pad, house-style frame + label + legend
    (legend_box = x1, y1, x2, y2 in NDC)."""
    pad.cd()
    pad.SetMargin(0.13, 0.05, 0.13, 0.05)
    pad.SetGridy()
    frame = pad.DrawFrame(0.0, 0.0, xmax, ymax)
    frame.GetXaxis().SetTitle("A = B [cm]")
    frame.GetYaxis().SetTitle("DUT residual #sigma_{Gauss} [#mum]")
    ps.style_axis_font43(frame.GetXaxis(), title_size=22, title_offset=1.3, label_size=19)
    ps.style_axis_font43(frame.GetYaxis(), title_size=22, title_offset=1.4, label_size=19)
    for g, _ in series:
        g.Draw("PL same")
    graphs = [g for g, _ in series]
    corner = ps.pick_label_corner_graph(graphs, candidates=("top-left", "top-right"))
    label = ps.draw_corner_label(pad, [header, sub], corner=corner, header_size=0.040, body_size=0.034)
    legend = ps.make_clean_legend(*legend_box, text_size=legend_size)
    for g, text in series:
        legend.AddEntry(g, text, "pl")
    legend.Draw()
    return frame, label, legend


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--c", type=float, nargs="+", default=[1.5], help="C [cm] of the scan(s) (default 1.5)")
    args = ap.parse_args()

    values = {c: collect(c) for c in args.c}
    all_pts = [p for c in values for k in values[c] for a in values[c][k] for p in values[c][k][a]]
    xmax = max(p["s_cm"] for p in all_pts) * 1.08
    ymax = max(p["sigma"] for p in all_pts) * (1.45 if len(args.c) == 1 else 1.6)
    header = "MALTA2 telescope, Allpix^{2} simulation"

    ps.set_global_style()
    keep = []
    if len(args.c) == 1:
        c = args.c[0]
        canvas = ROOT.TCanvas("c_sigma_vs_AB", "", 900, 650)
        series = []
        for key, _, label, color in TRACKINGS:
            for axis, (marker, line_style) in zip(AXES, STYLES):
                series.append((make_graph(values[c][key][axis], color, marker, line_style),
                               f"{label}, {axis.lower()}"))
        keep += series
        # sigma never drops far below the single-pixel binary limit (36.4um/sqrt(12) = 10.5um),
        # so the bottom of the frame stays free for the legend
        keep.append(draw_pad(canvas, series, xmax, ymax, header,
                             f"3 GeV e^{{-}}, C = {c:g} cm, DUT = {DUT}", 0.030, (0.50, 0.17, 0.94, 0.40)))
    else:
        canvas = ROOT.TCanvas("c_sigma_vs_AB", "", 1700, 650)
        canvas.Divide(2, 1)
        for i, axis in enumerate(AXES, start=1):
            series = []
            for key, _, label, color in TRACKINGS:
                for c, (marker, line_style) in zip(args.c, STYLES):
                    series.append((make_graph(values[c][key][axis], color, marker, line_style),
                                   f"{label.split(' tracking')[0]} {label.split('tracking ')[1]}, C = {c:g} cm"))
            keep += series
            # the larger C pushes the upstream curve up at small A=B only: the upper right,
            # under the label, is the free area here
            keep.append(draw_pad(canvas.cd(i), series, xmax, ymax, header,
                                 f"3 GeV e^{{-}}, DUT = {DUT}, residual {axis.lower()}", 0.033,
                                 (0.40, 0.50, 0.94, 0.76)))
    canvas.cd(0)

    basename = "_".join(scan_name(c) for c in args.c).replace("_ABscan", "") + "_dut_sigma_vs_AB"
    _, png = ps.save(canvas, str(OUT_DIR), basename)
    with open(OUT_DIR / f"{basename}.json", "w") as f:
        json.dump({"scans": {scan_name(c): {"c_cm": c, "values": values[c]} for c in args.c}, "dut": DUT,
                   "fit": "gaus, window mean +/- 2.5 RMS (common.fit_gaussian)"}, f, indent=1)

    for c in args.c:
        print(f"\nC = {c:g} cm\n{'A=B [cm]':>8}  " + "  ".join(f"{k}_{a.lower()} [um]" for k, *_ in TRACKINGS for a in AXES))
        for run, s in run_table(c):
            row = []
            for key, *_ in TRACKINGS:
                for axis in AXES:
                    p = next((p for p in values[c][key][axis] if p["run"] == run), None)
                    row.append(f"{p['sigma']:6.2f}+-{p['sigma_err']:.2f}" if p else "   ---   ")
            print(f"{s:8g}  " + "  ".join(f"{r:>17}" for r in row))
    print(f"Plot: {png}")


if __name__ == "__main__":
    main()
