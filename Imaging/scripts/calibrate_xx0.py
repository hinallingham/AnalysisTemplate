#!/usr/bin/env python3
"""Calibrate the material-budget image (kink width) to x/X0 with Al plates of known thickness,
taking the telescope's own contribution out (Jansen et al., doi:10.1063/1.5005503).

Model for the measured width (AAD of the central 90 % of the kink angles, x and y pooled):

    theta_meas^2 = dtheta^2 + [kappa * theta_HL(x/X0 + eps)]^2
    theta_HL(x)  = 13.6 MeV / p * sqrt(x) * (1 + 0.038 ln x)          (beta = 1)

  dtheta : the telescope's own width -- arm resolution + scattering in RP3/RP4 and air,
           fixed in practice by the 0 mm point (run without sample)
  eps    : material that is always there and enters the log term together with the sample
  kappa  : AAD(90 %) / theta_0 (0.69 for a pure Gaussian; tails make it differ)

Each image cell is then inverted: x/X0 = theta_HL^-1( sqrt(theta^2 - dtheta^2) / kappa ) - eps.
Because of the log term and of the AAD -> theta_0 scale, a plain quadratic subtraction of
the empty-telescope width would not give x/X0; the fit takes both into account.

The width of a calibration run is the AAD of the pooled kink distribution
(TrackingMultiplet/multipletKinkAtScatterer{X,Y}, every multiplet -- the plates cover the
whole beam), not the median of the per-cell values: with ~30 kinks per cell the per-cell
AAD trims more than 10 % (round(n * 0.05) per side) and comes out a few % low, i.e. it would
depend on the statistics of the calibration run. The MLCC runs have ~200 kinks per cell,
where the trimming is exact.

Inputs: output/imaging/imaging_run<N>.root (scripts/run_imaging.sh). Outputs in DEFAULT_OUT:
  calib_curve          widths of the calibration runs + fit, residuals
  MLCC_run<N>_xx0      calibrated x/X0 image (white: nominal capacitor outlines with --truth)
  MLCC_run<N>_xx0_truth / _xx0_diff / _xx0_xprofile / _xx0_per_capacitor   (--truth only)
  calib_fit.txt        fit parameters

--truth compares with the nominal x/X0 from the simulation generator (true_xx0 in
MLCC_imaging_generate_configs.py), averaged over 5 x 5 points per cell. The generator works
in the Allpix global frame; the aligned frame is tied to MALTA_0 (40 um, 10 um, 0.41 deg roll
in the simulation), so outlines can be off by up to ~0.1 mm.

    calibrate_xx0.py --calib 1:0 10:0.1 11:0.2 12:0.5 13:1 14:2 15:5 16:10 --image-run 2 3 --truth
"""
import argparse
import math
import sys
from pathlib import Path

import ROOT

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_imaging import (DEFAULT_OUT, GENERATOR, HEADER, draw_truth, load_truth, map_canvas,  # noqa: E402
                          ps, shifted)

IMG_DIR = Path(__file__).resolve().parent.parent
X0_AL_CM = 8.897  # PDG
HL = 0.038


def theta_hl(x, p_mev):
    """Highland theta_0 [mrad] for x = x/X0 (beta = 1)."""
    return 13.6 / p_mev * 1e3 * math.sqrt(x) * (1 + HL * math.log(x))


