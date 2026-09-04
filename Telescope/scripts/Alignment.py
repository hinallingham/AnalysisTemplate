#!/usr/bin/env python3
"""Step 3: run corry's Tracking4D + AlignmentMillepede and show track
chi2/ndof plus a Gaussian fit of the global residuals on each reference
plane (DUT excluded from tracking/alignment).

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

    log_path = common.TELESCOPE_DIR / "output" / "align" / f"run{args.run_number}_corry.log"
    common.run_corry(CONFIG, overrides, log_path)

    root_path = common.TELESCOPE_DIR / "output" / "align" / "align.root"
    f = ROOT.TFile.Open(str(root_path))

    reference_planes = [d for d in common.DETECTORS if d != common.DUT]

    canvas = common.make_grid_canvas(f"c_align_run{args.run_number}", 4, 2)
    keepalive = []

    pad = canvas.cd(1)
    chi2 = common.get_hist(f, "Tracking4D/trackChi2ndof")
    if chi2 is not None:
        chi2.SetLineColor(ROOT.kBlue + 2)
        chi2.SetLineWidth(2)
        chi2.GetXaxis().SetTitle("#chi^{2}/ndof")
        chi2.GetYaxis().SetTitle("tracks")
        ps.style_axis_font43(chi2.GetXaxis(), title_size=16, title_offset=2.4, label_size=13)
        ps.style_axis_font43(chi2.GetYaxis(), title_size=16, title_offset=1.8, label_size=13)
        chi2.Draw("HIST")
        label = ps.draw_corner_label(pad, ["trackChi2ndof", f"mean = {chi2.GetMean():.2f}"],
                                      corner="top-right", header_size=0.06, body_size=0.05)
        keepalive.append((chi2, label))

    for i, det in enumerate(reference_planes, start=2):
        pad = canvas.cd(i)
        pad.SetLeftMargin(0.13)

        hx = common.get_hist(f, f"Tracking4D/{det}/global_residuals/GlobalResidualsX")
        hy = common.get_hist(f, f"Tracking4D/{det}/global_residuals/GlobalResidualsY")
        if hx is None or hy is None:
            continue

        hx.SetLineColor(ROOT.kBlue + 2)
        hx.SetLineWidth(2)
        hx.GetXaxis().SetTitle("residual [mm]")
        hx.GetYaxis().SetTitle("tracks")
        ps.style_axis_font43(hx.GetXaxis(), title_size=16, title_offset=2.4, label_size=13)
        ps.style_axis_font43(hx.GetYaxis(), title_size=16, title_offset=1.8, label_size=13)

        fit_x = common.fit_gaussian(hx)
        fit_y = common.fit_gaussian(hy)

        centers = [d["mean"] for d in (fit_x, fit_y) if d]
        widths = [d["sigma"] for d in (fit_x, fit_y) if d]
        if centers and widths:
            center = sum(centers) / len(centers)
            half_window = max(8 * max(widths), 0.05)
            hx.GetXaxis().SetRangeUser(center - half_window, center + half_window)

        hx.Draw("HIST")
        if fit_x:
            fit_x["func"].SetLineColor(ROOT.kRed + 1)
            fit_x["func"].SetLineStyle(1)
            fit_x["func"].Draw("same")

        hy.SetLineColor(ROOT.kGreen + 2)
        hy.SetLineWidth(2)
        hy.Draw("HIST same")
        if fit_y:
            fit_y["func"].SetLineColor(ROOT.kRed + 1)
            fit_y["func"].SetLineStyle(2)
            fit_y["func"].Draw("same")

        lines = [det]
        if fit_x:
            lines.append(f"#sigma_{{x}} = {fit_x['sigma']*1000:.1f} #pm {fit_x['sigma_err']*1000:.1f} #mum")
        if fit_y:
            lines.append(f"#sigma_{{y}} = {fit_y['sigma']*1000:.1f} #pm {fit_y['sigma_err']*1000:.1f} #mum")
        corner = ps.pick_label_corner(hx)
        label = ps.draw_corner_label(pad, lines, corner=corner, header_size=0.065, body_size=0.055, dy=0.09)

        keepalive.append((hx, hy, fit_x, fit_y, label))

        if fit_x:
            print(f"{det}: X residual mean {fit_x['mean']*1000:+.1f} um, sigma {fit_x['sigma']*1000:.1f} um")
        if fit_y:
            print(f"{det}: Y residual mean {fit_y['mean']*1000:+.1f} um, sigma {fit_y['sigma']*1000:.1f} um")

    canvas.cd(0)
    png_path = common.save(canvas, common.TELESCOPE_DIR / "output" / "align", f"run{args.run_number}_summary")

    print(f"\nUpdated geometry written to: {common.TELESCOPE_DIR / 'geometry' / 'aligned.conf'}")
    print(f"Telescope (RP) alignment only -- run AlignmentDUT.py next to fine-tune {common.DUT}.")
    print(f"Summary: {png_path}")


if __name__ == "__main__":
    main()
