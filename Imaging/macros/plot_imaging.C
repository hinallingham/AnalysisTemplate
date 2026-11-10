// Plots for the material-budget imaging step (output/<setup>/imaging/imaging_run<N>.root):
//
//   <prefix>_image      kink-angle width per image cell (AnalysisMaterialBudget MBISqrt)
//   <prefix>_tracks     multiplets per cell (from the MBIpreview profile)
//   <prefix>_xprofile   image rows through y bands (default: the two MLCC capacitor rows), vs x
//   <prefix>_kink       kink-angle distribution at the scatterer, x and y
//
//   root -l -b -q 'plot_imaging.C("imaging_run2.root", "outdir", "2")'
//   root -l -b -q 'plot_imaging.C("imaging_run2.root", "outdir", "2", "MLCC_run2", "1.9,-1.9", true)'
// args: root file, output dir, run, file-name prefix ("" = MLCC_run<run>), y [mm] of the x-profile
// bands (comma separated), sim (label "(sim.)"). Normally called by scripts/run_imaging.sh.
#include "ImagingUtils.h"

#include <TProfile2D.h>

void plot_imaging(TString rootFile, TString outDir, TString run, TString prefix = "",
                  TString rowList = "1.9,-1.9", bool sim = false) {
    using namespace PlotStyle;
    if (prefix == "") prefix = "MLCC_run" + run;
    const TString header = TString("MALTA2 Telescope") + (sim ? " (sim.)" : "");
    SetGlobalStyle(kInvertedDarkBodyRadiator);
    TFile* f = MacroUtils::OpenOrDie(rootFile);
    TDirectory* amb = MacroUtils::Get<TDirectory>(f, "AnalysisMaterialBudget");
    TH2* raw = MacroUtils::Get<TH2>(amb, "MBISqrt");
    if (!raw) gSystem->Exit(1);

    // --- image: AAD of the central 90% of kink angles (x and y pooled), per cell
    TH2D* img = ImagingUtils::Shifted(raw, "img");
    const auto filled = ImagingUtils::FilledSorted(img);
    if (filled.empty()) {
        std::cerr << "MBISqrt is empty: not enough multiplets per cell (min_cell_content)" << std::endl;
        gSystem->Exit(1);
    }
    const double zmin = filled[int(0.01 * filled.size())], zmax = filled[int(0.995 * filled.size()) - 1];
    TCanvas* c = ImagingUtils::MapCanvas("c_image", img, "kink width (AAD, 90%) [mrad]", zmin * 0.95, zmax);
    TLatex lat;  // label in the top margin: the image fills the whole frame
    lat.SetNDC();
    lat.SetTextSize(0.04);
    const int cellUm = std::lround(img->GetXaxis()->GetBinWidth(1) * 1e3);
    lat.DrawLatex(0.07, 0.94, Form("#font[62]{%s}  run %s, 3 GeV e^{-}, %d #mum cells", header.Data(), run.Data(), cellUm));
    Save(c, outDir, prefix + "_image");

    // --- multiplets per cell (bin entries of the kink^2 profile count x and y separately)
    if (TProfile2D* prof = MacroUtils::Get<TProfile2D>(amb, "MBIpreview")) {
        TH2D* trk = new TH2D("trk", "", prof->GetNbinsX(), prof->GetXaxis()->GetXmin(), prof->GetXaxis()->GetXmax(),
                             prof->GetNbinsY(), prof->GetYaxis()->GetXmin(), prof->GetYaxis()->GetXmax());
        trk->SetDirectory(nullptr);
        for (int ix = 1; ix <= prof->GetNbinsX(); ++ix)
            for (int iy = 1; iy <= prof->GetNbinsY(); ++iy)
                trk->SetBinContent(ix, iy, prof->GetBinEntries(prof->GetBin(ix, iy)) / 2);
        Save(ImagingUtils::MapCanvas("c_tracks", trk, "multiplets / cell"), outDir, prefix + "_tracks");
    }

    // --- x profiles through y bands: mean image value over |y - y0| < 0.2 mm
    const auto rows = MacroUtils::Split(rowList);
    const int colors[3] = {kAzure + 2, kOrange + 7, kGreen + 2};
    TCanvas* c3 = new TCanvas("c_xprof", "c_xprof", 1100, 600);
    c3->SetLeftMargin(0.11);
    c3->SetRightMargin(0.04);
    c3->SetBottomMargin(0.13);
    TLegend* leg = MakeCleanLegend(0.13, 0.72, 0.45, 0.88, 0.040);
    std::vector<TH1D*> profs;
    double hmax = 0;
    for (size_t k = 0; k < rows.size(); ++k) {
        const double y0 = rows[k].Atof();
        TH1D* hp = new TH1D(Form("xprof%zu", k), "", img->GetNbinsX(), img->GetXaxis()->GetXmin(), img->GetXaxis()->GetXmax());
        hp->SetDirectory(nullptr);
        for (int i = 1; i <= img->GetNbinsX(); ++i) {
            std::vector<double> v;
            for (int j = 1; j <= img->GetNbinsY(); ++j)
                if (std::abs(img->GetYaxis()->GetBinCenter(j) - y0) < 0.2 && img->GetBinContent(i, j) > 0)
                    v.push_back(img->GetBinContent(i, j));
            if (v.empty()) continue;
            double m = 0, s2 = 0;
            for (double x : v) m += x;
            m /= v.size();
            for (double x : v) s2 += (x - m) * (x - m);
            hp->SetBinContent(i, m);
            hp->SetBinError(i, std::sqrt(s2 / v.size()) / std::sqrt(v.size()));
        }
        hp->SetLineColor(colors[k % 3]);
        hp->SetMarkerColor(colors[k % 3]);
        hp->SetMarkerStyle(20);
        hp->SetMarkerSize(0.6);
        hp->SetLineWidth(2);
        hmax = std::max(hmax, hp->GetMaximum());
        profs.push_back(hp);
        leg->AddEntry(hp, Form("|y - (%+.1f mm)| < 0.2 mm", y0), "lp");
    }
    for (size_t k = 0; k < profs.size(); ++k) {
        TH1D* hp = profs[k];
        hp->SetMaximum(hmax * 1.35);
        hp->SetMinimum(0);
        hp->GetXaxis()->SetTitle("x at scatterer [mm]");
        hp->GetYaxis()->SetTitle("kink width (AAD, 90%) [mrad]");
        for (TAxis* ax : {hp->GetXaxis(), hp->GetYaxis()}) { ax->SetTitleSize(0.05); ax->SetLabelSize(0.045); }
        hp->Draw(k == 0 ? "E1" : "E1 SAME");
    }
    leg->Draw();
    DrawCornerLabel(c3, {header, "run " + run}, PlotStyle::kTopRight);
    Save(c3, outDir, prefix + "_xprofile");

    // --- kink-angle distributions
    TCanvas* c4 = new TCanvas("c_kink", "c_kink", 900, 640);
    c4->SetLogy();
    c4->SetLeftMargin(0.13);
    c4->SetBottomMargin(0.13);
    TLegend* leg4 = MakeCleanLegend(0.16, 0.75, 0.45, 0.88, 0.040);
    const char* axes[2] = {"X", "Y"};
    const int kcol[2] = {kAzure + 2, kOrange + 7};
    for (int k = 0; k < 2; ++k) {
        TH1* h0 = MacroUtils::Get<TH1>(f, Form("TrackingMultiplet/multipletKinkAtScatterer%s", axes[k]));
        if (!h0) continue;
        // 0.05 mrad bins resolve the pixel quantisation of the arm slopes (comb pattern): x4
        TH1* h = h0->Rebin(4, Form("kink%s", axes[k]));
        h->SetLineColor(kcol[k]);
        h->SetLineWidth(2);
        h->GetXaxis()->SetTitle("kink angle at scatterer [mrad]");
        h->GetYaxis()->SetTitle("multiplets");
        h->GetXaxis()->SetTitleSize(0.05);
        h->GetYaxis()->SetTitleSize(0.05);
        h->Draw(k == 0 ? "HIST" : "HIST SAME");
        leg4->AddEntry(h, Form("kink %s  (RMS %.2f mrad)", k == 0 ? "x" : "y", h->GetRMS()), "l");
    }
    leg4->Draw();
    DrawCornerLabel(c4, {header, "run " + run}, PlotStyle::kTopRight);
    Save(c4, outDir, prefix + "_kink");
}
