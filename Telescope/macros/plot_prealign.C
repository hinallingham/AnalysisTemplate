// Step 2 (prealign): X/Y correlation peak of every plane with a Gaussian fit = the shift applied.
//   root -l -b -q 'plot_prealign.C("prealign.root", "outdir", "20", "MALTA_0,...", "MALTA_3")'
#include "../../common/MacroUtils.h"

void plot_prealign(TString rootFile, TString outDir, TString run, TString detList, TString dut) {
    using namespace PlotStyle;
    SetGlobalStyle();
    TFile* f = MacroUtils::OpenOrDie(rootFile);
    const auto dets = MacroUtils::Split(detList);

    TCanvas* c = new TCanvas("c_prealign_run" + run, "prealign", 2000, 1000);
    c->Divide(4, 2);
    for (size_t i = 0; i < dets.size() && i < 8; ++i) {
        TPad* pad = static_cast<TPad*>(c->cd(i + 1));
        pad->SetLeftMargin(0.13);
        TH1* hx = MacroUtils::Get<TH1>(f, "Prealignment/" + dets[i] + "/correlationX");
        TH1* hy = MacroUtils::Get<TH1>(f, "Prealignment/" + dets[i] + "/correlationY");
        if (!hx || !hy) continue;
        // zoom to the peak: the default +/-10 mm range hides a sub-mm shift
        auto [fx, fy] = MacroUtils::DrawXYPair(hx, hy, "residual [mm]", "clusters", 0.3);

        std::vector<TString> lines = {dets[i] + (dets[i] == dut ? " (fixed)" : "")};
        if (fx.ok) lines.push_back(Form("X = %.3f #pm %.3f mm", fx.mean, fx.meanErr));
        if (fy.ok) lines.push_back(Form("Y = %.3f #pm %.3f mm", fy.mean, fy.meanErr));
        DrawCornerLabel(pad, lines, PickLabelCorner(hx), 0.065, 0.055, 0.09);

        if (fx.ok) printf("%s: X shift = %+.4f +/- %.4f mm (sigma %.4f mm)\n", dets[i].Data(), fx.mean, fx.meanErr, fx.sigma);
        if (fy.ok) printf("%s: Y shift = %+.4f +/- %.4f mm (sigma %.4f mm)\n", dets[i].Data(), fy.mean, fy.meanErr, fy.sigma);
    }
    c->cd(0);
    Save(c, outDir, "run" + run + "_summary");
}
