#!/usr/bin/env python3
"""Step 3: run corry's Tracking4D + AlignmentMillepede and show the track
chi2/ndof as a quick fit-quality check (DUT excluded from tracking/
alignment). The reference-plane and DUT residual confirmation plots have
moved to run_analysis.py, which shows them for the final aligned_dut
geometry instead of the intermediate one produced here.

    ../.venv/bin/python3 Alignment.py 1 --data-dir ../data --sim-data
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import plot_style as ps
import ROOT

CONFIG = common.TELESCOPE_DIR / "config" / "align.conf"


def main():
    args = common.base_arg_parser("Run corry Tracking4D + AlignmentMillepede").parse_args()

    overrides = common.standard_overrides(args)
    out_dir = common.step_dir(args, "align")
    overrides.update(common.setup_overrides(args, "align", out_dir))

    log_path = out_dir / f"run{args.run_number}_corry.log"
    dut = common.run_corry(CONFIG, overrides, log_path, dut=args.dut)

    root_path = out_dir / "align.root"
    f = ROOT.TFile.Open(str(root_path))

    canvas = ROOT.TCanvas(f"c_align_run{args.run_number}", "align", 900, 700)
    keepalive = []

    chi2 = common.get_hist(f, "Tracking4D/trackChi2ndof")
    if chi2 is not None:
        chi2.SetLineColor(ROOT.kBlue + 2)
        chi2.SetLineWidth(2)
        chi2.GetXaxis().SetTitle("#chi^{2}/ndof")
        chi2.GetYaxis().SetTitle("tracks")
        ps.style_axis_font43(chi2.GetXaxis(), title_size=20, title_offset=1.6, label_size=17)
        ps.style_axis_font43(chi2.GetYaxis(), title_size=20, title_offset=1.4, label_size=17)
        chi2.Draw("HIST")
        label = ps.draw_corner_label(canvas, ["trackChi2ndof", f"mean = {chi2.GetMean():.2f}"],
                                      corner="top-right", header_size=0.045, body_size=0.038)
        keepalive.append((chi2, label))

    canvas.cd(0)
    png_path = common.save(canvas, out_dir, f"run{args.run_number}_summary")

    print(f"\nUpdated geometry written to: {common.geometry_file(args, 'aligned')}")
    print(f"Telescope (RP) alignment only -- run AlignmentDUT.py next to fine-tune {dut}.")
    print("Residual confirmation plots are produced by run_analysis.py against the final geometry.")
    print(f"Summary: {png_path}")


if __name__ == "__main__":
    main()
