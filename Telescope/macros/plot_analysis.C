// Step 5 (analysis): DUT efficiency (map + total) and the residual confirmation plots against the
// final aligned_dut geometry (reference-plane global residuals from Tracking4D, DUT residuals from
// AnalysisDUT). Extend this together with config/analysis.conf as the analysis grows.
//   root -l -b -q 'plot_analysis.C("analysis.root", "outdir", "20", "MALTA_0,...", "MALTA_3")'
// Output: run<N>_summary.{pdf,png}, run<N>_residuals.{pdf,png}
#include "../../common/MacroUtils.h"

#include <TEfficiency.h>

static void plot_efficiency(TFile* f, const TString& outDir, const TString& run, const TString& dut) {
    using namespace PlotStyle;
    TCanvas* c = new TCanvas("c_analysis_run" + run, "analysis", 1400, 650);
    c->Divide(2, 1);

    TPad* pad = static_cast<TPad*>(c->cd(1));
    pad->SetRightMargin(0.16);
    if (auto* emap = MacroUtils::Get<TEfficiency>(f, "AnalysisEfficiency/" + dut + "/chipEfficiencyMap_trackPos")) {
        TH2* h2 = static_cast<TH2*>(const_cast<TH1*>(emap->GetTotalHistogram()));
        emap->Draw("COLZ");
        pad->Update();
        if (TH2* painted = emap->GetPaintedHistogram()) {
            painted->GetXaxis()->SetTitle("column");
            painted->GetYaxis()->SetTitle("row");
            StyleAxisFont43(painted->GetXaxis(), 16, 1.3, 13);
            StyleAxisFont43(painted->GetYaxis(), 16, 1.8, 13);
        }
        DrawCornerLabel(pad, {dut + " chip efficiency"}, MacroUtils::PickLabelCorner2D(h2), 0.045, 0.036, 0.055, kBlack);
    }

    c->cd(2);
    if (auto* etot = MacroUtils::Get<TEfficiency>(f, "AnalysisEfficiency/" + dut + "/eTotalEfficiency")) {
        const double eff = etot->GetEfficiency(1), lo = etot->GetEfficiencyErrorLow(1), hi = etot->GetEfficiencyErrorUp(1);
        TLatex t;
        t.SetNDC();
        t.SetTextAlign(22);
        t.SetTextFont(62);
        t.SetTextSize(0.05);
        t.DrawLatex(0.5, 0.75, dut + " total efficiency");
        t.SetTextSize(0.09);
        t.DrawLatex(0.5, 0.55, Form("%.2f %%", eff * 100));
        t.SetTextFont(42);
        t.SetTextSize(0.045);
        t.DrawLatex(0.5, 0.42, Form("+%.2f / -%.2f %%", hi * 100, lo * 100));
        printf("%s total efficiency: %.2f %% (+%.2f/-%.2f)\n", dut.Data(), eff * 100, hi * 100, lo * 100);
    }
    c->cd(0);
    Save(c, outDir, "run" + run + "_summary");
}

