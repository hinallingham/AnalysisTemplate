// PlotStyle.h -- shared ROOT C++ house style (copy of the root-plot-polish skill style), extracted and generalized from
// the user's MALTA2 comparison macros (plot_cluster_size_compare.C,
// plot_trackangle_compare.C).
//
// Usage inside a macro:
//
//   #include "../../common/PlotStyle.h"   (from Telescope/macros or Imaging/macros)
//
//   void my_macro() {
//       PlotStyle::SetGlobalStyle();
//       TCanvas* c; TPad* pad1; TPad* pad2;
//       PlotStyle::MakeRatioCanvas("c_compare", pad1, pad2, c);
//       ...
//       PlotStyle::DrawCornerLabel(pad1, {"Telescope @ TestBeam", "Run: XDPW Epi"},
//                                   PlotStyle::kTopRight);
//       ...
//       PlotStyle::Save(c, outdir, "clustersize_MALTA_0_compare");
//   }
#pragma once

#include <TCanvas.h>
#include <TPad.h>
#include <TColor.h>
#include <TH1.h>
#include <TH2.h>
#include <TGraph.h>
#include <TLatex.h>
#include <TLegend.h>
#include <TLine.h>
#include <TStyle.h>
#include <TSystem.h>
#include <TString.h>
#include <vector>
#include <algorithm>
#include <cmath>
#include <iostream>

