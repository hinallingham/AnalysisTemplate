# AnalysisTemplate — analysis template for the December 2026 PF-AR beam test

[日本語版](README.md)

Corryvreckan analysis of the MALTA2 telescope at PF-AR. The configs and geometries are prepared
before the beam test, so that on the day **only the z positions of the planes have to be filled in**
to go from alignment to analysis and online monitoring.

| Purpose | Directory | Prepared setup |
|---|---|---|
| Telescope (6 RPs + 1 DUT, DUT = MALTA2) | `Telescope/` | `dec2026_C1p5` (every gap 1.5 cm) |
| Material-budget imaging (6 RPs, sample at z = 0) | `Imaging/` | `dec2026_EDA` (measured EDA-board positions) |

## 1. The idea: setups

A "setup" is one detector layout: `geometry/<setup>/init.conf` with the z position of every plane.
Each analysis step reads the geometry the previous step wrote and writes its own next to it:

```
Telescope:  geometry/<setup>/init.conf → masked → prealigned → aligned → aligned_dut .conf
Imaging:    geometry/<setup>/init.conf → masked → prealigned → aligned .conf
results:    Telescope: output/<setup>/run<N>/<step>/, Imaging: output/<setup>/<step>/
            (corry ROOT file, log, summary plots; N = the run the step read)
```

- `init.conf` only needs **z** (to ~1 mm). x/y offsets and rotations are found by
  Prealignment / Alignment (Millepede) / AlignmentDUT.
- The configs (`config/*.conf`) are shared by all setups; only the geometry differs.
- One setup per layout keeps the results of different layouts apart.

## 2. Directory layout

```
AnalysisTemplate/
├── README.md / README.en.md
├── Telescope/
│   ├── config/                   mask, prealign, align, align_dut, analysis, analysis_upstream3, online
│   ├── geometry/
│   │   ├── template/init.conf    setup template (z lines marked "EDIT")
│   │   ├── dec2026_C1p5/         all RP-RP and RP-DUT gaps 1.5 cm
│   │   └── init.conf ...         legacy geometry used without --setup (1 inch pitch)
│   ├── scripts/
│   │   ├── run_chain.sh          mask → prealign → align → align_dut → analysis (→ upstream3)
│   │   ├── run_online.sh         online monitor
│   │   └── NoiseMasking.py ...   the individual steps (all accept --setup)
│   ├── data/                     default place for run_<NNNNNN>_<0..6>.root
│   └── output/<setup>/run<N>/<step>/
└── Imaging/
    ├── config/                   mask, prealign, align, imaging, online
    ├── geometry/
    │   ├── template/init.conf
    │   └── dec2026_EDA/          measured EDA-board positions (RD53B plane = sample = z 0)
    ├── scripts/
    │   ├── run_imaging.sh        mask → prealign → align (no-sample run) → imaging → plot
    │   ├── run_online.sh         online monitor
    │   ├── plot_imaging.py       image plots
    │   └── calibrate_xx0.py      x/X0 calibration with Al plates
    ├── data/                     default place for run_<NNNNNN>_<0..5>.root
    └── output/<setup>/
```

## 3. Prepared layouts

**Telescope `dec2026_C1p5`** (beam along +z, MALTA_3 is the DUT):

```
MALTA_0 –1.5– MALTA_1 –1.5– MALTA_2 –1.5– [MALTA_3 = DUT] –1.5– MALTA_4 –1.5– MALTA_5 –1.5– MALTA_6   [cm]
  −45           −30           −15              0              +15          +30          +45     [mm]
```

**Imaging `dec2026_EDA`** (z = 0 at the RD53B plane, where the sample sits; beam enters at plane 1):

```
MALTA_0 –110– MALTA_1 –110– MALTA_2 –61.65– [sample] –48.35– MALTA_4 –110– MALTA_5 –110– MALTA_6   [mm]
 −281.65      −171.65       −61.65           0          +48.35        +158.35       +268.35  [mm]
```

## 4. Requirements

