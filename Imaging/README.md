# Imaging (6x MALTA2 RP, no DUT) -- material-budget imaging

corryvreckan chain for scattering-angle (material-budget) imaging with a
6-plane MALTA2 telescope: the upstream (MALTA_0-2) and downstream (MALTA_4-6)
arms are fitted separately, matched at the sample plane z = 0, and the width
of the kink-angle distribution is mapped per image cell
(TrackingMultiplet + AnalysisMaterialBudget; Jansen et al., Rev. Sci. Instrum.
88 (2017) 113702, doi:10.1063/1.5005503).

```
          run 1 (no sample)                              run 2, 3 (sample)
mask.conf -> prealign.conf -> align.conf  ->  imaging.conf  ->  plot_imaging.py
geometry/ init -> masked -> prealigned -> aligned            output/imaging/imaging_run<N>.root
```

The input is MaltaDAQ-format `run_<NNNNNN>_<0..5>.root` (EventLoaderMALTA),
file index 0..5 = `MALTA_0, 1, 2, 4, 5, 6` (the names keep the 7-plane
numbering; slot 3, the DUT slot, holds the sample instead).

Nominal layout (`geometry/init.conf`), A = B = 6 cm, C = 1.5 cm:

```
MALTA_0  MALTA_1  MALTA_2  [sample]  MALTA_4  MALTA_5  MALTA_6
-13.5cm  -7.5cm   -1.5cm    0        +1.5cm   +7.5cm   +13.5cm
```

## Running

```bash
scripts/run_imaging.sh --setup dec2026_EDA --data-dir <dir> --align-run 1 --image-run "2 3"
scripts/run_imaging.sh --setup dec2026_EDA --data-dir <dir> --image-run 3 --steps "imaging plot"   # re-image only
scripts/run_imaging.sh --data-dir <dir> --sim-data --align-run 1 --image-run "2 3" --truth   # sim, default geometry
scripts/run_online.sh  --setup dec2026_EDA --run 12      # online monitor (config/online.conf)
```

The configs default to **real MaltaDAQ data** (`real_data = true`); pass `--sim-data` for
Malta2TreeWriter (Allpix) data (the `MLCC_imaging*_run_all.sh` scripts do). `--setup S` (same as
`--variant S`) uses `geometry/S/` and `output/S/`; make a new setup with
copying `geometry/template/` to `geometry/S/` and editing the z positions (see the top-level README).

Plots go to `/home/hinata/output/plot/MALTA2/simulation_analyze/material_imaging/[<setup>/]`
for `--sim-data`, and to `.../real_analyze/material_imaging/<setup>/` for beam-test data.

The simulated data come from
`/home/hinata/MALTA2/Telescope/sim/config/MLCC_imaging_run_all.sh`
(Allpix^2 + Malta2TreeWriter: MLCCs on kapton tape (run 2) or on a G10 PCB (run 3) as GDML passive material;
see `MLCC_imaging_generate_configs.py` for the capacitor model and layout),
which ends by calling `run_imaging.sh` on `sim/output/MLCC_imaging/`.

## EDA-board layout (variant `A12C6p5`)

A = B = 12 cm, C = 6.5 cm (`geometry/A12C6p5/init.conf`), MLCCs on a 0.22 mm PCB
(Cu 35 um / G10 0.15 mm / Cu 35 um) at the DUT position z = 0:

```
MALTA_0  MALTA_1  MALTA_2  [sample]  MALTA_4  MALTA_5  MALTA_6
-30.5cm  -18.5cm  -6.5cm    0        +6.5cm   +18.5cm  +30.5cm
```

`/home/hinata/MALTA2/Telescope/sim/config/MLCC_imaging_A12C6p5_run_all.sh` simulates it and
runs the chain with `run_imaging.sh --variant A12C6p5`, which uses the same step configs with
`geometry/A12C6p5/` and `output/A12C6p5/`; plots go to `material_imaging/A12C6p5/`.

## Things that differ from the Telescope template (and why)

- **`mask_dead_pixels = false`**: with a cm-sized beam spot most pixels only
  see a few hits, so "dead" (= no hit in the mask run) masks pixels that do
  fire in the imaging run and silently drops ~60% of their hits.
  (`Telescope/config/mask.conf` is now `false` as well, for the same reason.)
- **Alignment on a run without the sample**: straight 6-plane tracks are
  only a valid model with nothing at z = 0.
- **`scatterer_position = 1um`** (not 0): TrackingMultiplet starts
  `max_z_upstream` at `numeric_limits<double>::min()` (= +2e-308), so with
  every upstream plane at z < 0 a scatterer at exactly 0 is rejected.
- **AnalysisMaterialBudget maps are one bin off**: it fills them with
  `SetBinContent(cell_x, cell_y)` for 0-based indices. `plot_imaging.py`
  shifts them back; the raw `MBI`/`MBISqrt` in the ROOT file are still off.
- The image is the kink width (AAD of the central 90%, x and y pooled), not
  x/X0. `scripts/calibrate_xx0.py` converts it (next section).

## Calibration to x/X0 (Al plates)

The kink width contains the telescope's own part (arm resolution + scattering
in RP3/RP4 and air). It is taken out with Al plates of known thickness imaged
in the same setup (simulation: runs 10..16 = 0.1 / 0.2 / 0.5 / 1 / 2 / 5 / 10 mm,
run 1 = 0 mm), fitted with

    theta_meas^2 = dtheta^2 + [kappa * theta_Highland(x/X0 + eps)]^2

(dtheta = telescope, eps = material that sits in the log term with the sample,
kappa = AAD(90%)/theta_0), and every image cell is inverted with it. A plain
quadratic subtraction of the empty-telescope width is not enough because of the
log term and the AAD scale. The plates go up to 10 mm (11% x/X0) since the MLCCs
on PCB reach ~10.5%.

```bash
scripts/run_imaging.sh --data-dir <dir> --image-run "1 10 11 12 13 14 15 16" --steps "imaging"
scripts/calibrate_xx0.py --calib 1:0 10:0.1 11:0.2 12:0.5 13:1 14:2 15:5 16:10 --image-run 2 3 --truth
```

(`MLCC_imaging_run_all.sh` does both when RUNS contains Al runs.) Outputs:
`calib_curve`, `calib_fit.txt`, `MLCC_run<N>_xx0` and, with `--truth`, the
nominal map / difference / profiles / per-capacitor comparison against
`true_xx0()` of the generator.
