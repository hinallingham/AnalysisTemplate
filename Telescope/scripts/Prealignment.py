#!/usr/bin/env python3
"""Step 2: run corry's Prealignment, fit a Gaussian to each plane's X/Y
correlation peak and show the resulting shift.

    ../.venv/bin/python3 Prealignment.py 1 --data-dir ../data --sim-data
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import plot_style as ps
import ROOT

CONFIG = common.TELESCOPE_DIR / "config" / "prealign.conf"


def main():
    args = common.base_arg_parser("Run corry Prealignment (coarse X/Y shifts from correlations)").parse_args()

    overrides = common.standard_overrides(args)
    out_dir = common.step_dir(args, "prealign")
    overrides.update(common.setup_overrides(args, "prealign", out_dir))

    log_path = out_dir / f"run{args.run_number}_corry.log"
    dut = common.run_corry(CONFIG, overrides, log_path, dut=args.dut)

    root_path = out_dir / "prealign.root"
    f = ROOT.TFile.Open(str(root_path))

    canvas = common.make_grid_canvas(f"c_prealign_run{args.run_number}", 4, 2)
    keepalive = []
    for i, det in enumerate(common.DETECTORS, start=1):
        pad = canvas.cd(i)
        pad.SetLeftMargin(0.13)

        hx = common.get_hist(f, f"Prealignment/{det}/correlationX")
        hy = common.get_hist(f, f"Prealignment/{det}/correlationY")
        if hx is None or hy is None:
            continue

        hx.SetLineColor(ROOT.kBlue + 2)
        hx.SetLineWidth(2)
        hx.GetXaxis().SetTitle("residual [mm]")
        hx.GetYaxis().SetTitle("clusters")
        ps.style_axis_font43(hx.GetXaxis(), title_size=16, title_offset=2.4, label_size=13)
        ps.style_axis_font43(hx.GetYaxis(), title_size=16, title_offset=1.8, label_size=13)

        fit_x = common.fit_gaussian(hx)
        fit_y = common.fit_gaussian(hy)

        # Zoom the x-axis in on the peak -- the default +/-10mm correlation
        # range makes a sub-mm shift invisible otherwise.
        centers = [d["mean"] for d in (fit_x, fit_y) if d]
        widths = [d["sigma"] for d in (fit_x, fit_y) if d]
        if centers and widths:
            center = sum(centers) / len(centers)
            half_window = max(8 * max(widths), 0.3)
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

        tag = " (fixed)" if det == dut else ""
        lines = [det + tag]
        if fit_x:
            lines.append(f"X = {fit_x['mean']:.3f} #pm {fit_x['mean_err']:.3f} mm")
        if fit_y:
            lines.append(f"Y = {fit_y['mean']:.3f} #pm {fit_y['mean_err']:.3f} mm")
        corner = ps.pick_label_corner(hx)
        label = ps.draw_corner_label(pad, lines, corner=corner, header_size=0.065, body_size=0.055, dy=0.09)

        keepalive.append((hx, hy, fit_x, fit_y, label))

        if fit_x:
            print(f"{det}: X shift = {fit_x['mean']:+.4f} +/- {fit_x['mean_err']:.4f} mm "
                  f"(sigma {fit_x['sigma']:.4f} mm)")
        if fit_y:
            print(f"{det}: Y shift = {fit_y['mean']:+.4f} +/- {fit_y['mean_err']:.4f} mm "
                  f"(sigma {fit_y['sigma']:.4f} mm)")

    canvas.cd(0)
    png_path = common.save(canvas, out_dir, f"run{args.run_number}_summary")
    print(f"\nUpdated geometry written to: {common.geometry_file(args, 'prealigned')}")
    print(f"Summary: {png_path}")


if __name__ == "__main__":
    main()
