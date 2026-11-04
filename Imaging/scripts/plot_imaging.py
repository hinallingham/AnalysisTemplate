#!/usr/bin/env python3
"""Plots for the material-budget imaging step (output/imaging/imaging_run<N>.root):

  <prefix>_image          kink-angle width per image cell (AnalysisMaterialBudget MBISqrt)
  <prefix>_tracks         multiplets per cell (from the MBIpreview profile)
  <prefix>_xprofile       image rows through the two capacitor rows (y bands), vs x
  <prefix>_kink           kink-angle distribution at the scatterer, x and y

AnalysisMaterialBudget fills its maps with SetBinContent(cell_x, cell_y) for 0-based cell
indices, i.e. one bin too low in x and y (cell 0 ends up in the underflow). The maps are
shifted back by one bin here before drawing.

--truth overlays the nominal capacitor (and PCB) outlines from the simulation generator
(MLCC_imaging_generate_configs.py; Allpix global frame, so up to ~0.1 mm off the aligned
frame, which is tied to MALTA_0).

    plot_imaging.py ../output/imaging/imaging_run2.root --run 2 --truth
"""
import argparse
import importlib.util
import math
import sys
from pathlib import Path

import ROOT

ROOT.gROOT.SetBatch(True)
sys.path.insert(0, "/home/hinata/MALTA2/AnalysisTemplate/Telescope/scripts/style")
import plot_style as ps  # noqa: E402

GENERATOR = "/home/hinata/MALTA2/Telescope/sim/config/MLCC_imaging_generate_configs.py"
DEFAULT_OUT = "/home/hinata/output/plot/MALTA2/simulation_analyze/material_imaging"
HEADER = "MALTA2 Telescope"  # + " (sim.)" with --sim-data


def shifted(raw, name):
    """Copy of a TH2 / TProfile2D-derived TH2 with contents moved up by one bin in x and y."""
    h = ROOT.TH2D(name, "", raw.GetNbinsX(), raw.GetXaxis().GetXmin(), raw.GetXaxis().GetXmax(),
                  raw.GetNbinsY(), raw.GetYaxis().GetXmin(), raw.GetYaxis().GetXmax())
    h.SetDirectory(0)
    for ix in range(1, raw.GetNbinsX() + 1):
        for iy in range(1, raw.GetNbinsY() + 1):
            h.SetBinContent(ix, iy, raw.GetBinContent(ix - 1, iy - 1))
    return h


def load_truth(generator=GENERATOR):
    spec = importlib.util.spec_from_file_location("mlcc_gen", generator)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    return gen


def draw_truth(gen, keep, run):
    """Outline of every capacitor body plus its two termination bands, and of the PCB if this
    run has one."""
    substrate = {r: sub for r, sub, _ in gen.RUNS.values()}.get(int(run))
    if substrate == "pcb":
        pcb = ROOT.TBox(gen.PCB_X[0], gen.PCB_Y[0], gen.PCB_X[1], gen.PCB_Y[1])
        pcb.SetFillStyle(0)
        pcb.SetLineColor(ROOT.kAzure + 1)
        pcb.SetLineWidth(2)
        pcb.SetLineStyle(2)
        pcb.Draw("l")
        keep.append(pcb)
    for label, size, x, y, rot in gen.LAYOUT:
        L, W, _, band = gen.SIZES[size]
        W += 2 * gen.TERM_SIDE
        hl, hw = (W / 2, L / 2) if rot else (L / 2, W / 2)
        box = ROOT.TBox(x - hl, y - hw, x + hl, y + hw)
        box.SetFillStyle(0)
        box.SetLineColor(ROOT.kWhite)
        box.SetLineWidth(1)
        box.SetLineStyle(2)
        box.Draw("l")
        keep.append(box)
        for s in (-1, 1):  # inner edge of each termination band
            if rot:
                ln = ROOT.TLine(x - hl, y + s * (hw - band), x + hl, y + s * (hw - band))
            else:
                ln = ROOT.TLine(x + s * (hl - band), y - hw, x + s * (hl - band), y + hw)
            ln.SetLineColor(ROOT.kWhite)
            ln.SetLineStyle(3)
            ln.Draw()
            keep.append(ln)
        txt = ROOT.TLatex(x, y + hw + 0.12, f"{label} {size}")
        txt.SetTextAlign(21)
        txt.SetTextSize(0.028)
        txt.SetTextColor(ROOT.kWhite)
        txt.Draw()
        keep.append(txt)


