// Calibrate the material-budget image (kink width) to x/X0 with Al plates of known thickness,
// taking the telescope's own contribution out (Jansen et al., doi:10.1063/1.5005503).
//
// Model for the measured width (AAD of the central 90 % of the kink angles, x and y pooled):
//
//     theta_meas^2 = dtheta^2 + [kappa * theta_HL(x/X0 + eps)]^2
//     theta_HL(x)  = 13.6 MeV / p * sqrt(x) * (1 + 0.038 ln x)          (beta = 1)
//
//   dtheta : the telescope's own width -- arm resolution + scattering in RP3/RP4 and air,
//            fixed in practice by the 0 mm point (run without sample)
//   eps    : material that is always there and enters the log term together with the sample
//   kappa  : AAD(90 %) / theta_0 (0.69 for a pure Gaussian; tails make it differ)
//
// Each image cell is then inverted: x/X0 = theta_HL^-1( sqrt(theta^2 - dtheta^2) / kappa ) - eps.
// Because of the log term and the AAD -> theta_0 scale, a plain quadratic subtraction of the
// empty-telescope width would not give x/X0; the fit takes both into account.
//
// The width of a calibration run is the AAD of the pooled kink distribution
// (TrackingMultiplet/multipletKinkAtScatterer{X,Y}, every multiplet -- the plates cover the whole
// beam), not the median of the per-cell values: with ~30 kinks per cell the per-cell AAD trims more
// than 10 % and comes out a few % low, i.e. it would depend on the statistics of the calibration run.
//
//   root -l -b -q 'calibrate_xx0.C("<imaging dir>", "<out dir>", "1:0 10:0.1 11:0.2 12:0.5 13:1 14:2 15:5 16:10", "2 3")'
// args: directory with imaging_run<N>.root, output dir, calibration runs RUN:T_AL_MM (0 = no sample),
//       runs to convert to x/X0, beam momentum [MeV] (default 3000).
// Outputs: calib_curve.{pdf,png}, calib_fit.txt, MLCC_run<N>_xx0.{pdf,png}
// Normally called by scripts/calibrate_xx0.sh.
#include "ImagingUtils.h"

#include <TFitResult.h>
#include <TGraphErrors.h>

#include <fstream>
#include <sstream>

