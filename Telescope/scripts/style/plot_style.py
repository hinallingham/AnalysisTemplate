"""
plot_style.py -- shared PyROOT house style, extracted and generalized from
the user's MALTA2 comparison/in-pixel macros.

Import this in any PyROOT plotting script:

    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "style"))
    import plot_style as ps

    ps.set_global_style()
    pad1, pad2 = ps.make_ratio_canvas("c_compare")
    ...
    ps.draw_corner_label(pad1, ["Telescope @ TestBeam", "Run: XDPW Epi"], corner="top-right")
    ...
    ps.save(canvas, outdir, "clustersize_MALTA_0_compare")
"""

import os
import ROOT


# ---------------------------------------------------------------------------
# Global style
# ---------------------------------------------------------------------------

def set_global_style(palette=113, n_contours=255):
    """Call once at the top of main(). Matches the house style used across
    all reference macros: no stat/title boxes, high-res 2D palette."""
    ROOT.gStyle.SetOptStat(0)
    ROOT.gStyle.SetOptTitle(0)
    ROOT.gStyle.SetNumberContours(n_contours)
    ROOT.gStyle.SetPalette(palette)


# ---------------------------------------------------------------------------
# Ratio-panel canvas (main plot 70% / ratio panel 30%, shared x-axis)
# ---------------------------------------------------------------------------

def make_ratio_canvas(name, width=900, height=640, split=0.30):
    """Returns (canvas, pad_main, pad_ratio) with the standard margins and
    font-code-43 friendly geometry used in every *_compare.C/.py macro.
    pad_main spans [split, 1.0], pad_ratio spans [0.0, split]; x-axis of
    pad_main is left blank (label/title size 0) since pad_ratio carries it.
    """
    c = ROOT.TCanvas(name, name, width, height)

    pad1 = ROOT.TPad(name + "_main", "main", 0.0, split, 1.0, 1.0)
    pad1.SetLeftMargin(0.14)
    pad1.SetRightMargin(0.05)
    pad1.SetTopMargin(0.10)
    pad1.SetBottomMargin(0.02)
    pad1.Draw()

    pad2 = ROOT.TPad(name + "_ratio", "ratio", 0.0, 0.0, 1.0, split)
    pad2.SetLeftMargin(0.14)
    pad2.SetRightMargin(0.05)
    pad2.SetTopMargin(0.03)
    pad2.SetBottomMargin(0.38)
    pad2.Draw()

    c._pads_keepalive = (pad1, pad2)  # prevent premature GC in PyROOT
    return c, pad1, pad2


def style_shared_xaxis_main(hist_or_frame):
    """Hide the x-axis labels/title on the main pad (it's shown on the ratio
    pad below instead)."""
    ax = hist_or_frame.GetXaxis()
    ax.SetLabelSize(0)
    ax.SetTitleSize(0)


def style_axis_font43(axis, title_size=20, title_offset=1.8, label_size=17,
                       title=None, ndivisions=None):
    """Apply the font-code-43 (absolute pixel size, pad-size independent)
    styling used throughout the reference macros. Use title_size~20/label_size~17
    for a main-pad y-axis, ~15/15 for a ratio-pad y-axis, offset~3.6 for a
    ratio-pad x-axis."""
    axis.SetTitleFont(43)
    axis.SetTitleSize(title_size)
    axis.SetTitleOffset(title_offset)
    axis.SetLabelFont(43)
    axis.SetLabelSize(label_size)
    if title is not None:
        axis.SetTitle(title)
    if ndivisions is not None:
        axis.SetNdivisions(ndivisions)


def draw_ratio_refline(xmin, xmax, y=1.0, color=None, style=2):
    """Dashed reference line at y (default 1.0) across the ratio panel.
    Returns the TLine -- keep a reference alive until SaveAs."""
    color = color if color is not None else ROOT.kRed
    line = ROOT.TLine(xmin, y, xmax, y)
    line.SetLineColor(color)
    line.SetLineStyle(style)
    line.Draw("same")
    return line


# ---------------------------------------------------------------------------
# Corner-safe annotation block
# ---------------------------------------------------------------------------

_CORNER_PRESETS = {
    # (x, y_top, align) -- lines are stacked downward from y_top with dy step
    "top-right":    (0.93, 0.86, 31),
    "top-left":     (0.16, 0.86, 11),
    "bottom-right": (0.93, 0.22, 31),
    "bottom-left":  (0.16, 0.22, 11),
}