def map_canvas(name, h, ztitle, zmin=None, zmax=None):
    nx = h.GetXaxis().GetXmax() - h.GetXaxis().GetXmin()
    ny = h.GetYaxis().GetXmax() - h.GetYaxis().GetXmin()
    c = ROOT.TCanvas(name, name, 1400, int(1400 * ny / nx * 0.86) + 120)
    c.SetLeftMargin(0.07)
    c.SetRightMargin(0.13)
    c.SetTopMargin(0.08)
    c.SetBottomMargin(0.13)
    h.GetXaxis().SetTitle("x at scatterer [mm]")
    h.GetYaxis().SetTitle("y at scatterer [mm]")
    h.GetZaxis().SetTitle(ztitle)
    h.GetYaxis().SetTitleOffset(0.6)
    h.GetZaxis().SetTitleOffset(0.8)
    for ax in (h.GetXaxis(), h.GetYaxis(), h.GetZaxis()):
        ax.SetTitleSize(0.05)
        ax.SetLabelSize(0.045)
    if zmin is not None:
        h.SetMinimum(zmin)
    if zmax is not None:
        h.SetMaximum(zmax)
    h.Draw("COLZ")
    return c


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root_file")
    ap.add_argument("--run", default="2")
    ap.add_argument("--outdir", default=DEFAULT_OUT)
    ap.add_argument("--prefix", default=None, help="file name prefix (default: MLCC_run<run>)")
    ap.add_argument("--truth", action="store_true", help="overlay nominal capacitor outlines")
    ap.add_argument("--sim-data", action="store_true", help='label the plots "(sim.)"')
    ap.add_argument("--generator", default=GENERATOR, help="simulation generator for --truth")
    args = ap.parse_args()
    prefix = args.prefix or f"MLCC_run{args.run}"
    header = HEADER + (" (sim.)" if args.sim_data else "")

    ps.set_global_style(palette=ROOT.kInvertedDarkBodyRadiator)
    f = ROOT.TFile.Open(args.root_file)
    amb = f.Get("AnalysisMaterialBudget")
    gen = load_truth(args.generator) if args.truth else None
    keep = []

    # --- image: AAD of the central 90% of kink angles (x and y pooled), per cell
    img = shifted(amb.Get("MBISqrt"), "img")
    filled = [img.GetBinContent(i, j) for i in range(1, img.GetNbinsX() + 1)
              for j in range(1, img.GetNbinsY() + 1) if img.GetBinContent(i, j) > 0]
    if not filled:
        sys.exit("MBISqrt is empty: not enough multiplets per cell (min_cell_content)")
    filled.sort()
    zmin, zmax = filled[int(0.01 * len(filled))], filled[int(0.995 * len(filled)) - 1]
    c = map_canvas("c_image", img, "kink width (AAD, 90%) [mrad]", zmin * 0.95, zmax)
    if gen:
        draw_truth(gen, keep, args.run)
    # label in the top margin: the image itself fills the whole frame
    lat = ROOT.TLatex()
    lat.SetNDC()
    lat.SetTextSize(0.04)
    cell_um = round(img.GetXaxis().GetBinWidth(1) * 1e3)
    lat.DrawLatex(0.07, 0.94, f"#bf{{{header}}}  run {args.run}, 3 GeV e^{{-}}, {cell_um} #mum cells")
    keep.append(lat)
    ps.save(c, args.outdir, f"{prefix}_image")

    # --- multiplets per cell (bin entries of the kink^2 profile count x and y separately)
    prof = amb.Get("MBIpreview")
    trk = ROOT.TH2D("trk", "", prof.GetNbinsX(), prof.GetXaxis().GetXmin(), prof.GetXaxis().GetXmax(),
                    prof.GetNbinsY(), prof.GetYaxis().GetXmin(), prof.GetYaxis().GetXmax())
    trk.SetDirectory(0)
    for ix in range(1, prof.GetNbinsX() + 1):
        for iy in range(1, prof.GetNbinsY() + 1):
            trk.SetBinContent(ix, iy, prof.GetBinEntries(prof.GetBin(ix, iy)) / 2)
    c2 = map_canvas("c_tracks", trk, "multiplets / cell")
    if gen:
        draw_truth(gen, keep, args.run)
    ps.save(c2, args.outdir, f"{prefix}_tracks")

    # --- x profiles through the capacitor rows: mean image value over a y band
    rows = sorted({y for _, _, _, y, _ in gen.LAYOUT}, reverse=True) if gen else [1.9, -1.9]
    colors = [ROOT.kAzure + 2, ROOT.kOrange + 7, ROOT.kGreen + 2]
    c3 = ROOT.TCanvas("c_xprof", "c_xprof", 1100, 600)
    c3.SetLeftMargin(0.11)
    c3.SetRightMargin(0.04)
    c3.SetBottomMargin(0.13)
    leg = ps.make_clean_legend(0.13, 0.72, 0.45, 0.88, text_size=0.040)
    hmax = 0
    profs = []
    for k, y0 in enumerate(rows):
        hp = ROOT.TH1D(f"xprof{k}", "", img.GetNbinsX(), img.GetXaxis().GetXmin(), img.GetXaxis().GetXmax())
        hp.SetDirectory(0)
        jy = [j for j in range(1, img.GetNbinsY() + 1) if abs(img.GetYaxis().GetBinCenter(j) - y0) < 0.2]
        for i in range(1, img.GetNbinsX() + 1):
            vals = [img.GetBinContent(i, j) for j in jy if img.GetBinContent(i, j) > 0]
            if vals:
                hp.SetBinContent(i, sum(vals) / len(vals))
                rms = math.sqrt(sum((v - sum(vals) / len(vals)) ** 2 for v in vals) / len(vals))
                hp.SetBinError(i, rms / math.sqrt(len(vals)))
        hp.SetLineColor(colors[k % len(colors)])
        hp.SetMarkerColor(colors[k % len(colors)])
        hp.SetMarkerStyle(20)
        hp.SetMarkerSize(0.6)
        hp.SetLineWidth(2)
        hmax = max(hmax, hp.GetMaximum())
        profs.append(hp)
        leg.AddEntry(hp, f"|y - ({y0:+.1f} mm)| < 0.2 mm", "lp")
    for k, hp in enumerate(profs):
        hp.SetMaximum(hmax * 1.35)
        hp.SetMinimum(0)
        hp.GetXaxis().SetTitle("x at scatterer [mm]")
        hp.GetYaxis().SetTitle("kink width (AAD, 90%) [mrad]")
        for ax in (hp.GetXaxis(), hp.GetYaxis()):
            ax.SetTitleSize(0.05)
            ax.SetLabelSize(0.045)
        hp.Draw("E1" if k == 0 else "E1 SAME")
    leg.Draw()
    keep.append(ps.draw_corner_label(c3, [header, f"run {args.run}"], corner="top-right"))
    ps.save(c3, args.outdir, f"{prefix}_xprofile")

    # --- kink-angle distributions
    c4 = ROOT.TCanvas("c_kink", "c_kink", 900, 640)
    c4.SetLogy()
    c4.SetLeftMargin(0.13)
    c4.SetBottomMargin(0.13)
    leg4 = ps.make_clean_legend(0.16, 0.75, 0.45, 0.88, text_size=0.040)
    for k, (axis, col) in enumerate((("X", ROOT.kAzure + 2), ("Y", ROOT.kOrange + 7))):
        # 0.05 mrad bins resolve the pixel quantisation of the arm slopes (comb pattern): x4
        h = f.Get(f"TrackingMultiplet/multipletKinkAtScatterer{axis}").Rebin(4, f"kink{axis}")
        h.SetLineColor(col)
        h.SetLineWidth(2)
        h.GetXaxis().SetTitle("kink angle at scatterer [mrad]")
        h.GetYaxis().SetTitle("multiplets")
        h.GetXaxis().SetTitleSize(0.05)
        h.GetYaxis().SetTitleSize(0.05)
        h.Draw("HIST" if k == 0 else "HIST SAME")
        leg4.AddEntry(h, f"kink {axis.lower()}  (RMS {h.GetRMS():.2f} mrad)", "l")
        keep.append(h)
    leg4.Draw()
    keep.append(ps.draw_corner_label(c4, [header, f"run {args.run}"], corner="top-right"))
    ps.save(c4, args.outdir, f"{prefix}_kink")


if __name__ == "__main__":
    main()
