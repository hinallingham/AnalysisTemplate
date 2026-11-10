// ImagingUtils.h -- pieces shared by plot_imaging.C and calibrate_xx0.C
#pragma once

#include "../../common/MacroUtils.h"

#include <TH2D.h>
#include <TProfile2D.h>

namespace ImagingUtils {

// AnalysisMaterialBudget fills its maps with SetBinContent(cell_x, cell_y) for 0-based cell indices,
// i.e. one bin too low in x and y (cell 0 ends up in the underflow): copy with contents moved up by one.
inline TH2D* Shifted(TH2* raw, const char* name) {
    TH2D* h = new TH2D(name, "", raw->GetNbinsX(), raw->GetXaxis()->GetXmin(), raw->GetXaxis()->GetXmax(),
                       raw->GetNbinsY(), raw->GetYaxis()->GetXmin(), raw->GetYaxis()->GetXmax());
    h->SetDirectory(nullptr);
    for (int ix = 1; ix <= raw->GetNbinsX(); ++ix)
        for (int iy = 1; iy <= raw->GetNbinsY(); ++iy) h->SetBinContent(ix, iy, raw->GetBinContent(ix - 1, iy - 1));
    return h;
}

// Canvas sized to the map's aspect ratio, COLZ, common axis styling.
inline TCanvas* MapCanvas(const char* name, TH2* h, const char* ztitle, double zmin = NAN, double zmax = NAN) {
    const double nx = h->GetXaxis()->GetXmax() - h->GetXaxis()->GetXmin();
    const double ny = h->GetYaxis()->GetXmax() - h->GetYaxis()->GetXmin();
    TCanvas* c = new TCanvas(name, name, 1400, int(1400 * ny / nx * 0.86) + 120);
    c->SetLeftMargin(0.07);
    c->SetRightMargin(0.13);
    c->SetTopMargin(0.08);
    c->SetBottomMargin(0.13);
    h->GetXaxis()->SetTitle("x at scatterer [mm]");
    h->GetYaxis()->SetTitle("y at scatterer [mm]");
    h->GetZaxis()->SetTitle(ztitle);
    h->GetYaxis()->SetTitleOffset(0.6);
    h->GetZaxis()->SetTitleOffset(0.8);
    for (TAxis* ax : {h->GetXaxis(), h->GetYaxis(), h->GetZaxis()}) {
        ax->SetTitleSize(0.05);
        ax->SetLabelSize(0.045);
    }
    if (!std::isnan(zmin)) h->SetMinimum(zmin);
    if (!std::isnan(zmax)) h->SetMaximum(zmax);
    h->Draw("COLZ");
    return c;
}

// Sorted contents of the filled (> 0) bins.
inline std::vector<double> FilledSorted(TH2* h) {
    std::vector<double> v;
    for (int i = 1; i <= h->GetNbinsX(); ++i)
        for (int j = 1; j <= h->GetNbinsY(); ++j)
            if (h->GetBinContent(i, j) > 0) v.push_back(h->GetBinContent(i, j));
    std::sort(v.begin(), v.end());
    return v;
}

}  // namespace ImagingUtils
