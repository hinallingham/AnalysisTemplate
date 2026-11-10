// [simulation only] DUT residual width vs A = B for one or more ABscans (C fixed per scan):
// Gaussian-fit sigma of the AnalysisDUT global residuals, 6-plane tracking vs upstream-3 tracking.
// With one C, x and y share one pad; with several C, x and y get a pad each and the C values are
// overlaid in both. The fit is MacroUtils::FitGaussian (window mean +/- 2.5 RMS), the same as in
// plot_analysis.C, so the numbers match the per-run residual plots.
//
// Normally called by scripts/plot_ABscan_sigma.sh, which builds the run table:
//   scans = "ABscan_C1p5|1.5|15:1.5,20:2,...;ABscan_C5|5|50015:1.5,..."   (scan|C [cm]|run:A=B [cm],...)
// Reads <telOutDir>/<scan>/run<NNN>/{analysis,analysis_upstream3}/*.root
// Writes <outDir>/<basename>.{pdf,png,json}
#include "../../common/MacroUtils.h"

#include <TGraphErrors.h>

#include <fstream>
#include <map>

namespace {
struct Point { double s; int run; MacroUtils::GausFit fit; };
struct Scan { TString name; double c; std::vector<std::pair<int, double>> runs; };

const char* kTrkKey[2] = {"6plane", "upstream3"};
const char* kTrkDir[2] = {"analysis", "analysis_upstream3"};
const char* kTrkLabel[2] = {"6-plane tracking (RP1-6)", "upstream 3-plane tracking (RP1-3)"};
const int kTrkColor[2] = {kBlue + 2, kRed + 1};
const char* kAxes[2] = {"X", "Y"};
// closed/solid = first, open/dashed = second: per C, or per axis for one C
const int kSeriesMarker[4] = {20, 24, 21, 25};
const int kSeriesLine[4] = {1, 2, 3, 4};

TGraphErrors* make_graph(const std::vector<Point>& pts, int color, int marker, int line) {
    TGraphErrors* g = new TGraphErrors();
    for (const auto& p : pts) { g->SetPoint(g->GetN(), p.s, p.fit.sigma); g->SetPointError(g->GetN() - 1, 0, p.fit.sigmaErr); }
    g->SetMarkerStyle(marker);
    g->SetMarkerSize(1.3);
    g->SetMarkerColor(color);
    g->SetLineColor(color);
    g->SetLineStyle(line);
    g->SetLineWidth(2);
    return g;
}

void draw_pad(TPad* pad, const std::vector<std::pair<TGraphErrors*, TString>>& series, double xmax, double ymax,
              const TString& sub, double legSize, double x1, double y1, double x2, double y2) {
    using namespace PlotStyle;
    pad->cd();
    pad->SetMargin(0.13, 0.05, 0.13, 0.05);
    pad->SetGridy();
    TH1F* frame = pad->DrawFrame(0.0, 0.0, xmax, ymax);
    frame->GetXaxis()->SetTitle("A = B [cm]");
    frame->GetYaxis()->SetTitle("DUT residual #sigma_{Gauss} [#mum]");
    StyleAxisFont43(frame->GetXaxis(), 22, 1.3, 19);
    StyleAxisFont43(frame->GetYaxis(), 22, 1.4, 19);
    std::vector<TGraph*> graphs;
    for (auto& [g, t] : series) { g->Draw("PL same"); graphs.push_back(g); }
    Corner corner = PickLabelCornerGraph(graphs);
    if (corner == PlotStyle::kBottomRight) corner = PlotStyle::kTopRight;  // only top corners: the legend sits at the bottom
    if (corner == PlotStyle::kBottomLeft) corner = PlotStyle::kTopLeft;
    DrawCornerLabel(pad, {"MALTA2 telescope, Allpix^{2} simulation", sub}, corner, 0.040, 0.034);
    TLegend* leg = MakeCleanLegend(x1, y1, x2, y2, legSize);
    for (auto& [g, t] : series) leg->AddEntry(g, t, "pl");
    leg->Draw();
}
}  // namespace

