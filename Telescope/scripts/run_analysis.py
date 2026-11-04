#!/usr/bin/env python3
"""Main analysis skeleton: runs config/analysis.conf against the fully
aligned geometry, shows the DUT (MALTA_3) efficiency as a first look, and
the residual confirmation plots (reference-plane global residuals from
Tracking4D plus the DUT's own residuals from AnalysisDUT) that used to be
shown during Alignment.py / AlignmentDUT.py -- now against the final
aligned_dut geometry instead of the intermediate alignment-step ones.

Extend this (and config/analysis.conf) as the actual analysis grows --
this is deliberately the thinnest of the four scripts.

    ../.venv/bin/python3 run_analysis.py 1 --data-dir ../data --sim-data
    ../.venv/bin/python3 run_analysis.py 1 --sim-data --config ../config/analysis_upstream3.conf

--config picks another analysis config (default config/analysis.conf); the output
directory and ROOT file are taken from that config's output_directory / histogram_file.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import plot_style as ps
import ROOT

CONFIG = common.TELESCOPE_DIR / "config" / "analysis.conf"


def output_paths(config: Path, args) -> tuple[Path, Path]:
    """(output_directory, histogram_file path) of a corry config, resolved like corry does
    (relative to the config file's own directory). With --setup the directory moves to
    output/<setup>/run<N>/<same directory name> (e.g. output/<setup>/run121/analysis_upstream3)."""
    section = common._read_ini_like(config)["Corryvreckan"]
    out_dir = (config.parent / section["output_directory"]).resolve()
    if args.setup:
        out_dir = common.step_dir(args, out_dir.name)
    return out_dir, out_dir / section["histogram_file"]


def plot_residuals(f, dut, run_number, out_dir):
    """Residual confirmation plots against the final aligned_dut geometry:
    per-reference-plane global residuals (Tracking4D, same as the old
    Alignment.py plot) plus the DUT's own residuals (AnalysisDUT, same as
    the old AlignmentDUT.py plot)."""
    # only the planes Tracking4D actually used (e.g. 3 for analysis_upstream3.conf)
    # (the Tracking4D/<det> directories exist for every plane in the geometry, so check entries)
    reference_planes = [d for d in common.DETECTORS if d != dut
                        and f.Get(f"Tracking4D/{d}/global_residuals/GlobalResidualsX")
                        and f.Get(f"Tracking4D/{d}/global_residuals/GlobalResidualsX").GetEntries() > 0]

    canvas = common.make_grid_canvas(f"c_residuals_run{run_number}", 3, 3, width=1900, height=1500)
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
            lines.append(f"#sigma_{{x}} = {fit_x['sigma']*1000:.3f} #pm {fit_x['sigma_err']*1000:.3f} #mum")
        if fit_y:
            lines.append(f"#sigma_{{y}} = {fit_y['sigma']*1000:.3f} #pm {fit_y['sigma_err']*1000:.3f} #mum")
        corner = ps.pick_label_corner(hx)
        label = ps.draw_corner_label(pad, lines, corner=corner, header_size=0.065, body_size=0.055, dy=0.09)

        leg_x1, leg_x2 = (0.62, 0.90) if "left" in corner else (0.14, 0.42)
        legend = ps.make_clean_legend(leg_x1, 0.80, leg_x2, 0.93, text_size=0.05)
        legend.AddEntry(hx, "x", "l")
        legend.AddEntry(hy, "y", "l")
        legend.Draw()

        keepalive.append((hx, hy, fit_x, fit_y, label, legend))

        if fit_x:
            print(f"{det}: X residual mean {fit_x['mean']*1000:+.3f} um, "
                  f"sigma {fit_x['sigma']*1000:.3f} +/- {fit_x['sigma_err']*1000:.3f} um")
        if fit_y:
            print(f"{det}: Y residual mean {fit_y['mean']*1000:+.3f} um, "
                  f"sigma {fit_y['sigma']*1000:.3f} +/- {fit_y['sigma_err']*1000:.3f} um")

    dut_dir = f.Get(f"AnalysisDUT/{dut}/global_residuals")
    for i, (hist_name, axis_label) in enumerate([("residualsX", "x"), ("residualsY", "y")], start=8):
        pad = canvas.cd(i)
        pad.SetLeftMargin(0.14)
        h = common.get_hist(dut_dir, hist_name) if dut_dir else None
        if h is None:
            print(f"  [warn] histogram not found: AnalysisDUT/{dut}/global_residuals/{hist_name}")
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
            lines = [dut, f"mean = {fit['mean']:.2f} #pm {fit['mean_err']:.2f} #mum",
                     f"sigma = {fit['sigma']:.2f} #pm {fit['sigma_err']:.2f} #mum"]
            corner = ps.pick_label_corner(h)
            label = ps.draw_corner_label(pad, lines, corner=corner, header_size=0.06, body_size=0.05, dy=0.09)
            keepalive.append(label)
            print(f"{dut}: {axis_label} residual mean {fit['mean']:+.2f} um, sigma {fit['sigma']:.2f} um")
        keepalive.append((h, fit))

    canvas.cd(0)
    return common.save(canvas, out_dir, f"run{run_number}_residuals")


def main():
    parser = common.base_arg_parser("Run the main corry analysis chain")
    parser.add_argument("--config", default=str(CONFIG),
                        help="Analysis config to run (default: config/analysis.conf), "
                             "e.g. ../config/analysis_upstream3.conf for upstream-only tracking")
    args = parser.parse_args()
    config = Path(args.config).resolve()
    out_dir, root_path = output_paths(config, args)

    overrides = common.standard_overrides(args)
    overrides.update(common.setup_overrides(args, "analysis", out_dir))

    log_path = out_dir / f"run{args.run_number}_corry.log"
    dut = common.run_corry(config, overrides, log_path, dut=args.dut)

    f = ROOT.TFile.Open(str(root_path))

    canvas = ROOT.TCanvas(f"c_analysis_run{args.run_number}", "analysis", 1400, 650)
    canvas.Divide(2, 1)
    keepalive = []

    pad = canvas.cd(1)
    pad.SetRightMargin(0.16)
    emap = common.get_hist(f, f"AnalysisEfficiency/{dut}/chipEfficiencyMap_trackPos")
    if emap is not None:
        h2 = emap.GetTotalHistogram()
        h2.GetXaxis().SetTitle("column")
        h2.GetYaxis().SetTitle("row")
        ps.style_axis_font43(h2.GetXaxis(), title_size=16, title_offset=2.2, label_size=13)
        ps.style_axis_font43(h2.GetYaxis(), title_size=16, title_offset=1.8, label_size=13)
        emap.Draw("COLZ")
        corner = ps.pick_label_corner_2d(h2)
        label = ps.draw_corner_label(pad, [f"{dut} chip efficiency"],
                                      corner=corner, header_size=0.045, color=ROOT.kBlack)
        keepalive.append((emap, h2, label))

    pad = canvas.cd(2)
    etot = common.get_hist(f, f"AnalysisEfficiency/{dut}/eTotalEfficiency")
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
        title.DrawLatex(0.5, 0.75, f"{dut} total efficiency")
        keepalive.append((text, sub, title))
        print(f"{dut} total efficiency: {eff*100:.2f} % (+{hi*100:.2f}/-{lo*100:.2f})")

    canvas.cd(0)
    png_path = common.save(canvas, out_dir, f"run{args.run_number}_summary")
    print(f"Summary: {png_path}")

    residuals_png_path = plot_residuals(f, dut, args.run_number, out_dir)
    print(f"Residuals: {residuals_png_path}")


if __name__ == "__main__":
    main()
