// MacroUtils.h -- helpers shared by the Telescope/ and Imaging/ plotting macros
// (formerly Telescope/scripts/common.py + the PyROOT plot_style module).
#pragma once

#include "PlotStyle.h"

#include <TDirectory.h>
#include <TF1.h>
#include <TFile.h>
#include <TKey.h>
#include <TObjArray.h>
#include <TObjString.h>
#include <TROOT.h>
#include <TString.h>

#include <iostream>
#include <string>
#include <vector>

namespace MacroUtils {

// "MALTA_0,MALTA_1,..." -> {"MALTA_0", "MALTA_1", ...}
inline std::vector<TString> Split(const TString& s, const char* sep = ",") {
    std::vector<TString> out;
    TObjArray* tok = s.Tokenize(sep);
    for (int i = 0; i < tok->GetEntriesFast(); ++i) {
        TString t = static_cast<TObjString*>(tok->At(i))->String();
        t = t.Strip(TString::kBoth);
        if (t.Length()) out.push_back(t);
    }
    delete tok;
    return out;
}

inline TFile* OpenOrDie(const TString& path) {
    TFile* f = TFile::Open(path);
    if (!f || f->IsZombie()) {
        std::cerr << "ERROR: cannot open " << path << std::endl;
        gSystem->Exit(1);
    }
    return f;
}

// Object by path, nullptr (with a warning) if missing.
template <class T = TObject>
T* Get(TDirectory* d, const TString& path, bool warn = true) {
    T* obj = d ? dynamic_cast<T*>(d->Get(path)) : nullptr;
    if (!obj && warn) std::cout << "  [warn] not found: " << path << std::endl;
    return obj;
}

// First object in a directory whose key name starts with prefix.
inline TObject* FindByPrefix(TDirectory* d, const TString& prefix) {
    if (!d) return nullptr;
    TIter next(d->GetListOfKeys());
    while (TKey* key = static_cast<TKey*>(next())) {
        if (TString(key->GetName()).BeginsWith(prefix)) return key->ReadObj();
    }
    return nullptr;
}

struct GausFit {
    bool ok = false;
    double mean = 0, meanErr = 0, sigma = 0, sigmaErr = 0;
    TF1* func = nullptr;
};

// Gaussian fit around a 1D histogram's peak, window mean +/- nSigma * RMS. The TF1 stays attached
// to the histogram (and is returned) so it can be drawn with it.
inline GausFit FitGaussian(TH1* h, double nSigma = 2.5, const char* options = "QR0") {
    GausFit r;
    if (!h || h->GetEntries() == 0) return r;
    double mean0 = h->GetMean(), rms0 = h->GetRMS();
    if (rms0 <= 0) rms0 = h->GetXaxis()->GetBinWidth(1) * 5;
    const double lo = mean0 - nSigma * rms0, hi = mean0 + nSigma * rms0;
    r.func = new TF1(Form("f_%s_gaus", h->GetName()), "gaus", lo, hi);
    r.func->SetLineWidth(2);
    h->Fit(r.func, options, "", lo, hi);
    r.ok = true;
    r.mean = r.func->GetParameter(1);
    r.meanErr = r.func->GetParError(1);
    r.sigma = r.func->GetParameter(2);
    r.sigmaErr = r.func->GetParError(2);
    return r;
}

// Same idea as PlotStyle::PickLabelCorner, for a TH2 map: the corner quadrant (frac x frac of the
// map) with the lowest mean content.
inline PlotStyle::Corner PickLabelCorner2D(TH2* h, double frac = 0.30) {
    const int nx = h->GetNbinsX(), ny = h->GetNbinsY();
    const int ex = std::max(1, (int)(nx * frac)), ey = std::max(1, (int)(ny * frac));
    auto mean = [&](int x0, int x1, int y0, int y1) {
        double s = 0;
        int n = 0;
        for (int i = x0; i <= x1; ++i)
            for (int j = y0; j <= y1; ++j) { s += h->GetBinContent(i, j); ++n; }
        return n ? s / n : 0.0;
    };
    const double score[4] = {mean(nx - ex + 1, nx, ny - ey + 1, ny), mean(1, ex, ny - ey + 1, ny),
                             mean(nx - ex + 1, nx, 1, ey), mean(1, ex, 1, ey)};
    const PlotStyle::Corner order[4] = {PlotStyle::kTopRight, PlotStyle::kTopLeft,
                                        PlotStyle::kBottomRight, PlotStyle::kBottomLeft};
    int best = 0;
    for (int k = 1; k < 4; ++k)
        if (score[k] < score[best]) best = k;
    return order[best];
}

inline bool IsLeft(PlotStyle::Corner c) { return c == PlotStyle::kTopLeft || c == PlotStyle::kBottomLeft; }

// Draw a residual/correlation pair x (blue) + y (green) with their Gaussian fits (red, solid/dashed)
// and zoom the x axis to the peak (+/- max(8 sigma, minHalfWindow)). Returns the fits.
inline std::pair<GausFit, GausFit> DrawXYPair(TH1* hx, TH1* hy, const char* xtitle, const char* ytitle,
                                              double minHalfWindow) {
    hx->SetLineColor(kBlue + 2);
    hx->SetLineWidth(2);
    hx->GetXaxis()->SetTitle(xtitle);
    hx->GetYaxis()->SetTitle(ytitle);
    PlotStyle::StyleAxisFont43(hx->GetXaxis(), 16, 1.3, 13);
    PlotStyle::StyleAxisFont43(hx->GetYaxis(), 16, 1.8, 13);

    GausFit fx = FitGaussian(hx), fy = FitGaussian(hy);
    std::vector<double> centers, widths;
    for (const GausFit* f : {&fx, &fy})
        if (f->ok) { centers.push_back(f->mean); widths.push_back(f->sigma); }
    if (!centers.empty()) {
        double c = 0;
        for (double v : centers) c += v;
        c /= centers.size();
        const double hw = std::max(8 * *std::max_element(widths.begin(), widths.end()), minHalfWindow);
        hx->GetXaxis()->SetRangeUser(c - hw, c + hw);
    }
    hx->SetMaximum(std::max(hx->GetMaximum(), hy->GetMaximum()) * 1.1);
    hx->Draw("HIST");
    if (fx.ok) { fx.func->SetLineColor(kRed + 1); fx.func->SetLineStyle(1); fx.func->Draw("same"); }
    hy->SetLineColor(kGreen + 2);
    hy->SetLineWidth(2);
    hy->Draw("HIST same");
    if (fy.ok) { fy.func->SetLineColor(kRed + 1); fy.func->SetLineStyle(2); fy.func->Draw("same"); }
    return {fx, fy};
}

}  // namespace MacroUtils