static void plot_residuals(TFile* f, const TString& outDir, const TString& run,
                           const std::vector<TString>& dets, const TString& dut) {
    using namespace PlotStyle;
    // only the planes Tracking4D actually used (e.g. 3 for analysis_upstream3.conf): the
    // Tracking4D/<det> directories exist for every plane, so check the entries
    std::vector<TString> refs;
    for (const auto& d : dets) {
        if (d == dut) continue;
        TH1* h = MacroUtils::Get<TH1>(f, "Tracking4D/" + d + "/global_residuals/GlobalResidualsX", false);
        if (h && h->GetEntries() > 0) refs.push_back(d);
    }

    TCanvas* c = new TCanvas("c_residuals_run" + run, "residuals", 1900, 1500);
    c->Divide(3, 3);

    TPad* pad = static_cast<TPad*>(c->cd(1));
    if (TH1* chi2 = MacroUtils::Get<TH1>(f, "Tracking4D/trackChi2ndof")) {
        chi2->SetLineColor(kBlue + 2);
        chi2->SetLineWidth(2);
        chi2->GetXaxis()->SetTitle("#chi^{2}/ndof");
        chi2->GetYaxis()->SetTitle("tracks");
        StyleAxisFont43(chi2->GetXaxis(), 16, 1.3, 13);
        StyleAxisFont43(chi2->GetYaxis(), 16, 1.8, 13);
        chi2->Draw("HIST");
        DrawCornerLabel(pad, {"trackChi2ndof", Form("mean = %.2f", chi2->GetMean())}, PlotStyle::kTopRight, 0.06, 0.05);
    }

    for (size_t i = 0; i < refs.size() && i < 6; ++i) {
        const TString& det = refs[i];
        pad = static_cast<TPad*>(c->cd(i + 2));
        pad->SetLeftMargin(0.13);
        TH1* hx = MacroUtils::Get<TH1>(f, "Tracking4D/" + det + "/global_residuals/GlobalResidualsX");
        TH1* hy = MacroUtils::Get<TH1>(f, "Tracking4D/" + det + "/global_residuals/GlobalResidualsY");
        if (!hx || !hy) continue;
        auto [fx, fy] = MacroUtils::DrawXYPair(hx, hy, "residual [mm]", "tracks", 0.05);

        std::vector<TString> lines = {det};
        if (fx.ok) lines.push_back(Form("#sigma_{x} = %.3f #pm %.3f #mum", fx.sigma * 1000, fx.sigmaErr * 1000));
        if (fy.ok) lines.push_back(Form("#sigma_{y} = %.3f #pm %.3f #mum", fy.sigma * 1000, fy.sigmaErr * 1000));
        const Corner corner = PickLabelCorner(hx);
        DrawCornerLabel(pad, lines, corner, 0.065, 0.055, 0.09);
        const bool left = MacroUtils::IsLeft(corner);
        TLegend* leg = MakeCleanLegend(left ? 0.62 : 0.14, 0.80, left ? 0.90 : 0.42, 0.93, 0.05);
        leg->AddEntry(hx, "x", "l");
        leg->AddEntry(hy, "y", "l");
        leg->Draw();

        if (fx.ok) printf("%s: X residual mean %+.3f um, sigma %.3f +/- %.3f um\n", det.Data(), fx.mean * 1000, fx.sigma * 1000, fx.sigmaErr * 1000);
        if (fy.ok) printf("%s: Y residual mean %+.3f um, sigma %.3f +/- %.3f um\n", det.Data(), fy.mean * 1000, fy.sigma * 1000, fy.sigmaErr * 1000);
    }

    const char* names[2] = {"residualsX", "residualsY"};
    const char* axes[2] = {"x", "y"};
    for (int k = 0; k < 2; ++k) {
        pad = static_cast<TPad*>(c->cd(8 + k));
        pad->SetLeftMargin(0.14);
        TH1* h = MacroUtils::Get<TH1>(f, "AnalysisDUT/" + dut + "/global_residuals/" + names[k]);
        if (!h) continue;
        h->SetLineColor(kBlue + 2);
        h->SetLineWidth(2);
        h->GetXaxis()->SetTitle(Form("%s_{track} - %s [#mum]", axes[k], axes[k]));
        h->GetYaxis()->SetTitle("associated clusters");
        StyleAxisFont43(h->GetXaxis(), 16, 1.3, 13);
        StyleAxisFont43(h->GetYaxis(), 16, 1.8, 13);
        MacroUtils::GausFit fit = MacroUtils::FitGaussian(h);
        if (fit.ok) {
            const double hw = std::max(8 * fit.sigma, 20.0);
            h->GetXaxis()->SetRangeUser(fit.mean - hw, fit.mean + hw);
        }
        h->Draw("HIST");
        if (fit.ok) {
            fit.func->SetLineColor(kRed + 1);
            fit.func->Draw("same");
            DrawCornerLabel(pad, {dut, Form("mean = %.2f #pm %.2f #mum", fit.mean, fit.meanErr),
                                  Form("sigma = %.2f #pm %.2f #mum", fit.sigma, fit.sigmaErr)},
                            PickLabelCorner(h), 0.06, 0.05, 0.09);
            printf("%s: %s residual mean %+.2f um, sigma %.2f um\n", dut.Data(), axes[k], fit.mean, fit.sigma);
        }
    }
    c->cd(0);
    Save(c, outDir, "run" + run + "_residuals");
}

void plot_analysis(TString rootFile, TString outDir, TString run, TString detList, TString dut) {
    PlotStyle::SetGlobalStyle();
    TFile* f = MacroUtils::OpenOrDie(rootFile);
    plot_efficiency(f, outDir, run, dut);
    plot_residuals(f, outDir, run, MacroUtils::Split(detList), dut);
}