def draw_corner_label(pad, lines, corner="top-right", header_size=0.042,
                       body_size=0.036, dy=0.055, color=ROOT.kBlack):
    """Draw a multi-line NDC text block in one corner of `pad`, matching the
    "MALTA2 Telescope @ PF-AR" / "MALTA2 XDPW Epi" / detail-line pattern from
    the reference macros: first line bold (font 62), remaining lines regular
    (font 42). Returns the list of TLatex objects (keep alive until SaveAs).

    Use pick_label_corner() first if you want the corner chosen automatically
    to avoid the histogram's own data.
    """
    pad.cd()
    x, y0, align = _CORNER_PRESETS[corner]
    objs = []
    for i, text in enumerate(lines):
        lat = ROOT.TLatex()
        lat.SetNDC()
        lat.SetTextAlign(align)
        lat.SetTextColor(color)
        if i == 0:
            lat.SetTextFont(62)
            lat.SetTextSize(header_size)
        else:
            lat.SetTextFont(42)
            lat.SetTextSize(body_size)
        lat.DrawLatex(x, y0 - i * dy, text)
        objs.append(lat)
    return objs


def pick_label_corner(hist, candidates=("top-right", "top-left",
                                         "bottom-right", "bottom-left"),
                       frac=0.30):
    """Heuristic: for a TH1, sample the mean bin content in the x/y quadrant
    behind each candidate corner and return the corner with the least data
    there, so an annotation block placed there won't overlap the histogram.
    Works for TH1 (checks left/right x-thirds at high/low y) -- for TH2 maps
    use pick_label_corner_2d instead.
    """
    nx = hist.GetNbinsX()
    n_edge = max(1, int(nx * frac))
    y_max = hist.GetMaximum()

    def region_score(x_side, y_side):
        bins = range(1, n_edge + 1) if x_side == "left" else range(nx - n_edge + 1, nx + 1)
        vals = [hist.GetBinContent(b) for b in bins]
        peak = max(vals) if vals else 0.0
        # "top" corners care about tall bins near the top of the range;
        # normalize against the histogram's global max.
        return peak / y_max if y_max > 0 else 0.0

    scored = {
        "top-right": region_score("right", "top"),
        "top-left": region_score("left", "top"),
        "bottom-right": region_score("right", "bottom"),
        "bottom-left": region_score("left", "bottom"),
    }
    candidates = [c for c in candidates if c in scored]
    return min(candidates, key=lambda c: scored[c])


def pick_label_corner_2d(hist2d, candidates=("top-right", "top-left",
                                              "bottom-right", "bottom-left"),
                          frac=0.30):
    """Same idea as pick_label_corner but for a TH2 map: samples the mean
    bin content in each corner quadrant (frac x frac of the map) and returns
    the emptiest one."""
    nx, ny = hist2d.GetNbinsX(), hist2d.GetNbinsY()
    ex, ey = max(1, int(nx * frac)), max(1, int(ny * frac))

    def region_mean(x_range, y_range):
        vals = [hist2d.GetBinContent(i, j) for i in x_range for j in y_range]
        return sum(vals) / len(vals) if vals else 0.0

    left, right = range(1, ex + 1), range(nx - ex + 1, nx + 1)
    bottom, top = range(1, ey + 1), range(ny - ey + 1, ny + 1)
    scored = {
        "top-right": region_mean(right, top),
        "top-left": region_mean(left, top),
        "bottom-right": region_mean(right, bottom),
        "bottom-left": region_mean(left, bottom),
    }
    candidates = [c for c in candidates if c in scored]
    return min(candidates, key=lambda c: scored[c])


# ---------------------------------------------------------------------------
# Legend
# ---------------------------------------------------------------------------

def make_clean_legend(x1, y1, x2, y2, text_size=0.032):
    """Borderless, transparent-fill TLegend matching the house style."""
    leg = ROOT.TLegend(x1, y1, x2, y2)
    leg.SetBorderSize(0)
    leg.SetFillStyle(0)
    leg.SetTextSize(text_size)
    return leg


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save(canvas, outdir, basename):
    """Write both <basename>.pdf and <basename>.png into outdir, creating it
    if needed. Returns (pdf_path, png_path)."""
    os.makedirs(outdir, exist_ok=True)
    outpdf = os.path.join(outdir, basename + ".pdf")
    outpng = os.path.join(outdir, basename + ".png")
    canvas.SaveAs(outpdf)
    canvas.SaveAs(outpng)
    print(f"[plot_style] Saved: {outpdf}")
    print(f"[plot_style] Saved: {outpng}")
    return outpdf, outpng