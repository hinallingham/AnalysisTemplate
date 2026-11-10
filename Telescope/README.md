# Telescope (6x MALTA2 RP + 1 DUT)

corryvreckan analysis template for a 7-plane MALTA2 telescope: 6 reference planes
(`MALTA_0,1,2,4,5,6`) with the DUT (`MALTA_3`) in the middle. Needs only bash, corry and ROOT;
the paths of corry / ROOT / the data come from `../paths.json` (see the top-level README).

```
step:       mask        -> prealign       -> align          -> align_dut        -> analysis [upstream3]
config:     mask.conf      prealign.conf     align.conf        align_dut.conf      analysis.conf [analysis_upstream3.conf]
geometry:   run<A>/init -> masked         -> prealigned     -> aligned          -> aligned_dut
plot macro: plot_mask.C    plot_prealign.C   plot_align.C      plot_align_dut.C    plot_analysis.C
```

Each step reads the previous step's geometry and writes its own. `align` (AlignmentMillepede) fits
the 6 reference planes only, with the DUT excluded; `align_dut` (AlignmentDUTResidual) then
fine-tunes just the DUT on top of that, using unbiased residuals against the now-fixed RP tracks.
`aligned_dut.conf` is the final geometry -- that's what the analysis reads.

## Layout

- `config/*.conf` -- one corryvreckan config per step. `run_number`, `base_path`, the geometry
  files and `output_directory` are filled in by `scripts/run_chain.sh` with `-o` overrides.
- `geometry/<setup>/init.conf` -- z positions of one layout; `geometry/<setup>/run<A>/` -- the
  alignment chain made on run A. `geometry/template/` is the starting point for a new setup.
- `scripts/run_chain.sh` -- runs corry for each step, then the step's ROOT macro.
- `macros/plot_<step>.C` -- summary plots (PDF + PNG) in the MALTA2 house style
  (`../common/PlotStyle.h`, `../common/MacroUtils.h`): Gaussian fits on residual/correlation
  peaks, shift values and widths annotated on the plot.
- `output/<setup>/run<N>/<step>/` -- corry's histogram file, corry's log, the summary plots.

## Running

```bash
scripts/run_chain.sh  --setup dec2026_C1p5 --run 120                     # mask .. analysis
scripts/run_chain.sh  --setup dec2026_C1p5 --align-run 120 --run 121 --steps "analysis upstream3"
scripts/run_chain.sh  --setup dec2026_C1p5 --run 120 --steps prealign    # one step
scripts/run_chain.sh  --setup dec2026_C1p5 --run 120 --plot-only         # redo only the plots
scripts/run_online.sh --setup dec2026_C1p5 --run 121
```

`--data-dir` defaults to `telescope_data_dir` in `paths.json` and expects
`run_<run number zero-padded to 6 digits>_<plane index 0-6>.root` (EventLoaderMALTA multi-file convention).

`--events N` overrides `number_of_events` for a quick test. `--sim-data` sets
`EventLoaderMALTA.real_data=false` for data from the `Malta2TreeWriter` Allpix module (no hardware
group-address offset). **All configs default to real data**, so simulated data always needs `--sim-data`.

`--analysis-config FILE` runs the analysis step with another config (output in
`output/<setup>/run<N>/<last part of its output_directory>/`).

A macro can be run by hand on any corry output, e.g.

```bash
root -l -b -q 'macros/plot_analysis.C("output/dec2026_C1p5/run120/analysis/analysis.root", "/tmp/plots", "120", "MALTA_0,MALTA_1,MALTA_2,MALTA_3,MALTA_4,MALTA_5,MALTA_6", "MALTA_3")'
```

## DUT (`--dut`)

The DUT is the detector with `role = "dut"` in the input geometry. `--dut MALTA_x` moves the role
for this step with corry `-g` overrides and regenerates `Tracking4D.require_detectors` to exclude
the new DUT; corry writes the role into the step's output geometry, so later steps inherit it
without `--dut` again.

## Setups

Each setup has its own `geometry/<setup>/` and `output/<setup>/`; every alignment run has its own
`geometry/<setup>/run<A>/` (the mask step copies `geometry/<setup>/init.conf` there; A = `--align-run`,
default the run itself). New setups: copy `geometry/template/` to `geometry/<setup>/` and edit the
z positions (lines marked `EDIT`). See the top-level README (`../README.md`, `../README.en.md`).

## Notes

- `config/mask.conf` has `mask_dead_pixels = false`: with the beam covering part of the chip, the
  pixels it never reaches count as "dead", and AnalysisEfficiency then drops every track next to
  a masked pixel (measured on simulation: 85 of 30704 tracks left).
- A truly global `[Corryvreckan]` option like `number_of_events` must be passed unprefixed
  (`-o number_of_events=...`): corry's OptionParser treats anything before a `.` as a
  module/detector identifier, and `Corryvreckan.number_of_events` is silently dropped.
- corry occasionally crashes in its teardown (`double free or corruption`) after the results are
  written; `run_chain.sh` then warns and continues.

## Simulation only: ABscan

`scripts/run_ABscan.sh` (C = gap RP3-DUT, A = B scanned) runs `run_chain.sh` for every run of a
simulated scan, `scripts/plot_ABscan_sigma.sh --c "1.5 5"` plots the DUT residual width vs A = B.
Both need `sim_config_dir` in `paths.json` (for the run table of `ABscan_generate_configs.py`).

## Growing the main analysis

`config/analysis.conf` and `macros/plot_analysis.C` are intentionally minimal (Tracking4D +
DUTAssociation + AnalysisDUT + AnalysisEfficiency). Add more `[AnalysisXxx]` sections as needed
and extend `plot_analysis.C` to match.