void plot_ABscan_sigma(TString telOutDir, TString outDir, TString scanSpec, TString dut = "MALTA_3") {
    PlotStyle::SetGlobalStyle();
    std::vector<Scan> scans;
    for (const TString& s : MacroUtils::Split(scanSpec, ";")) {
        const auto parts = MacroUtils::Split(s, "|");
        if (parts.size() != 3) { std::cerr << "bad scan spec: " << s << std::endl; gSystem->Exit(1); }
        Scan sc{parts[0], parts[1].Atof(), {}};
        for (const TString& rs : MacroUtils::Split(parts[2], ",")) {
            const auto r = MacroUtils::Split(rs, ":");
            sc.runs.push_back({r[0].Atoi(), r[1].Atof()});
        }
        scans.push_back(sc);
    }

    // values[scan][tracking][axis]
    std::vector<std::vector<std::vector<std::vector<Point>>>> values(scans.size(),
        std::vector<std::vector<std::vector<Point>>>(2, std::vector<std::vector<Point>>(2)));
    double xmax = 0, ymax = 0;
    for (size_t is = 0; is < scans.size(); ++is)
        for (int t = 0; t < 2; ++t)
            for (const auto& [run, s] : scans[is].runs) {
                const TString path = Form("%s/%s/run%03d/%s/%s.root", telOutDir.Data(), scans[is].name.Data(), run, kTrkDir[t], kTrkDir[t]);
                if (gSystem->AccessPathName(path)) { std::cout << "  [warn] missing " << path << ", skipped" << std::endl; continue; }
                TFile* f = TFile::Open(path);
                for (int a = 0; a < 2; ++a) {
                    TH1* h = MacroUtils::Get<TH1>(f, "AnalysisDUT/" + dut + "/global_residuals/residuals" + kAxes[a]);
                    MacroUtils::GausFit fit = MacroUtils::FitGaussian(h);
                    if (!fit.ok) continue;
                    values[is][t][a].push_back({s, run, fit});
                    xmax = std::max(xmax, s);
                    ymax = std::max(ymax, fit.sigma);
                }
            }
    if (ymax <= 0) { std::cerr << "no results found" << std::endl; gSystem->Exit(1); }
    xmax *= 1.08;
    ymax *= scans.size() == 1 ? 1.45 : 1.6;

    TCanvas* c;
    if (scans.size() == 1) {
        c = new TCanvas("c_sigma_vs_AB", "", 900, 650);
        std::vector<std::pair<TGraphErrors*, TString>> series;
        for (int t = 0; t < 2; ++t)
            for (int a = 0; a < 2; ++a)
                series.push_back({make_graph(values[0][t][a], kTrkColor[t], kSeriesMarker[a], kSeriesLine[a]),
                                  Form("%s, %s", kTrkLabel[t], a ? "y" : "x")});
        // sigma never drops far below the single-pixel binary limit, so the bottom stays free for the legend
        draw_pad(c, series, xmax, ymax, Form("3 GeV e^{-}, C = %g cm, DUT = %s", scans[0].c, dut.Data()),
                 0.030, 0.50, 0.17, 0.94, 0.40);
    } else {
        c = new TCanvas("c_sigma_vs_AB", "", 1700, 650);
        c->Divide(2, 1);
        for (int a = 0; a < 2; ++a) {
            std::vector<std::pair<TGraphErrors*, TString>> series;
            for (int t = 0; t < 2; ++t)
                for (size_t is = 0; is < scans.size() && is < 4; ++is)
                    series.push_back({make_graph(values[is][t][a], kTrkColor[t], kSeriesMarker[is], kSeriesLine[is]),
                                      Form("%s, C = %g cm", kTrkLabel[t], scans[is].c)});
            draw_pad(static_cast<TPad*>(c->cd(a + 1)), series, xmax, ymax,
                     Form("3 GeV e^{-}, DUT = %s, residual %s", dut.Data(), a ? "y" : "x"), 0.033, 0.40, 0.50, 0.94, 0.76);
        }
    }
    c->cd(0);

    TString base;
    for (size_t is = 0; is < scans.size(); ++is) base += (is ? TString(scans[is].name).ReplaceAll("ABscan", "") : scans[is].name);
    base += "_dut_sigma_vs_AB";
    PlotStyle::Save(c, outDir, base);

    // numbers as JSON (same layout as the former python version)
    std::ofstream js(outDir + "/" + base + ".json");
    js << "{\n \"scans\": {\n";
    for (size_t is = 0; is < scans.size(); ++is) {
        js << Form("  \"%s\": {\"c_cm\": %g, \"values\": {\n", scans[is].name.Data(), scans[is].c);
        for (int t = 0; t < 2; ++t) {
            js << Form("   \"%s\": {", kTrkKey[t]);
            for (int a = 0; a < 2; ++a) {
                js << Form("\"%s\": [", kAxes[a]);
                const auto& v = values[is][t][a];
                for (size_t k = 0; k < v.size(); ++k)
                    js << Form("%s{\"s_cm\": %g, \"run\": %d, \"mean\": %.6g, \"mean_err\": %.6g, \"sigma\": %.6g, \"sigma_err\": %.6g}",
                               k ? ", " : "", v[k].s, v[k].run, v[k].fit.mean, v[k].fit.meanErr, v[k].fit.sigma, v[k].fit.sigmaErr);
                js << "]" << (a ? "" : ", ");
            }
            js << "}" << (t ? "\n" : ",\n");
        }
        js << "  }}" << (is + 1 < scans.size() ? ",\n" : "\n");
    }
    js << " },\n \"dut\": \"" << dut << "\",\n \"fit\": \"gaus, window mean +/- 2.5 RMS (MacroUtils::FitGaussian)\"\n}\n";
    js.close();

    for (size_t is = 0; is < scans.size(); ++is) {
        printf("\nC = %g cm\n%8s  6plane_x [um]      6plane_y [um]      upstream3_x [um]   upstream3_y [um]\n", scans[is].c, "A=B [cm]");
        for (const auto& [run, s] : scans[is].runs) {
            printf("%8g", s);
            for (int t = 0; t < 2; ++t)
                for (int a = 0; a < 2; ++a) {
                    const Point* p = nullptr;
                    for (const auto& q : values[is][t][a]) if (q.run == run) p = &q;
                    if (p) printf("  %8.2f+-%-6.2f", p->fit.sigma, p->fit.sigmaErr);
                    else printf("  %17s", "---");
                }
            printf("\n");
        }
    }
    printf("Plot: %s/%s.png\n", outDir.Data(), base.Data());
}
