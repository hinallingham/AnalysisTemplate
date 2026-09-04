#!/usr/bin/env python3
"""Step 4: run corry's AlignmentDUTResidual to fine-tune the DUT (MALTA_3)
on top of the already-Millepede-aligned reference planes. Shows the final
unbiased residuals (with a Gaussian fit) and the per-iteration convergence
of the DUT's translation/rotation corrections.

Run Alignment.py first -- this step reads geometry/aligned.conf.

    ../.venv/bin/python3 AlignmentDUT.py 1 --data-dir ../data --sim-data
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import plot_style as ps
import ROOT

CONFIG = common.TELESCOPE_DIR / "config" / "align_dut.conf"


def find_object(directory, prefix):
    """First object in a TDirectory whose key name starts with prefix."""
    if directory is None:
        return None
    for key in directory.GetListOfKeys():
        if key.GetName().startswith(prefix):
            return key.ReadObj()
    return None


def find_module_dir(root_file, module, det):
    """AlignmentDUTResidual is a DUT-type module -- try the per-detector
    subdirectory first (the usual corry convention), fall back to the
    module's top-level directory (single DUT instance) if that's empty."""
    d = root_file.Get(f"{module}/{det}")
    if d:
        return d
    return root_file.Get(module)


def draw_convergence(pad, graph, title):
    if graph is None:
        pad.SetVisible(False)
        return
    graph.SetMarkerStyle(20)
    graph.SetMarkerColor(ROOT.kBlue + 2)
    graph.SetLineColor(ROOT.kBlue + 2)
    graph.SetLineWidth(2)
    graph.GetXaxis().SetTitle("iteration")
    ps.style_axis_font43(graph.GetXaxis(), title_size=16, title_offset=2.4, label_size=13)
    ps.style_axis_font43(graph.GetYaxis(), title_size=16, title_offset=1.8, label_size=13)
    graph.Draw("APL")
    label = ps.draw_corner_label(pad, [title], corner="top-right", header_size=0.06)
    return label


def main():
    args = common.base_arg_parser("Run corry AlignmentDUTResidual (fine-tune the DUT)").parse_args()

    overrides = common.standard_overrides(args)

    log_path = common.TELESCOPE_DIR / "output" / "align_dut" / f"run{args.run_number}_corry.log"
    common.run_corry(CONFIG, overrides, log_path)

    root_path = common.TELESCOPE_DIR / "output" / "align_dut" / "align_dut.root"
    f = ROOT.TFile.Open(str(root_path))
    mod_dir = find_module_dir(f, "AlignmentDUTResidual", common.DUT)

    canvas = common.make_grid_canvas(f"c_align_dut_run{args.run_number}", 4, 2)
    keepalive = []

    # --- residual histograms (final, unbiased) with a Gaussian fit -------
    for i, (hist_name, axis_label) in enumerate([("residualsX", "x"), ("residualsY", "y")], start=1):
        pad = canvas.cd(i)
        pad.SetLeftMargin(0.14)
        h = find_object(mod_dir, hist_name)
        if h is None:
            print(f"  [warn] histogram not found: AlignmentDUTResidual/.../{hist_name}")
            continue
        h.SetLineColor(ROOT.kBlue + 2)
        h.SetLineWidth(2)
        h.GetXaxis().SetTitle(f"{axis_label}_{{track}} - {axis_label} [#mum]")
        h.GetYaxis().SetTitle("associated clusters")
        ps.style_axis_font43(h.GetXaxis(), title_size=16, title_offset=2.4, label_size=13)
        ps.style_axis_font43(h.GetYaxis(), title_size=16, title_offset=1.8, label_size=13)
        h.Draw("HIST")
        fit = common.fit_gaussian(h)
        if fit:
            fit["func"].SetLineColor(ROOT.kRed + 1)
            fit["func"].Draw("same")
            center = fit["mean"]
            half_window = max(8 * fit["sigma"], 20)
            h.GetXaxis().SetRangeUser(center - half_window, center + half_window)
            lines = [common.DUT, f"mean = {fit['mean']:.2f} #pm {fit['mean_err']:.2f} #mum",
                     f"sigma = {fit['sigma']:.2f} #pm {fit['sigma_err']:.2f} #mum"]
            corner = ps.pick_label_corner(h)
            label = ps.draw_corner_label(pad, lines, corner=corner, header_size=0.06, body_size=0.05, dy=0.09)
            keepalive.append(label)
            print(f"{common.DUT}: {axis_label} residual mean {fit['mean']:+.2f} um, sigma {fit['sigma']:.2f} um")
        keepalive.append((h, fit))

    # --- per-iteration convergence graphs ---------------------------------
    graph_specs = [
        ("alignment_correction_displacementX_", "shift X [#mum]"),
        ("alignment_correction_displacementY_", "shift Y [#mum]"),
        ("alignment_correction_rotation0_", "rot 0 [deg]"),
        ("alignment_correction_rotation1_", "rot 1 [deg]"),
        ("alignment_correction_rotation2_", "rot 2 [deg]"),
    ]
    for i, (prefix, title) in enumerate(graph_specs, start=3):
        pad = canvas.cd(i)
        pad.SetLeftMargin(0.16)
        graph = find_object(mod_dir, prefix)
        label = draw_convergence(pad, graph, title)
        keepalive.append((graph, label))

    canvas.cd(0)
    png_path = common.save(canvas, common.TELESCOPE_DIR / "output" / "align_dut", f"run{args.run_number}_summary")

    print(f"\nUpdated geometry written to: {common.TELESCOPE_DIR / 'geometry' / 'aligned_dut.conf'}")
    print("This is the final geometry -- config/analysis.conf reads from it.")
    print(f"Summary: {png_path}")


if __name__ == "__main__":
    main()