namespace {
const double X0_AL_CM = 8.897;  // PDG
const double HL = 0.038;

double theta_hl(double x, double p) { return 13.6 / p * 1e3 * std::sqrt(x) * (1 + HL * std::log(x)); }

struct CalPoint { int run; double t_mm, xx0, aad, err; };

// AAD of the central `quantile` of the pooled x+y kink distribution and its error [mrad]
bool pooled_aad(TFile* f, double& aad, double& err, double quantile = 0.9) {
    TH1* hx = MacroUtils::Get<TH1>(f, "TrackingMultiplet/multipletKinkAtScattererX");
    TH1* hy = MacroUtils::Get<TH1>(f, "TrackingMultiplet/multipletKinkAtScattererY");
    if (!hx || !hy) return false;
    TH1* h = static_cast<TH1*>(hx->Clone("kink_pooled"));
    h->Add(hy);
    const int nb = h->GetNbinsX();
    const double n = h->Integral(0, nb + 1), lo = n * (1 - quantile) / 2, hi = n * (1 + quantile) / 2;
    if (h->GetBinContent(0) > lo || h->GetBinContent(nb + 1) > n - hi) {
        std::cerr << "kink histogram range too narrow for the quantile cut (raise kink_*_low/high)" << std::endl;
        gSystem->Exit(1);
    }
    double cum = h->GetBinContent(0), s1 = 0, s2 = 0, kept = 0;
    for (int i = 1; i <= nb; ++i) {
        const double c = h->GetBinContent(i);
        const double w = std::max(0.0, std::min(cum + c, hi) - std::max(cum, lo));  // part inside the quantile
        cum += c;
        if (w <= 0) continue;
        const double a = std::abs(h->GetBinCenter(i));
        s1 += w * a;
        s2 += w * a * a;
        kept += w;
    }
    aad = s1 / kept;
    err = std::sqrt(std::max(s2 / kept - aad * aad, 0.0) / kept);
    delete h;
    return true;
}

TF1* make_model(const char* name, double p) {
    const double k = 13.6 / p * 1e3;
    TF1* f = new TF1(name, Form("sqrt([0]*[0] + pow([1]*%g*sqrt(x+[2])*(1+%g*log(x+[2])), 2))", k, HL), 0, 0.2);
    f->SetParNames("dtheta", "kappa", "eps");
    return f;
}

// x/X0 for a measured width; may come out < 0 (statistical fluctuations below dtheta)
double invert(double theta, const double* par, double p) {
    const double target = std::sqrt(std::max(theta * theta - par[0] * par[0], 0.0)) / par[1];
    double lo = 1e-9, hi = 1.0;
    if (theta_hl(lo, p) >= target) return lo - par[2];
    for (int it = 0; it < 80; ++it) {
        const double mid = std::sqrt(lo * hi);
        (theta_hl(mid, p) < target ? lo : hi) = mid;
    }
    return std::sqrt(lo * hi) - par[2];
}

void fit_calibration(const std::vector<CalPoint>& pts, double p, const TString& outDir, double* par) {
    using namespace PlotStyle;
    TGraphErrors g;
    for (const auto& q : pts) { g.SetPoint(g.GetN(), q.xx0, q.aad); g.SetPointError(g.GetN() - 1, 0, q.err); }
    TF1* model = make_model("calib", p);
    const CalPoint* zero = nullptr;
    for (const auto& q : pts) if (q.xx0 == 0) { zero = &q; break; }
    model->SetParameters(zero ? zero->aad : 0.15, 0.69, 0.002);
    model->SetParLimits(0, 0.0, 5.0);
    model->SetParLimits(1, 0.1, 2.0);
    model->SetParLimits(2, 1e-6, 0.05);
    TFitResultPtr res = g.Fit(model, "QSN");
    if (int(res) != 0) printf("WARNING: calibration fit status %d\n", int(res));
    double err[3];
    for (int i = 0; i < 3; ++i) { par[i] = model->GetParameter(i); err[i] = model->GetParError(i); }
    const double chi2 = model->GetChisquare();
    const int ndf = model->GetNDF();

    std::ostringstream os;
    os << Form("# kink width -> x/X0 calibration, p = %g MeV\n", p)
       << "# theta^2 = dtheta^2 + [kappa * theta_HL(x/X0 + eps)]^2\n"
       << Form("dtheta = %.5f +- %.5f mrad\n", par[0], err[0])
       << Form("kappa  = %.5f +- %.5f\n", par[1], err[1])
       << Form("eps    = %.6f +- %.6f\n", par[2], err[2])
       << Form("chi2/ndf = %.2f/%d\n", chi2, ndf)
       << "# run  t_Al[mm]  x/X0  AAD[mrad]  err  fit  (data-fit)/err\n";
    for (const auto& q : pts) {
        const double fv = model->Eval(q.xx0);
        os << Form("%4d  %7.3f  %.5f  %.5f  %.5f  %.5f  %+.2f\n", q.run, q.t_mm, q.xx0, q.aad, q.err, fv, (q.aad - fv) / q.err);
    }
    gSystem->mkdir(outDir, kTRUE);
    std::ofstream(outDir + "/calib_fit.txt") << os.str();
    std::cout << os.str();

    // --- plot: log x (the 0 mm point is drawn as a band), residual panel below
    TCanvas* c = new TCanvas("c_calib", "c_calib", 900, 800);
    TPad* top = new TPad("top", "", 0, 0.3, 1, 1);
    TPad* bot = new TPad("bot", "", 0, 0, 1, 0.3);
    for (TPad* pad : {top, bot}) { pad->SetLeftMargin(0.13); pad->SetRightMargin(0.04); pad->SetLogx(); pad->Draw(); }
    top->SetBottomMargin(0.02);
    bot->SetTopMargin(0.03);
    bot->SetBottomMargin(0.33);
    const double xmin = 4e-4, xmax = 0.3;

    top->cd();
    TGraphErrors* gal = new TGraphErrors();
    double ymax = 0;
    for (const auto& q : pts) {
        ymax = std::max(ymax, q.aad);
        if (q.xx0 > 0) { gal->SetPoint(gal->GetN(), q.xx0, q.aad); gal->SetPointError(gal->GetN() - 1, 0, q.err); }
    }
    TH1F* frame = top->DrawFrame(xmin, 0, xmax, ymax * 1.25);
    frame->GetYaxis()->SetTitle("kink width (AAD, 90%) [mrad]");
    frame->GetYaxis()->SetTitleSize(0.055);
    frame->GetYaxis()->SetLabelSize(0.05);
    frame->GetXaxis()->SetLabelSize(0);
    TF1* curve = make_model("calib_curve", p);
    curve->SetParameters(par);
    curve->SetRange(xmin, xmax);
    curve->SetLineColor(kAzure + 2);
    curve->SetLineWidth(2);
    curve->Draw("SAME");
    TF1* tel = new TF1("tel", Form("%g", par[0]), xmin, xmax);  // telescope only
    tel->SetLineColor(kGray + 1);
    tel->SetLineStyle(2);
    tel->Draw("SAME");
    TF1* sample = new TF1("sample_only", Form("%g*%g*sqrt(x+%g)*(1+%g*log(x+%g))", par[1], 13.6 / p * 1e3, par[2], HL, par[2]), xmin, xmax);
    sample->SetLineColor(kOrange + 7);
    sample->SetLineStyle(7);
    sample->Draw("SAME");
    gal->SetMarkerStyle(20);
    gal->Draw("P SAME");
    TLegend* leg = MakeCleanLegend(0.16, 0.56, 0.6, 0.88, 0.045);
    leg->AddEntry(gal, "Al plates", "p");
    leg->AddEntry(tel, zero ? Form("no sample (run %d): #Delta#theta = %.3f mrad", zero->run, par[0]) : "#Delta#theta", "l");
    leg->AddEntry(sample, Form("#kappa #theta_{HL}(x/X_{0}+#varepsilon), #kappa = %.3f, #varepsilon = %.2f%%", par[1], par[2] * 100), "l");
    leg->AddEntry(curve, Form("fit, #chi^{2}/ndf = %.1f/%d", chi2, ndf), "l");
    leg->Draw();
    DrawCornerLabel(top, {"MALTA2 Telescope", "3 GeV e^{-}"}, PlotStyle::kBottomRight);

    bot->cd();
    TGraphErrors* gr = new TGraphErrors();
    for (const auto& q : pts) {
        if (q.xx0 <= 0) continue;
        const double fv = curve->Eval(q.xx0);
        gr->SetPoint(gr->GetN(), q.xx0, (q.aad - fv) / fv * 100);
        gr->SetPointError(gr->GetN() - 1, 0, q.err / fv * 100);
    }
    TH1F* fr2 = bot->DrawFrame(xmin, -4, xmax, 4);
    fr2->GetXaxis()->SetTitle("x/X_{0} of the Al plate");
    fr2->GetYaxis()->SetTitle("(data - fit)/fit [%]");
    fr2->GetYaxis()->SetNdivisions(505);
    for (TAxis* ax : {fr2->GetXaxis(), fr2->GetYaxis()}) { ax->SetTitleSize(0.12); ax->SetLabelSize(0.11); }
    fr2->GetYaxis()->SetTitleOffset(0.45);
    fr2->GetXaxis()->SetTitleOffset(1.1);
    TLine* line = new TLine(xmin, 0, xmax, 0);
    line->SetLineStyle(2);
    line->Draw();
    gr->SetMarkerStyle(20);
    gr->Draw("P SAME");
    Save(c, outDir, "calib_curve");
}

void image_xx0(const TString& run, const double* par, double p, const TString& imagingDir, const TString& outDir) {
    TFile* f = MacroUtils::OpenOrDie(imagingDir + "/imaging_run" + run + ".root");
    TH2* raw = MacroUtils::Get<TH2>(f, "AnalysisMaterialBudget/MBISqrt");
    if (!raw) return;
    TH2D* img = ImagingUtils::Shifted(raw, "img" + run);
    TH2D* xx0 = static_cast<TH2D*>(img->Clone("xx0_" + run));
    xx0->Reset();
    xx0->SetDirectory(nullptr);
    std::vector<double> vals;
    for (int i = 1; i <= img->GetNbinsX(); ++i)
        for (int j = 1; j <= img->GetNbinsY(); ++j) {
            const double th = img->GetBinContent(i, j);
            if (th <= 0) continue;
            const double v = invert(th, par, p) * 100;
            vals.push_back(v);
            // cells without image value stay white: keep them at 0 and draw from a tiny positive minimum
            xx0->SetBinContent(i, j, std::max(v, 1e-4));
        }
    if (vals.empty()) { std::cerr << "run " << run << ": empty image" << std::endl; return; }
    std::sort(vals.begin(), vals.end());
    const double zmax = vals[int(0.995 * vals.size()) - 1];
    const TString prefix = "MLCC_run" + run + "_xx0";
    TCanvas* c = ImagingUtils::MapCanvas("c_" + prefix, xx0, "x/X_{0} [%]", 1e-4, zmax);
    TLatex lat;
    lat.SetNDC();
    lat.SetTextSize(0.04);
    const int cellUm = std::lround(xx0->GetXaxis()->GetBinWidth(1) * 1e3);
    lat.DrawLatex(0.07, 0.94, Form("#font[62]{MALTA2 Telescope}  run %s, calibrated with Al, %d #mum cells", run.Data(), cellUm));
    PlotStyle::Save(c, outDir, prefix);
    // keep the calibrated map for further analysis
    TFile out(outDir + "/" + prefix + ".root", "RECREATE");
    xx0->Write("xx0");
}
}  // namespace