namespace PlotStyle {

enum Corner { kTopRight, kTopLeft, kBottomRight, kBottomLeft };

// Ordered N-series palette (scan parameter as the series, e.g. beam energy or
// a gap length): cold -> warm in parameter order, distinct closed marker each.
const int kSeries5Colors[5]  = {kViolet + 1, kBlue + 1, kGreen + 2, kOrange + 1, kRed + 1};
const int kSeries5Markers[5] = {20, 21, 22, 23, 33};

// n colors evenly sampled from a sequential palette (default kViridis), for scans
// with more ordered series than kSeries5Colors covers. Changes gStyle's palette.
inline std::vector<int> SequentialColors(int n, int palette = kViridis) {
    gStyle->SetPalette(palette);
    const int ncol = TColor::GetNumberOfColors();
    std::vector<int> out;
    for(int i = 0; i < n; ++i) {
        out.push_back(TColor::GetColorPalette(static_cast<int>(std::lround(i * (ncol - 1.0) / std::max(n - 1, 1)))));
    }
    return out;
}

// --------------------------------------------------------------------------
// Global style
// --------------------------------------------------------------------------
inline void SetGlobalStyle(int palette = 113, int nContours = 255) {
    gStyle->SetOptStat(0);
    gStyle->SetOptTitle(0);
    gStyle->SetNumberContours(nContours);
    gStyle->SetPalette(palette);
}

// --------------------------------------------------------------------------
// Ratio-panel canvas (main plot 70% / ratio panel 30%, shared x-axis)
// --------------------------------------------------------------------------
inline void MakeRatioCanvas(const char* name, TPad*& pad1, TPad*& pad2, TCanvas*& c,
                             int width = 900, int height = 640, double split = 0.30) {
    c = new TCanvas(name, name, width, height);

    pad1 = new TPad(Form("%s_main", name), "main", 0.0, split, 1.0, 1.0);
    pad1->SetLeftMargin(0.14);
    pad1->SetRightMargin(0.05);
    pad1->SetTopMargin(0.10);
    pad1->SetBottomMargin(0.02);
    pad1->Draw();

    pad2 = new TPad(Form("%s_ratio", name), "ratio", 0.0, 0.0, 1.0, split);
    pad2->SetLeftMargin(0.14);
    pad2->SetRightMargin(0.05);
    pad2->SetTopMargin(0.03);
    pad2->SetBottomMargin(0.38);
    pad2->Draw();
}

// Hide x-axis labels/title on the main pad (ratio pad below carries them).
inline void HideSharedXAxis(TH1* h) {
    h->GetXaxis()->SetLabelSize(0);
    h->GetXaxis()->SetTitleSize(0);
}

// Font-code-43 (absolute pixel size) axis styling, matching the reference
// macros. Typical values: main-pad y-axis titleSize=20/labelSize=17/offset=1.8;
// ratio-pad y-axis titleSize=15-17/labelSize=15/offset=1.8-2.0; ratio-pad
// x-axis titleSize=20/labelSize=17/offset=3.6.
inline void StyleAxisFont43(TAxis* axis, double titleSize, double titleOffset,
                             double labelSize, int ndivisions = -1) {
    axis->SetTitleFont(43);
    axis->SetTitleSize(titleSize);
    axis->SetTitleOffset(titleOffset);
    axis->SetLabelFont(43);
    axis->SetLabelSize(labelSize);
    if (ndivisions > 0) axis->SetNdivisions(ndivisions);
}

inline TLine* DrawRatioRefLine(double xmin, double xmax, double y = 1.0,
                                int color = kRed, int style = 2) {
    TLine* line = new TLine(xmin, y, xmax, y);
    line->SetLineColor(color);
    line->SetLineStyle(style);
    line->Draw("same");
    return line;
}

// --------------------------------------------------------------------------
// Corner-safe annotation block
// --------------------------------------------------------------------------
struct CornerPreset { double x, yTop; int align; };

inline CornerPreset GetCornerPreset(Corner c) {
    switch (c) {
        case kTopRight:    return {0.93, 0.86, 31};
        case kTopLeft:     return {0.16, 0.86, 11};
        case kBottomRight: return {0.93, 0.22, 31};
        case kBottomLeft:  return {0.16, 0.22, 11};
    }
    return {0.93, 0.86, 31};
}

// Draws a stacked NDC text block: first line bold (font 62), remaining
// lines regular (font 42) -- the "MALTA2 Telescope @ PF-AR" / "MALTA2 XDPW
// Epi" pattern from the reference macros. Objects are drawn directly (ROOT
// keeps them alive on the pad until the canvas is deleted).
// yOffset shifts the whole block vertically in NDC (negative = down). The
// presets assume a full canvas; inside the main pad of a ratio layout the
// frame top sits at NDC 0.90 instead of ~0.94, so a top-corner block needs
// roughly -0.05 there or its first line collides with the frame border and
// the topmost y-axis tick label.
inline void DrawCornerLabel(TPad* pad, const std::vector<TString>& lines, Corner corner,
                             double headerSize = 0.042, double bodySize = 0.036,
                             double dy = 0.055, int color = kBlack,
                             double yOffset = 0.0) {
    pad->cd();
    CornerPreset p = GetCornerPreset(corner);
    p.yTop += yOffset;
    for (size_t i = 0; i < lines.size(); ++i) {
        TLatex* lat = new TLatex();
        lat->SetNDC();
        lat->SetTextAlign(p.align);
        lat->SetTextColor(color);
        if (i == 0) { lat->SetTextFont(62); lat->SetTextSize(headerSize); }
        else        { lat->SetTextFont(42); lat->SetTextSize(bodySize); }
        lat->DrawLatex(p.x, p.yTop - i * dy, lines[i]);
    }
}

// Heuristic corner picker for a TH1: scores each corner by the peak bin
// content in that x-third of the histogram (relative to the global max) and
// returns the emptiest one, so an annotation placed there won't cover data.
inline Corner PickLabelCorner(TH1* h, double frac = 0.30) {
    int nx = h->GetNbinsX();
    int nEdge = std::max(1, (int)(nx * frac));
    double yMax = h->GetMaximum();
    if (yMax <= 0) return kTopRight;

    double leftPeak = 0, rightPeak = 0;
    for (int b = 1; b <= nEdge; ++b) leftPeak = std::max(leftPeak, h->GetBinContent(b));
    for (int b = nx - nEdge + 1; b <= nx; ++b) rightPeak = std::max(rightPeak, h->GetBinContent(b));

    // Prefer top-* corners (most annotations sit near the top); choose left
    // vs right by whichever x-third has less data.
    return (rightPeak <= leftPeak) ? kTopRight : kTopLeft;
}

// Corner picker for an overlay of TGraphs (a scan plot: x = scan parameter,
// y = measured quantity). Unlike PickLabelCorner, a scan's points do not fill
// the pad the way a histogram's bins do, so each of the four corners is
// scored by how close the nearest data point is to it *in normalized (x,y)
// pad coordinates*; the corner whose nearest point is furthest away wins.
// This is what keeps the annotation off a monotonically rising or falling
// scan curve (e.g. resolution vs lever arm, where the data runs diagonally
// and exactly one pair of opposite corners is free).
inline Corner PickLabelCornerGraph(const std::vector<TGraph*>& graphs) {
    double xmin = 1e300, xmax = -1e300, ymin = 1e300, ymax = -1e300;
    for (TGraph* g : graphs) {
        if (!g) continue;
        for (int i = 0; i < g->GetN(); ++i) {
            double x, y;
            g->GetPoint(i, x, y);
            xmin = std::min(xmin, x); xmax = std::max(xmax, x);
            ymin = std::min(ymin, y); ymax = std::max(ymax, y);
        }
    }
    if (xmax <= xmin || ymax <= ymin) return kTopRight;

    // Corner anchors in normalized data coordinates, in Corner enum order.
    const double cx[4] = {1.0, 0.0, 1.0, 0.0};
    const double cy[4] = {1.0, 1.0, 0.0, 0.0};
    const Corner order[4] = {kTopRight, kTopLeft, kBottomRight, kBottomLeft};

    double best = -1.0;
    Corner bestCorner = kTopRight;
    for (int k = 0; k < 4; ++k) {
        double nearest = 1e300;
        for (TGraph* g : graphs) {
            if (!g) continue;
            for (int i = 0; i < g->GetN(); ++i) {
                double x, y;
                g->GetPoint(i, x, y);
                double nx = (x - xmin) / (xmax - xmin);
                double ny = (y - ymin) / (ymax - ymin);
                nearest = std::min(nearest, std::hypot(nx - cx[k], ny - cy[k]));
            }
        }
        if (nearest > best) { best = nearest; bestCorner = order[k]; }
    }
    return bestCorner;
}

// --------------------------------------------------------------------------
// Legend
// --------------------------------------------------------------------------
inline TLegend* MakeCleanLegend(double x1, double y1, double x2, double y2,
                                 double textSize = 0.032) {
    TLegend* leg = new TLegend(x1, y1, x2, y2);
    leg->SetBorderSize(0);
    leg->SetFillStyle(0);
    leg->SetTextSize(textSize);
    return leg;
}

// --------------------------------------------------------------------------
// Output
// --------------------------------------------------------------------------
inline void Save(TCanvas* c, const TString& outdir, const TString& basename) {
    gSystem->mkdir(outdir, kTRUE);
    TString outpdf = outdir + "/" + basename + ".pdf";
    TString outpng = outdir + "/" + basename + ".png";
    c->SaveAs(outpdf);
    c->SaveAs(outpng);
    std::cout << "[PlotStyle] Saved: " << outpdf << std::endl;
    std::cout << "[PlotStyle] Saved: " << outpng << std::endl;
}

}  // namespace PlotStyle