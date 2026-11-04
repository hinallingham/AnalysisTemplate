# Telescope (6x MALTA2 RP + 1 DUT)

corryvreckan analysis template for a 7-plane MALTA2 telescope: 6 reference
planes (`MALTA_0,1,2,4,5,6`) spaced 1 inch (2.54 cm) apart, with the DUT
(`MALTA_3`) in the middle.

```
NoiseMasking.py -> Prealignment.py -> Alignment.py -> AlignmentDUT.py -> run_analysis.py
     mask.conf       prealign.conf     align.conf       align_dut.conf     analysis.conf
        |                 |                |                 |                  |
        v                 v                v                 v                  v
  geometry/masked  geometry/prealigned  geometry/aligned  geometry/aligned_dut  output/analysis
```

Each geometry file only exists once its step has been run; each step reads
the previous step's geometry output and writes its own. `Alignment.py`
(AlignmentMillepede) fits the 6 reference planes only, with the DUT
excluded; `AlignmentDUT.py` (AlignmentDUTResidual) then fine-tunes just the
DUT on top of that, using unbiased residuals against the now-fixed RP
tracks. `geometry/aligned_dut.conf` is the final geometry -- that's what
`config/analysis.conf` reads from.

## Layout

- `geometry/init.conf` -- ideal 7-plane placement, DUT = `MALTA_3`.
- `config/*.conf` -- one corryvreckan config per step. `run_number` /
  `base_path` are left blank (`0` / `""`-ish placeholders) and filled in
  via `-o` overrides at run time.
- `scripts/*.py` -- one script per step. Each one runs `corry`, then reads
  the resulting ROOT file (PyROOT) and shows a summary plot in the MALTA2
  house ROOT style (`scripts/style/plot_style.py`, from the
  `root-plot-polish` skill) -- white ROOT canvas, Gaussian fits on
  residual/correlation peaks, shift values annotated on the plot.
- `output/<step>/` -- corry's histogram_file, corry's own log, and the
  summary PDF+PNG, per run.
- `.venv/` -- project-local venv (numpy + matplotlib, used only
  incidentally; PyROOT comes from the shared ROOT install via
  `PYTHONPATH` and is what actually does the plotting).

## Running a step

```bash
cd scripts
../.venv/bin/python3 NoiseMasking.py  1 --data-dir ../data
../.venv/bin/python3 Prealignment.py  1 --data-dir ../data
../.venv/bin/python3 Alignment.py     1 --data-dir ../data
../.venv/bin/python3 AlignmentDUT.py  1 --data-dir ../data
../.venv/bin/python3 run_analysis.py  1 --data-dir ../data
```

`--data-dir` defaults to `Telescope/data`, and expects
`run_<run_number zero-padded to 6 digits>_<plane index 0-6>.root` files
there (corryvreckan's `EventLoaderMALTA` multi-file convention).

`--events N` overrides `number_of_events` from the config for a quick test
run (e.g. while iterating on a config change). `--sim-data` sets
`EventLoaderMALTA.real_data=false` for data produced by the
`Malta2TreeWriter` Allpix module (no hardware group-address offset) rather
than a real MaltaDAQ beam-test run. **All configs default to real data**
(`real_data = true`), so simulated data always needs `--sim-data`.

## Setups (`--setup`)

`--setup S` on any step script runs the same configs on `geometry/S/` (starting from
`geometry/S/init.conf`) and writes to `output/S/run<N>/<step>/` (N = the run the step reads), leaving `geometry/*.conf` and
`output/<step>/` alone -- several layouts can then live side by side. `scripts/run_chain.sh`
runs the whole chain for one setup, `scripts/run_online.sh` the online monitor:

```bash
scripts/run_chain.sh  --setup dec2026_C1p5 --run 120                     # mask .. analysis
scripts/run_chain.sh  --setup dec2026_C1p5 --align-run 120 --run 121 --steps "analysis upstream3"
scripts/run_online.sh --setup dec2026_C1p5 --run 121
```

New setups: copy `geometry/template/` to `geometry/S/` and edit the z positions (lines marked `EDIT`).
See the top-level README (`../README.md`, `../README.en.md`).

`config/mask.conf` has `mask_dead_pixels = false`: with the beam covering part of the chip, the
pixels it never reaches count as "dead", and AnalysisEfficiency then drops every track next to
a masked pixel (measured on simulation: 85 of 30704 tracks left).

All step-specific `-o` overrides go through `common.standard_overrides()` --
notably, a truly global `[Corryvreckan]` option like `number_of_events` must
be passed unprefixed (`-o number_of_events=...`), not as
`Corryvreckan.number_of_events`: corry's OptionParser treats anything
before a `.` as a module/detector identifier to match, and `Corryvreckan`
isn't a module, so the prefixed form is silently dropped.

## Growing the main analysis

`config/analysis.conf` and `scripts/run_analysis.py` are intentionally
minimal (Tracking4D + DUTAssociation + AnalysisDUT + AnalysisEfficiency).
Add more `[AnalysisXxx]` sections as needed and extend the plotting code
in `run_analysis.py` to match.
