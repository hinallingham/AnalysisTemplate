// Step 3 (align, Millepede on the reference planes): track chi2/ndof as a quick fit-quality check.
// The residual plots are made by plot_analysis.C against the final aligned_dut geometry.
//   root -l -b -q 'plot_align.C("align.root", "outdir", "20")'
#include "../../common/MacroUtils.h"

void plot_align(TString rootFile, TString outDir, TString run) {
    using namespace PlotStyle;
    SetGlobalStyle();
    TFile* f = MacroUtils::OpenOrDie(rootFile);

    TCanvas* c = new TCanvas("c_align_run" + run, "align", 900, 700);
    if (TH1* chi2 = MacroUtils::Get<TH1>(f, "Tracking4D/trackChi2ndof")) {
        chi2->SetLineColor(kBlue + 2);
        chi2->SetLineWidth(2);
        chi2->GetXaxis()->SetTitle("#chi^{2}/ndof");
        chi2->GetYaxis()->SetTitle("tracks");
        StyleAxisFont43(chi2->GetXaxis(), 20, 1.6, 17);
        StyleAxisFont43(chi2->GetYaxis(), 20, 1.4, 17);
        chi2->Draw("HIST");
        DrawCornerLabel(c, {"trackChi2ndof", Form("mean = %.2f", chi2->GetMean())}, PlotStyle::kTopRight, 0.045, 0.038);
    }
    Save(c, outDir, "run" + run + "_summary");
}