def pooled_aad(f, quantile=0.9):
    """AAD of the central `quantile` of the pooled x+y kink distribution and its error [mrad]."""
    h = f.Get("TrackingMultiplet/multipletKinkAtScattererX").Clone("kink_pooled")
    h.Add(f.Get("TrackingMultiplet/multipletKinkAtScattererY"))
    n = h.Integral(0, h.GetNbinsX() + 1)
    lo, hi = n * (1 - quantile) / 2, n * (1 + quantile) / 2
    if h.GetBinContent(0) > lo or h.GetBinContent(h.GetNbinsX() + 1) > n - hi:
        sys.exit("kink histogram range too narrow for the quantile cut (raise kink_*_low/high)")
    cum = h.GetBinContent(0)
    s1 = s2 = kept = 0.0
    for i in range(1, h.GetNbinsX() + 1):
        c = h.GetBinContent(i)
        # part of this bin inside the central quantile
        w = max(0.0, min(cum + c, hi) - max(cum, lo))
        cum += c
        if w <= 0:
            continue
        a = abs(h.GetBinCenter(i))
        s1 += w * a
        s2 += w * a * a
        kept += w
    aad = s1 / kept
    return aad, math.sqrt(max(s2 / kept - aad * aad, 0.0) / kept)


def make_model(p_mev):
    k = 13.6 / p_mev * 1e3
    f = ROOT.TF1("calib", f"sqrt([0]*[0] + pow([1]*{k}*sqrt(x+[2])*(1+{HL}*log(x+[2])), 2))", 0, 0.2)
    f.SetParNames("dtheta", "kappa", "eps")
    return f


def invert(theta, dtheta, kappa, eps, p_mev):
    """x/X0 for a measured width; may come out < 0 (statistical fluctuations below dtheta)."""
    target = math.sqrt(max(theta * theta - dtheta * dtheta, 0.0)) / kappa
    lo, hi = 1e-9, 1.0
    if theta_hl(lo, p_mev) >= target:
        return lo - eps
    for _ in range(80):
        mid = math.sqrt(lo * hi)
        if theta_hl(mid, p_mev) < target:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi) - eps