- corry: `/home/hinata/package/corryvreckan/bin/corry` (set `CORRY_BIN=...` if it lives elsewhere)
- Python: `Telescope/.venv/bin/python3` (PyROOT from the shared ROOT install); the scripts use it automatically.
- Data: MaltaDAQ `run_<6-digit run number>_<plane index>.root` (EventLoaderMALTA format)
  - Telescope: plane index 0..6 = MALTA_0..MALTA_6
  - Imaging: plane index 0..5 = MALTA_0, 1, 2, 4, 5, 6 (slot 3, the DUT slot, is empty)
- All configs **default to real data (`real_data = true`)**. Data simulated with the Allpix
  `Malta2TreeWriter` always needs `--sim-data`.

## 5. On the day

1. **Measure the z positions and make a setup** (not needed if the prepared layout is used as is).
   Copy the template and change only the z (third value) of the `position` lines marked `# <-- EDIT`,
   upstream plane first:
   ```bash
   cp -r Telescope/geometry/template Telescope/geometry/dec2026_run1
   cp -r Imaging/geometry/template   Imaging/geometry/dec2026_img1
   # open each init.conf and set z (e.g. position = 0um, 0um, -45mm)
   ```
   Write z with its unit (mm or cm). Leave the `role` lines as they are.
2. **Start the online monitor during the first run.** There is no alignment yet, so it uses init.conf:
   watch the hitmaps and correlations (residuals and efficiency are not meaningful yet).
   ```bash
   Telescope/scripts/run_online.sh --setup dec2026_C1p5 --run 120 --data-dir /path/to/maltadaq/data
   ```
3. **Align on a run with enough statistics** (prealign uses 200k events, align / align_dut 10k events):
   ```bash
   Telescope/scripts/run_chain.sh --setup dec2026_C1p5 --run 120 --data-dir /path/to/data
   ```
4. **Restart the online monitor.** It now picks `aligned_dut.conf` and shows the DUT residuals and efficiency.
5. **Analyse further runs of the same layout with that alignment:**
   ```bash
   Telescope/scripts/run_chain.sh --setup dec2026_C1p5 --align-run 120 --run 121 --steps "analysis upstream3"
   ```
   After moving any plane, make a new setup and align again.

## 6. Telescope analysis (`Telescope/`)

```bash
cd Telescope/scripts
./run_chain.sh --setup dec2026_C1p5 --run 120 [--data-dir DIR] [--events N] [--sim-data]
./run_chain.sh --setup dec2026_C1p5 --run 120 --steps "mask prealign align align_dut analysis upstream3"
```

| Step | Config | What it does | Writes geometry |
|---|---|---|---|
| `mask` | `mask.conf` | masks noisy pixels | `masked.conf` |
| `prealign` | `prealign.conf` | coarse x/y shifts from correlations (DUT fixed) | `prealigned.conf` |
| `align` | `align.conf` | Millepede alignment of the 6 RPs (DUT excluded) | `aligned.conf` |
| `align_dut` | `align_dut.conf` | aligns only the DUT, on RP tracks | `aligned_dut.conf` |
| `analysis` | `analysis.conf` | 6-RP tracking, DUT efficiency and residuals | — |
| `upstream3` | `analysis_upstream3.conf` | tracking with the 3 upstream RPs only (extrapolated to the DUT) | — |

- Results: `output/<setup>/run<N>/<step>/` with `*.root`, `run<N>_corry.log`, `run<N>_summary.png/pdf`
  (analysis also `run<N>_residuals.png`). N is the run the step read, so with
  `--align-run 120 --run 121` the alignment goes to `run120/` and the analysis to `run121/`.
- The step scripts can also be run directly: `../.venv/bin/python3 Alignment.py 120 --setup dec2026_C1p5`
- `--dut MALTA_x` makes another plane the DUT (see Telescope/README.md).

## 7. Imaging analysis (`Imaging/`)

Align on a run without the sample, then image the runs with the sample
(straight 6-plane tracks are only a valid alignment model with nothing at z = 0).

