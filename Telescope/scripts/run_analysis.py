#!/usr/bin/env python3
"""Main analysis skeleton: runs config/analysis.conf against the fully
aligned geometry and shows the DUT (MALTA_3) efficiency as a first look.

Extend this (and config/analysis.conf) as the actual analysis grows --
this is deliberately the thinnest of the four scripts.

    ../.venv/bin/python3 run_analysis.py 1 --data-dir ../data --sim-data
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import plot_style as ps
import ROOT

CONFIG = common.TELESCOPE_DIR / "config" / "analysis.conf"


def main():
    args = common.base_arg_parser("Run the main corry analysis chain").parse_args()

    overrides = common.standard_overrides(args)

    log_path = common.TELESCOPE_DIR / "output" / "analysis" / f"run{args.run_number}_corry.log"
    common.run_corry(CONFIG, overrides, log_path)

    root_path = common.TELESCOPE_DIR / "output" / "analysis" / "analysis.root"
    f = ROOT.TFile.Open(str(root_path))

    canvas = ROOT.TCanvas(f"c_analysis_run{args.run_number}", "analysis", 1400, 650)
    canvas.Divide(2, 1)
    keepalive = []

    pad = canvas.cd(1)
    pad.SetRightMargin(0.16)
    emap = common.get_hist(f, f"AnalysisEfficiency/{common.DUT}/chipEfficiencyMap_trackPos")
    if emap is not None:
        h2 = emap.GetTotalHistogram()
        h2.GetXaxis().SetTitle("column")
        h2.GetYaxis().SetTitle("row")
        ps.style_axis_font43(h2.GetXaxis(), title_size=16, title_offset=2.2, label_size=13)
        ps.style_axis_font43(h2.GetYaxis(), title_size=16, title_offset=1.8, label_size=13)
        emap.Draw("COLZ")
        corner = ps.pick_label_corner_2d(h2)
        label = ps.draw_corner_label(pad, [f"{common.DUT} chip efficiency"],
                                      corner=corner, header_size=0.045, color=ROOT.kBlack)
        keepalive.append((emap, h2, label))

    pad = canvas.cd(2)
    etot = common.get_hist(f, f"AnalysisEfficiency/{common.DUT}/eTotalEfficiency")
    if etot is not None:
        eff = etot.GetEfficiency(1)
        lo = etot.GetEfficiencyErrorLow(1)
        hi = etot.GetEfficiencyErrorUp(1)
        text = ROOT.TLatex()
        text.SetNDC()
        text.SetTextAlign(22)
        text.SetTextFont(62)
        text.SetTextSize(0.09)
        text.DrawLatex(0.5, 0.55, f"{eff * 100:.2f} %")
        sub = ROOT.TLatex()
        sub.SetNDC()
        sub.SetTextAlign(22)
        sub.SetTextFont(42)
        sub.SetTextSize(0.045)
        sub.DrawLatex(0.5, 0.42, f"+{hi*100:.2f} / -{lo*100:.2f} %")
        title = ROOT.TLatex()
        title.SetNDC()
        title.SetTextAlign(22)
        title.SetTextFont(62)
        title.SetTextSize(0.05)
        title.DrawLatex(0.5, 0.75, f"{common.DUT} total efficiency")
        keepalive.append((text, sub, title))
        print(f"{common.DUT} total efficiency: {eff*100:.2f} % (+{hi*100:.2f}/-{lo*100:.2f})")

    canvas.cd(0)
    png_path = common.save(canvas, common.TELESCOPE_DIR / "output" / "analysis", f"run{args.run_number}_summary")
    print(f"Summary: {png_path}")


if __name__ == "__main__":
    main()