def fit_calibration(points, p_mev, outdir):
    """points: [(run, t_mm, xx0, aad, err)]. Returns (dtheta, kappa, eps)."""
    g = ROOT.TGraphErrors()
    for i, (_, _, xx0, aad, err) in enumerate(points):
        g.SetPoint(i, xx0, aad)
        g.SetPointError(i, 0, err)
    model = make_model(p_mev)
    zero = [aad for _, _, xx0, aad, _ in points if xx0 == 0]
    model.SetParameters(zero[0] if zero else 0.15, 0.69, 0.002)
    model.SetParLimits(0, 0.0, 5.0)
    model.SetParLimits(1, 0.1, 2.0)
    model.SetParLimits(2, 1e-6, 0.05)
    res = g.Fit(model, "QSN")
    if int(res) != 0:
        print(f"WARNING: calibration fit status {int(res)}")
    par = [model.GetParameter(i) for i in range(3)]
    err = [model.GetParError(i) for i in range(3)]
    chi2, ndf = model.GetChisquare(), model.GetNDF()

    lines = [f"# kink width -> x/X0 calibration, p = {p_mev:g} MeV",
             "# theta^2 = dtheta^2 + [kappa * theta_HL(x/X0 + eps)]^2",
             f"dtheta = {par[0]:.5f} +- {err[0]:.5f} mrad",
             f"kappa  = {par[1]:.5f} +- {err[1]:.5f}",
             f"eps    = {par[2]:.6f} +- {err[2]:.6f}",
             f"chi2/ndf = {chi2:.2f}/{ndf}",
             "# run  t_Al[mm]  x/X0  AAD[mrad]  err  fit  (data-fit)/err"]
    for run, t, xx0, aad, e in points:
        fv = model.Eval(xx0)
        lines.append(f"{run:4d}  {t:7.3f}  {xx0:.5f}  {aad:.5f}  {e:.5f}  {fv:.5f}  {(aad - fv) / e:+.2f}")
    Path(outdir).mkdir(parents=True, exist_ok=True)
    (Path(outdir) / "calib_fit.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))

    # --- plot: log x (the 0 mm point is drawn as a band), residual panel below
    c = ROOT.TCanvas("c_calib", "c_calib", 900, 800)
    top = ROOT.TPad("top", "", 0, 0.3, 1, 1)
    bot = ROOT.TPad("bot", "", 0, 0, 1, 0.3)
    for pad in (top, bot):
        pad.SetLeftMargin(0.13)
        pad.SetRightMargin(0.04)
        pad.SetLogx()
        pad.Draw()
    top.SetBottomMargin(0.02)
    bot.SetTopMargin(0.03)
    bot.SetBottomMargin(0.33)
    xmin, xmax = 4e-4, 0.3
    keep = []

    top.cd()
    gal = ROOT.TGraphErrors()
    for _, _, xx0, aad, e in points:
        if xx0 > 0:
            gal.SetPoint(gal.GetN(), xx0, aad)
            gal.SetPointError(gal.GetN() - 1, 0, e)
    frame = top.DrawFrame(xmin, 0, xmax, max(p[3] for p in points) * 1.25)
    frame.GetYaxis().SetTitle("kink width (AAD, 90%) [mrad]")
    frame.GetYaxis().SetTitleSize(0.055)
    frame.GetYaxis().SetLabelSize(0.05)
    frame.GetXaxis().SetLabelSize(0)
    curve = make_model(p_mev)
    curve.SetParameters(*par)
    curve.SetRange(xmin, xmax)
    curve.SetLineColor(ROOT.kAzure + 2)
    curve.SetLineWidth(2)
    curve.Draw("SAME")
    tel = ROOT.TF1("tel", f"{par[0]}", xmin, xmax)  # telescope only
    tel.SetLineColor(ROOT.kGray + 1)
    tel.SetLineStyle(2)
    tel.Draw("SAME")
    sample = ROOT.TF1("sample_only", f"{par[1]}*{13.6 / p_mev * 1e3}*sqrt(x+{par[2]})*(1+{HL}*log(x+{par[2]}))",
                      xmin, xmax)
    sample.SetLineColor(ROOT.kOrange + 7)
    sample.SetLineStyle(7)
    sample.Draw("SAME")
    gal.SetMarkerStyle(20)
    gal.Draw("P SAME")
    leg = ps.make_clean_legend(0.16, 0.56, 0.6, 0.88, text_size=0.045)
    leg.AddEntry(gal, "Al plates (0.1 - 10 mm)", "p")
    leg.AddEntry(tel, f"no sample (run {[p[0] for p in points if p[2] == 0][0]}): "
                      f"#Delta#theta = {par[0]:.3f} mrad" if zero else "#Delta#theta", "l")
    leg.AddEntry(sample, f"#kappa #theta_{{HL}}(x/X_{{0}}+#varepsilon), #kappa = {par[1]:.3f}, "
                         f"#varepsilon = {par[2] * 100:.2f}%", "l")
    leg.AddEntry(curve, f"fit, #chi^{{2}}/ndf = {chi2:.1f}/{ndf}", "l")
    leg.Draw()
    keep += [gal, curve, tel, sample, leg]
    keep.append(ps.draw_corner_label(top, [HEADER, "3 GeV e^{-}"], corner="bottom-right"))

    bot.cd()
    gr = ROOT.TGraphErrors()
    for _, _, xx0, aad, e in points:
        if xx0 > 0:
            fv = curve.Eval(xx0)
            gr.SetPoint(gr.GetN(), xx0, (aad - fv) / fv * 100)
            gr.SetPointError(gr.GetN() - 1, 0, e / fv * 100)
    fr2 = bot.DrawFrame(xmin, -4, xmax, 4)
    fr2.GetXaxis().SetTitle("x/X_{0} of the Al plate")
    fr2.GetYaxis().SetTitle("(data - fit)/fit [%]")
    fr2.GetYaxis().SetNdivisions(505)
    for ax in (fr2.GetXaxis(), fr2.GetYaxis()):
        ax.SetTitleSize(0.12)
        ax.SetLabelSize(0.11)
    fr2.GetYaxis().SetTitleOffset(0.45)
    fr2.GetXaxis().SetTitleOffset(1.1)
    line = ROOT.TLine(xmin, 0, xmax, 0)
    line.SetLineStyle(2)
    line.Draw()
    gr.SetMarkerStyle(20)
    gr.Draw("P SAME")
    keep += [gr, line]
    ps.save(c, outdir, "calib_curve")
    return par


def truth_map(gen, sample, template, sub=5):
    """Nominal x/X0 per image cell (mean over sub x sub points)."""
    h = template.Clone("truth")
    h.Reset()
    h.SetDirectory(0)
    ax, ay = h.GetXaxis(), h.GetYaxis()
    for i in range(1, h.GetNbinsX() + 1):
        for j in range(1, h.GetNbinsY() + 1):
            x0, y0 = ax.GetBinLowEdge(i), ay.GetBinLowEdge(j)
            dx, dy = ax.GetBinWidth(i) / sub, ay.GetBinWidth(j) / sub
            v = sum(gen.true_xx0(x0 + (a + 0.5) * dx, y0 + (b + 0.5) * dy, sample)
                    for a in range(sub) for b in range(sub)) / sub ** 2
            h.SetBinContent(i, j, v * 100)
    return h


def image_xx0(run, par, p_mev, imaging_dir, outdir, gen):
    f = ROOT.TFile.Open(str(Path(imaging_dir) / f"imaging_run{run}.root"))
    img = shifted(f.Get("AnalysisMaterialBudget/MBISqrt"), f"img{run}")
    xx0 = img.Clone(f"xx0_{run}")
    xx0.Reset()
    xx0.SetDirectory(0)
    mask = set()
    for i in range(1, img.GetNbinsX() + 1):
        for j in range(1, img.GetNbinsY() + 1):
            th = img.GetBinContent(i, j)
            if th > 0:
                xx0.SetBinContent(i, j, invert(th, *par, p_mev) * 100)
                mask.add((i, j))
    keep = []
    prefix = f"MLCC_run{run}_xx0"
    vals = sorted(xx0.GetBinContent(i, j) for i, j in mask)
    zmax = vals[int(0.995 * len(vals)) - 1]
    # cells without image value stay white: keep them at 0 and draw from a tiny positive minimum
    for i in range(1, xx0.GetNbinsX() + 1):
        for j in range(1, xx0.GetNbinsY() + 1):
            if (i, j) in mask:
                xx0.SetBinContent(i, j, max(xx0.GetBinContent(i, j), 1e-4))
    c = map_canvas(f"c_{prefix}", xx0, "x/X_{0} [%]", 1e-4, zmax)
    if gen:
        draw_truth(gen, keep, run)
    lat = ROOT.TLatex()
    lat.SetNDC()
    lat.SetTextSize(0.04)
    lat.DrawLatex(0.07, 0.94, f"#bf{{{HEADER}}}  run {run}, calibrated with Al, 100 #mum cells")
    keep.append(lat)
    ps.save(c, outdir, prefix)
    if not gen:
        return

    sample = {r: s for r, s, _ in gen.RUNS.values()}[int(run)]
    tr = truth_map(gen, sample, xx0)
    for i in range(1, tr.GetNbinsX() + 1):
        for j in range(1, tr.GetNbinsY() + 1):
            tr.SetBinContent(i, j, max(tr.GetBinContent(i, j), 1e-4) if (i, j) in mask else 0)
    c2 = map_canvas(f"c_{prefix}_truth", tr, "nominal x/X_{0} [%]", 1e-4, zmax)
    draw_truth(gen, keep, run)
    ps.save(c2, outdir, f"{prefix}_truth")

    diff = xx0.Clone(f"diff{run}")
    diff.Reset()
    for i, j in mask:
        diff.SetBinContent(i, j, xx0.GetBinContent(i, j) - tr.GetBinContent(i, j) or 1e-6)
    lim = 0.3 * zmax
    ROOT.gStyle.SetPalette(ROOT.kTemperatureMap)
    c3 = map_canvas(f"c_{prefix}_diff", diff, "x/X_{0} calibrated - nominal [%]", -lim, lim)
    draw_truth(gen, keep, run)
    ps.save(c3, outdir, f"{prefix}_diff")
    ROOT.gStyle.SetPalette(ROOT.kInvertedDarkBodyRadiator)

    # --- x profiles through the two capacitor rows: calibrated vs nominal
    rows = sorted({y for _, _, _, y, _ in gen.LAYOUT}, reverse=True)
    c4 = ROOT.TCanvas(f"c_{prefix}_xprof", "", 1100, 400 * len(rows))
    c4.Divide(1, len(rows))
    for k, y0 in enumerate(rows):
        pad = c4.cd(k + 1)
        pad.SetLeftMargin(0.09)
        pad.SetRightMargin(0.03)
        pad.SetBottomMargin(0.15)
        jy = [j for j in range(1, xx0.GetNbinsY() + 1) if abs(xx0.GetYaxis().GetBinCenter(j) - y0) < 0.2]
        hm = ROOT.TH1D(f"pm{run}_{k}", "", xx0.GetNbinsX(), xx0.GetXaxis().GetXmin(), xx0.GetXaxis().GetXmax())
        ht = hm.Clone(f"pt{run}_{k}")
        for h in (hm, ht):
            h.SetDirectory(0)
        for i in range(1, xx0.GetNbinsX() + 1):
            cells = [j for j in jy if (i, j) in mask]
            if not cells:
                continue
            vm = [xx0.GetBinContent(i, j) for j in cells]
            mean = sum(vm) / len(vm)
            rms = math.sqrt(sum((v - mean) ** 2 for v in vm) / len(vm))
            hm.SetBinContent(i, mean)
            hm.SetBinError(i, rms / math.sqrt(len(vm)))
            ht.SetBinContent(i, sum(tr.GetBinContent(i, j) for j in cells) / len(cells))
        hm.SetMarkerStyle(20)
        hm.SetMarkerSize(0.5)
        hm.SetLineColor(ROOT.kAzure + 2)
        hm.SetMarkerColor(ROOT.kAzure + 2)
        ht.SetLineColor(ROOT.kOrange + 7)
        ht.SetLineWidth(2)
        hm.SetMinimum(min(0, hm.GetMinimum()))
        hm.SetMaximum(max(hm.GetMaximum(), ht.GetMaximum()) * 1.3)
        hm.GetXaxis().SetTitle("x at scatterer [mm]")
        hm.GetYaxis().SetTitle("x/X_{0} [%]")
        for ax in (hm.GetXaxis(), hm.GetYaxis()):
            ax.SetTitleSize(0.06)
            ax.SetLabelSize(0.055)
        hm.GetYaxis().SetTitleOffset(0.6)
        hm.Draw("E1")
        ht.Draw("HIST SAME")
        leg = ps.make_clean_legend(0.11, 0.7, 0.5, 0.88, text_size=0.05)
        leg.AddEntry(hm, f"calibrated, |y - ({y0:+.1f} mm)| < 0.2 mm", "lp")
        leg.AddEntry(ht, "nominal (geometry)", "l")
        leg.Draw()
        keep += [hm, ht, leg]
    ps.save(c4, outdir, f"{prefix}_xprofile")

    # --- per capacitor: mean over the inner part (body, away from edges and terminations)
    g = ROOT.TGraphErrors()
    print(f"run {run}: per-capacitor x/X0 [%], inner region (calibrated / nominal)")
    labels = []
    for label, size, cx, cy, rot in gen.LAYOUT:
        L, W, _, band = gen.SIZES[size]
        hl, hw = (L / 2 - band - 0.05, W / 2 - 0.1)
        if rot:
            hl, hw = hw, hl
        sel = [(i, j) for i, j in mask
               if abs(xx0.GetXaxis().GetBinCenter(i) - cx) < hl and abs(xx0.GetYaxis().GetBinCenter(j) - cy) < hw]
        if len(sel) < 2:
            continue
        vm = [xx0.GetBinContent(i, j) for i, j in sel]
        vt = [tr.GetBinContent(i, j) for i, j in sel]
        mean, nominal = sum(vm) / len(vm), sum(vt) / len(vt)
        rms = math.sqrt(sum((v - mean) ** 2 for v in vm) / len(vm))
        g.SetPoint(g.GetN(), nominal, mean)
        g.SetPointError(g.GetN() - 1, 0, rms / math.sqrt(len(vm)))
        labels.append((nominal, mean, f"{label} {size}"))
        print(f"  {label} {size:6s} {mean:7.3f} +- {rms / math.sqrt(len(vm)):.3f}   {nominal:7.3f}  ({len(sel)} cells)")
    bg = [(i, j) for i, j in mask if tr.GetBinContent(i, j) <= 1e-4 * 1.01]
    if bg:
        vb = [xx0.GetBinContent(i, j) for i, j in bg]
        print(f"  no material: {sum(vb) / len(vb):.4f} %  ({len(vb)} cells)")
    c5 = ROOT.TCanvas(f"c_{prefix}_cap", "", 800, 750)
    c5.SetLeftMargin(0.14)
    c5.SetBottomMargin(0.13)
    top = max(max(p[0], p[1]) for p in labels) * 1.15
    fr = c5.DrawFrame(0, 0, top, top)
    fr.GetXaxis().SetTitle("nominal x/X_{0} [%]")
    fr.GetYaxis().SetTitle("calibrated x/X_{0} [%]")
    diag = ROOT.TLine(0, 0, top, top)
    diag.SetLineStyle(2)
    diag.SetLineColor(ROOT.kGray + 1)
    diag.Draw()
    g.SetMarkerStyle(20)
    g.SetMarkerColor(ROOT.kAzure + 2)
    g.Draw("P SAME")
    for nominal, mean, text in labels:
        t = ROOT.TLatex(nominal + 0.01 * top, mean - 0.035 * top, text)
        t.SetTextSize(0.028)
        t.Draw()
        keep.append(t)
    keep += [g, diag]
    keep.append(ps.draw_corner_label(c5, [HEADER, f"run {run}, capacitor bodies"], corner="top-left"))
    ps.save(c5, outdir, f"{prefix}_per_capacitor")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--calib", nargs="+", required=True, metavar="RUN:T_MM",
                    help="calibration runs and their Al thickness in mm (0 = run without sample)")
    ap.add_argument("--image-run", nargs="*", default=[], help="runs to convert to x/X0")
    ap.add_argument("--imaging-dir", default=str(IMG_DIR / "output" / "imaging"))
    ap.add_argument("--outdir", default=DEFAULT_OUT)
    ap.add_argument("--momentum", type=float, default=3000.0, help="beam momentum [MeV]")
    ap.add_argument("--truth", action="store_true", help="compare with the nominal x/X0 of the simulation")
    ap.add_argument("--generator", default=GENERATOR, help="simulation generator for --truth")
    args = ap.parse_args()

    ps.set_global_style(palette=ROOT.kInvertedDarkBodyRadiator)
    points = []
    for item in args.calib:
        run, t = item.split(":")
        f = ROOT.TFile.Open(str(Path(args.imaging_dir) / f"imaging_run{run}.root"))
        if not f or f.IsZombie():
            sys.exit(f"missing imaging_run{run}.root -- run scripts/run_imaging.sh --image-run {run} first")
        aad, err = pooled_aad(f)
        points.append((int(run), float(t), float(t) * 0.1 / X0_AL_CM, aad, err))
        f.Close()
    points.sort(key=lambda p: p[2])
    if len(points) < 4:
        sys.exit("need at least 4 calibration points for 3 parameters")
    par = fit_calibration(points, args.momentum, args.outdir)

    gen = load_truth(args.generator) if args.truth else None
    for run in args.image_run:
        image_xx0(run, par, args.momentum, args.imaging_dir, args.outdir, gen)


if __name__ == "__main__":
    main()