```bash
cd Imaging/scripts
./run_imaging.sh --setup dec2026_EDA --data-dir DIR --align-run 11 --image-run "12 13"
./run_imaging.sh --setup dec2026_EDA --data-dir DIR --image-run 14 --steps "imaging plot"   # already aligned
```

- The image is the kink-angle width per cell (AAD of the central 90%, x and y pooled), not x/X0.
  For x/X0, take runs with Al plates of known thickness in the same layout and calibrate with
  `calibrate_xx0.py` (see Imaging/README.md).
- Plots: `/home/hinata/output/plot/MALTA2/real_analyze/material_imaging/<setup>/MLCC_run<N>_{image,tracks,xprofile,kink}.png`
  (`simulation_analyze/` with `--sim-data`).
- **Statistics**: a cell only gets a value with at least 20 multiplets (`min_cell_content`). In the
  EDA-layout simulation, ~1.6M tracks fill every 100 µm cell, while 100k tracks leave the MLCCs
  nearly empty. With ~100k tracks, use 200 µm cells
  (`cell_size` in `config/imaging.conf`, or `-o AnalysisMaterialBudget.cell_size=200um,200um`).
- The image area is `image_size = 18mm 9mm` (one MALTA2) in `config/imaging.conf`.

## 8. Online monitor

Reads the run files while MaltaDAQ is still writing them and shows hitmaps, correlations, tracks,
residuals, efficiency and more in real time. The settings are in `config/online.conf` of Telescope / Imaging.

### 8.1 Starting and stopping

```bash
Telescope/scripts/run_online.sh --setup dec2026_C1p5 --run 121 --data-dir DIR
Imaging/scripts/run_online.sh   --setup dec2026_EDA  --run 12  --data-dir DIR
```

- It reads files that are still being written, so it can be started together with the run. It never writes a geometry.
- **Needs a display (X11).** Over ssh, log in with `ssh -X` / `ssh -Y`.
- It picks the newest geometry of the setup
  (Telescope: aligned_dut > aligned > prealigned > init; Imaging: aligned > prealigned > masked > init),
  or the one given with `--geometry FILE`. Before the alignment (init.conf), only look at the hitmaps and correlations.
- A restart starts all histograms from zero. After an alignment, restart to pick up the new geometry.
- Stop it by closing the window or with Ctrl-C in the terminal.
- Snapshots (PNG) every minute: Telescope `output/<setup>/run<N>/online/snapshots/`,
  Imaging `output/<setup>/online/snapshots/`. All histograms are written to `online.root` there at the end.
- `--sim-data` shows simulated data (for practice).

### 8.2 The display

Switch canvases with the buttons on the left. Keys:

| Key | Action |
|---|---|
| `Space` | pause / resume |
| `F` | current canvas full screen |
| `S` | save the current canvas as PNG |
| `1`–`9` | Overview, Tracking Performance, Residuals X, Residuals Y, Res Trends, Timeline, Corr Trends, Hitmaps, Event Times |

The canvases, and whether their content can be changed in the config (those that can are overridden with the key named in the last column):

| Canvas | Default content | Config key |
|---|---|---|
| Overview | χ²/ndf, hitmap and residual of the reference plane | `overview` |
| Tracking Performance | χ², angle X/Y, tracks/event, clusters/track | `tracking` |
| Residuals X / Y | residual per plane (DUT excluded) | `residuals` / `residuals_y` |
| Hitmaps | hitmap per plane | `hitmaps` |
| Event Times | event time per plane | `event_times` |
| Cluster Size | cluster size per plane | `cluster_size` |
| 1D X / 1D Y | 1D correlations per plane | `correlation_x` / `correlation_y` |
| 2D X / 2D Y | 2D correlations per plane | `correlation_x2d` / `correlation_y2d` |
| DUTs (one per DUT) | DUT hitmap, residual X/Y, efficiency map | `dut_plots` |
| Res Trends, Timeline, Corr Trends, L1idC | residual / cluster count / correlation vs time, DAQ health | fixed |

