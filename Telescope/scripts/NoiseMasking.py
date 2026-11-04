#!/usr/bin/env python3
"""Step 1: run corry's MaskCreator and show an occupancy/mask summary.

    ../.venv/bin/python3 NoiseMasking.py 1 --data-dir ../data --sim-data
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import plot_style as ps
import ROOT

CONFIG = common.TELESCOPE_DIR / "config" / "mask.conf"


def main():
    args = common.base_arg_parser("Run corry MaskCreator (noise/dead pixel masking)").parse_args()

    overrides = common.standard_overrides(args)
    out_dir = common.step_dir(args, "mask")
    overrides.update(common.setup_overrides(args, "mask", out_dir))

    log_path = out_dir / f"run{args.run_number}_corry.log"
    common.run_corry(CONFIG, overrides, log_path, dut=args.dut)

    root_path = out_dir / "mask.root"
    f = ROOT.TFile.Open(str(root_path))

    canvas = common.make_grid_canvas(f"c_mask_run{args.run_number}", 4, 2)
    keepalive = []
    for i, det in enumerate(common.DETECTORS, start=1):
        pad = canvas.cd(i)
        pad.SetRightMargin(0.16)
        pad.SetLeftMargin(0.12)

        occupancy = common.get_hist(f, f"MaskCreator/{det}/occupancy")
        maskmap = common.get_hist(f, f"MaskCreator/{det}/maskmap")
        if occupancy is None:
            continue
        n_masked = int(maskmap.GetEntries()) if maskmap else -1

        occupancy.GetXaxis().SetTitle("column")
        occupancy.GetYaxis().SetTitle("row")
        ps.style_axis_font43(occupancy.GetXaxis(), title_size=16, title_offset=2.2, label_size=13)
        ps.style_axis_font43(occupancy.GetYaxis(), title_size=16, title_offset=1.6, label_size=13)
        occupancy.Draw("COLZ")

        # These occupancy maps have a genuinely empty (zero-content, i.e.
        # white) region outside the beam spot -- unlike a typical COLZ map
        # that's colored everywhere, so black text (not white) is what
        # stays legible in the emptiest corner.
        corner = ps.pick_label_corner_2d(occupancy)
        label = ps.draw_corner_label(
            pad, [det, f"masked: {n_masked}"], corner=corner,
            header_size=0.065, body_size=0.055, dy=0.09, color=ROOT.kBlack,
        )
        keepalive.append((occupancy, maskmap, label))

    canvas.cd(0)
    png_path = common.save(canvas, out_dir, f"run{args.run_number}_summary")
    print(f"\nUpdated geometry written to: {common.geometry_file(args, 'masked')}")
    print(f"Summary: {png_path}")


if __name__ == "__main__":
    main()