void calibrate_xx0(TString imagingDir, TString outDir, TString calibList, TString imageRuns = "", double momentum = 3000.0) {
    PlotStyle::SetGlobalStyle(kInvertedDarkBodyRadiator);
    std::vector<CalPoint> pts;
    for (const TString& item : MacroUtils::Split(calibList, " ,")) {
        const auto rt = MacroUtils::Split(item, ":");
        if (rt.size() != 2) { std::cerr << "bad calibration entry '" << item << "' (RUN:T_MM)" << std::endl; gSystem->Exit(1); }
        const TString path = imagingDir + "/imaging_run" + rt[0] + ".root";
        TFile* f = TFile::Open(path);
        if (!f || f->IsZombie()) {
            std::cerr << "missing " << path << " -- run scripts/run_imaging.sh --image-run " << rt[0] << " first" << std::endl;
            gSystem->Exit(1);
        }
        CalPoint q{rt[0].Atoi(), rt[1].Atof(), rt[1].Atof() * 0.1 / X0_AL_CM, 0, 0};
        if (!pooled_aad(f, q.aad, q.err)) gSystem->Exit(1);
        pts.push_back(q);
        f->Close();
    }
    std::sort(pts.begin(), pts.end(), [](const CalPoint& a, const CalPoint& b) { return a.xx0 < b.xx0; });
    if (pts.size() < 4) { std::cerr << "need at least 4 calibration points for 3 parameters" << std::endl; gSystem->Exit(1); }
    double par[3];
    fit_calibration(pts, momentum, outDir, par);
    for (const TString& run : MacroUtils::Split(imageRuns, " ,")) image_xx0(run, par, momentum, imagingDir, outDir);
}
