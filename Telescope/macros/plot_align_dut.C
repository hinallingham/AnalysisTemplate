// Step 4 (align_dut, AlignmentDUTResidual): per-iteration convergence of the DUT corrections.
//   root -l -b -q 'plot_align_dut.C("align_dut.root", "outdir", "20", "MALTA_3")'
#include "../../common/MacroUtils.h"

#include <TGraph.h>

void plot_align_dut(TString rootFile, TString outDir, TString run, TString dut) {
    using namespace PlotStyle;
    SetGlobalStyle();
    TFile* f = MacroUtils::OpenOrDie(rootFile);
    // DUT-type module: per-detector subdirectory, else the module's top-level directory
    TDirectory* dir = MacroUtils::Get<TDirectory>(f, "AlignmentDUTResidual/" + dut, false);
    if (!dir) dir = MacroUtils::Get<TDirectory>(f, "AlignmentDUTResidual");

    const std::vector<std::pair<TString, TString>> specs = {
        {"alignment_correction_displacementX_", "shift X [#mum]"},
        {"alignment_correction_displacementY_", "shift Y [#mum]"},
        {"alignment_correction_rotation0_", "rot 0 [deg]"},
        {"alignment_correction_rotation1_", "rot 1 [deg]"},
        {"alignment_correction_rotation2_", "rot 2 [deg]"},
    };
    TCanvas* c = new TCanvas("c_align_dut_run" + run, "align_dut", 1500, 1000);
    c->Divide(3, 2);
    for (size_t i = 0; i < specs.size(); ++i) {
        TPad* pad = static_cast<TPad*>(c->cd(i + 1));
        pad->SetLeftMargin(0.16);
        TGraph* g = dynamic_cast<TGraph*>(MacroUtils::FindByPrefix(dir, specs[i].first));
        if (!g) { std::cout << "  [warn] not found: " << specs[i].first << "*" << std::endl; continue; }
        g->SetMarkerStyle(20);
        g->SetMarkerColor(kBlue + 2);
        g->SetLineColor(kBlue + 2);
        g->SetLineWidth(2);
        g->GetXaxis()->SetTitle("iteration");
        StyleAxisFont43(g->GetXaxis(), 16, 1.3, 13);
        StyleAxisFont43(g->GetYaxis(), 16, 1.8, 13);
        g->Draw("APL");
        DrawCornerLabel(pad, {specs[i].second}, PlotStyle::kTopRight, 0.06);
    }
    c->cd(0);
    Save(c, outDir, "run" + run + "_summary");
}