What to look for in each plot is described in corry's `src/modules/OnlineMonitor/PLOT_GUIDE_en.md`.

### 8.3 Putting your own plots on the monitor

**New canvases cannot be added.** Instead, you **replace** the content of a canvas that has a config key
(table above) in the `[OnlineMonitor]` section of `config/online.conf`. A canvas you set shows only what you
wrote: its default content is gone (it replaces, it does not add — list the default plots you want to keep too).

The value is a matrix of `[histogram path, draw option]` rows:

```toml
[OnlineMonitor]
overview = [["Tracking4D/trackChi2ndof"], ["Correlations/%REFERENCE%/hitmap", "colz"], ["Tracking4D/tracksPerEvent", "log"]]
```

- **One line**: corry's config parser has no line continuation; however long, it stays on one line.
- **Path** = `module/detector/…/histogram`, as inside the result ROOT file (how to find it: 8.4).
- **Placeholders**:
  - `%REFERENCE%` → one plot, for the reference plane (MALTA_0)
  - `%DETECTOR%` → one plot per plane (DUT excluded on Residuals X/Y)
  - `%DUT%` → one plot per DUT (on `dut_plots`: that canvas's DUT)
- **Draw option** (second entry, optional): `"colz"` for 2D. Anything containing `"log"` makes the y axis
  logarithmic (combinations like `"colz log"` work). Everything else goes to ROOT's Draw (`"hist"`, ...).
- Only TH1 / TH2 / TProfile can be drawn. A `TEfficiency` (e.g. `AnalysisEfficiency/MALTA_3/chipEfficiencyMap_trackPos`)
  cannot; use its `_TProfile` twin.
- **A wrong path is silently not shown** (no error). If a plot does not appear, check the path first.
- Only histograms of **modules that run inside `online.conf`** can be shown. If no module makes the histogram
  you want, add that module's section to `online.conf`.

**Example 1: add the cluster size to the DUT canvas** (Telescope). Clustering4D makes it, so just add the path:

```toml
dut_plots = [["Correlations/%DUT%/hitmap", "colz"], ["OnlineMonitor/dut_residual_x_%DUT%"], ["OnlineMonitor/dut_residual_y_%DUT%"], ["AnalysisEfficiency/%DUT%/chipEfficiencyMap_trackPos_TProfile", "colz"], ["Clustering4D/%DUT%/clusterSize", "log"]]
```

**Example 2: the DUT in-pixel efficiency** (Telescope). AnalysisEfficiency already runs in `online.conf`:

```toml
dut_plots = [["AnalysisEfficiency/%DUT%/chipEfficiencyMap_trackPos_TProfile", "colz"], ["AnalysisEfficiency/%DUT%/pixelEfficiencyMap_trackPos_TProfile", "colz"], ["OnlineMonitor/dut_residual_x_%DUT%"], ["OnlineMonitor/dut_residual_y_%DUT%"]]
```

**Example 3: a histogram of a module that does not run yet.** The size of the DUT's associated clusters
(`AnalysisDUT/%DUT%/clusterSizeAssociated`) comes from AnalysisDUT, so first add an `[AnalysisDUT]` section to
`online.conf`. AnalysisDUT books ~4 GB of histograms, though, which makes the monitor heavy (that is why it is
not in by default) — keep the modules you add light.

**Example 4: change the Imaging overview.** The Imaging `online.conf` tracks with `TrackingMultiplet`, so its
Overview / Tracking / Residuals are already set to TrackingMultiplet and AnalysisMaterialBudget histograms.
To also see the kink angle in y:

```toml
overview = [["AnalysisMaterialBudget/MBIpreview", "colz"], ["TrackingMultiplet/multipletKinkAtScattererX"], ["TrackingMultiplet/multipletKinkAtScattererY"], ["TrackingMultiplet/matchingDistanceAtScattererX"]]
```

### 8.4 Finding a histogram's path

Run the online monitor or an offline analysis once and look inside the ROOT file it wrote:

```bash
rootls -r Telescope/output/dec2026_C1p5/run121/online/online.root | less          # everything (long)
rootls Telescope/output/dec2026_C1p5/run121/analysis/analysis.root:AnalysisEfficiency/MALTA_3   # one directory
```

- The ROOT browser (`root -l online.root`, then `new TBrowser`) works too.
- Replace the plane name by `%DETECTOR%` / `%DUT%` / `%REFERENCE%` to expand it to every plane.
- `OnlineMonitor/…` histograms (e.g. `dut_residual_x_MALTA_3`) are made by the online monitor itself.

### 8.5 Other settings (`[OnlineMonitor]`)

| Key | Current value | Meaning |
|---|---|---|
| `update` | 200 | events between redraws (at most once per second, and at least every 5 s) |
| `target_events` | 500000 (Telescope) / 2000000 (Imaging) | progress-bar target; only counts events with a hit on every RP |
| `auto_save_interval` | 60 | snapshot interval [s] (0 = off) |
| `auto_save_dir` | `"snapshots/"` | snapshot directory (relative to `output_directory`; created by `run_online.sh`) |
| `canvas_title` | — | window title (`run_online.sh` fills in setup and run) |
| `display_max_bins_1d` / `_2d` | 2000 / 300 | finer histograms are drawn through a coarser display copy (saved content unchanged) |

The Tracking4D / AnalysisEfficiency cuts match the offline `analysis.conf`. The online Tracking4D needs
`min_hits_on_track = 6`, so a single RP dropping out leaves no tracks (the Timeline and L1idC canvases show it).

## 9. Trying it on simulation

There are simulations with the same geometry as the prepared setups, so the procedure can be tested before the day.

```bash
# Telescope: ABscan run 15 (A = B = C = 1.5 cm) has the dec2026_C1p5 layout
Telescope/scripts/run_chain.sh --setup dec2026_C1p5 --run 15 --sim-data --events 30000 \
    --steps "mask prealign align align_dut analysis upstream3"
#   -> DUT efficiency 99.99%, residual sigma ~10.8 um (6 planes) / 17.9 um (upstream 3)

# Imaging: MLCC_imaging_EDA run 1 (no sample) and run 3 (MLCCs on a 0.22 mm PCB)
Imaging/scripts/run_imaging.sh --setup dec2026_EDA --sim-data \
    --data-dir /home/hinata/MALTA2/Telescope/sim/output/MLCC_imaging_EDA --align-run 1 --image-run 3
```

Afterwards, delete everything in `geometry/<setup>/` except init.conf (masked, prealigned, aligned,
aligned_dut) and `output/<setup>/` before the beam test: the online monitor would otherwise pick up
the geometry aligned on simulation.

## 10. Caveats

- **`--sim-data` for simulation**: without it, the hardware group-address correction is applied and the hit positions are wrong.
- **`mask_dead_pixels = false`** (Telescope and Imaging): pixels the beam never reaches would be masked as "dead",
  and AnalysisEfficiency then drops nearly every track next to a masked pixel (85 of 30704 tracks left in
  simulation). Only noisy pixels are masked.
- **corry occasionally crashes at exit** (`double free or corruption`): after the results are written, so the
  Telescope scripts warn and continue. If it happens in Imaging, rerun the same command.
- **A setup's geometries are overwritten**: rerunning the alignment of a setup replaces `masked` … `aligned_dut`.
  Use a separate setup for an alignment you want to keep.
- Without `--setup`, the legacy `geometry/*.conf` and `output/<step>/` are used (for compatibility).
- A new analysis config goes into `config/` and runs with
  `Telescope/scripts/run_analysis.py --config ../config/<new>.conf --setup <setup>`
  (output in `output/<setup>/run<N>/<name of the config's output_directory>/`).
- **Do not move the output directories**: the mask results (`mask_file`) are written into the geometry
  as absolute paths. Moving or deleting `output/<setup>/run<N>/mask/` makes that setup's geometry
  unreadable (if you move it, fix the `mask_file` paths in `geometry/<setup>/*.conf` too).
