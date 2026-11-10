// Step 1 (mask): occupancy map + number of masked pixels per plane.
//   root -l -b -q 'plot_mask.C("output/.../mask.root", "output/.../mask", "20", "MALTA_0,MALTA_1,...")'
// Normally called by scripts/run_chain.sh.
#include "../../common/MacroUtils.h"

void plot_mask(TString rootFile, TString outDir, TString run, TString detList) {
    using namespace PlotStyle;
    SetGlobalStyle();
    TFile* f = MacroUtils::OpenOrDie(rootFile);
    const auto dets = MacroUtils::Split(detList);

    TCanvas* c = new TCanvas("c_mask_run" + run, "mask", 2000, 1000);
    c->Divide(4, 2);
    for (size_t i = 0; i < dets.size() && i < 8; ++i) {
        TPad* pad = static_cast<TPad*>(c->cd(i + 1));
        pad->SetRightMargin(0.16);
        pad->SetLeftMargin(0.12);
        TH2* occ = MacroUtils::Get<TH2>(f, "MaskCreator/" + dets[i] + "/occupancy");
        TH1* maskmap = MacroUtils::Get<TH1>(f, "MaskCreator/" + dets[i] + "/maskmap");
        if (!occ) continue;
        const long nMasked = maskmap ? (long)maskmap->GetEntries() : -1;
        occ->GetXaxis()->SetTitle("column");
        occ->GetYaxis()->SetTitle("row");
        StyleAxisFont43(occ->GetXaxis(), 16, 1.3, 13);
        StyleAxisFont43(occ->GetYaxis(), 16, 1.6, 13);
        occ->Draw("COLZ");
        // the maps are empty (white) outside the beam spot: black text stays legible there
        DrawCornerLabel(pad, {dets[i], Form("masked: %ld", nMasked)}, MacroUtils::PickLabelCorner2D(occ),
                        0.065, 0.055, 0.09, kBlack);
    }
    c->cd(0);
    Save(c, outDir, "run" + run + "_summary");
}
