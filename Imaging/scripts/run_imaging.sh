#!/bin/bash
# =============================================================================
# Material-budget imaging chain for a 6-plane MALTA2 telescope (no DUT), run on
# MaltaDAQ-format files exactly as for real data:
#
#   mask.conf -> prealign.conf -> align.conf      (on the alignment run, no sample)
#   imaging.conf                                  (on each sample run)
#   plot_imaging.py                               (PDF/PNG of the image)
#
# Each step reads the previous step's geometry/*.conf and writes its own; corry's
# histograms and log go to output/<step>/ (imaging: imaging_run<N>.root, one per sample run).
#
# Usage:
#   ./run_imaging.sh --data-dir DIR [--align-run 1] [--image-run "2 3"] [--steps "..."]
#   --data-dir   directory with run_<NNNNNN>_<0..5>.root (default: ../data)
#   --steps      subset of "mask prealign align imaging plot" (default: all)
#   --events N   number_of_events for every corry step (quick test)
#   --image-run  one or more sample runs (imaging + plot are repeated per run)
#   --truth      overlay the nominal MLCC / PCB outlines from the simulation generator
#   --generator  generator file for --truth (default: MLCC_imaging_generate_configs.py)
#   --setup V    use geometry/V/ (starting from geometry/V/init.conf) and output/V/, and write
#                plots to material_imaging/V/, instead of the default geometry and outputs
#                (--variant V is the same; make a setup by copying geometry/template/ to geometry/V/
#                and editing its z positions)
#   --sim-data   Malta2TreeWriter (Allpix) data: EventLoaderMALTA.real_data = false
#                (the configs default to real MaltaDAQ beam-test data)
#
# Simulation: /home/hinata/MALTA2/Telescope/sim/config/MLCC_imaging_run_all.sh
# writes run 1 (no sample), run 2 (MLCC on kapton) and run 3 (MLCC on PCB) into
# sim/output/MLCC_imaging/.
# =============================================================================
set -e

IMG_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CORRY_BIN="${CORRY_BIN:-/home/hinata/package/corryvreckan/bin/corry}"
PYTHON="${PYTHON:-/home/hinata/MALTA2/AnalysisTemplate/Telescope/.venv/bin/python3}"

DATA_DIR="${IMG_DIR}/data"
ALIGN_RUN=1
IMAGE_RUNS="2"
STEPS="mask prealign align imaging plot"
EVENTS=""
VARIANT=""
SIM_DATA=""
PLOT_ARGS=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --data-dir)  DATA_DIR="$2"; shift 2 ;;
    --align-run) ALIGN_RUN="$2"; shift 2 ;;
    --image-run) IMAGE_RUNS="$2"; shift 2 ;;
    --steps)     STEPS="$2"; shift 2 ;;
    --events)    EVENTS="$2"; shift 2 ;;
    --truth)     PLOT_ARGS+=(--truth); shift ;;
    --generator) PLOT_ARGS+=(--generator "$2"); shift 2 ;;
    --variant|--setup) VARIANT="$2"; shift 2 ;;
    --sim-data)  SIM_DATA=1; PLOT_ARGS+=(--sim-data); shift ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done
DATA_DIR="$(cd "$DATA_DIR" && pwd)"  # corry chdir's into output_directory: base_path must be absolute

OUT_ROOT="${IMG_DIR}/output"
if [ -n "$VARIANT" ]; then
  OUT_ROOT="${IMG_DIR}/output/${VARIANT}"
  # beam-test data -> real_analyze, Malta2TreeWriter sim -> simulation_analyze (output/ convention)
  KIND="real_analyze"; [ -n "$SIM_DATA" ] && KIND="simulation_analyze"
  PLOT_ARGS+=(--outdir "/home/hinata/output/plot/MALTA2/${KIND}/material_imaging/${VARIANT}")
fi

run_step() {
  local STEP="$1" RUN="$2"
  local OUT="${OUT_ROOT}/${STEP}"
  mkdir -p "$OUT"
  local CMD=("$CORRY_BIN" -c "${IMG_DIR}/config/${STEP}.conf"
             -o "EventLoaderMALTA.run_number=${RUN}"
             -o "EventLoaderMALTA.base_path=${DATA_DIR}")
  if [ -n "$VARIANT" ]; then
    # same step configs, with this variant's geometry chain and output directory
    local GEO="${IMG_DIR}/geometry/${VARIANT}"
    CMD+=(-o "output_directory=${OUT}")
    case "$STEP" in
      mask)     CMD+=(-o "detectors_file=${GEO}/init.conf"       -o "detectors_file_updated=${GEO}/masked.conf") ;;
      prealign) CMD+=(-o "detectors_file=${GEO}/masked.conf"     -o "detectors_file_updated=${GEO}/prealigned.conf") ;;
      align)    CMD+=(-o "detectors_file=${GEO}/prealigned.conf" -o "detectors_file_updated=${GEO}/aligned.conf") ;;
      imaging)  CMD+=(-o "detectors_file=${GEO}/aligned.conf") ;;
    esac
  fi
  # one histogram file per sample run, so imaging several runs keeps them all
  [ "$STEP" = "imaging" ] && CMD+=(-o "histogram_file=imaging_run${RUN}.root")
  # number_of_events is a global [Corryvreckan] key: pass it unprefixed
  [ -n "$EVENTS" ] && CMD+=(-o "number_of_events=${EVENTS}")
  [ -n "$SIM_DATA" ] && CMD+=(-o "EventLoaderMALTA.real_data=false")
  echo "+ ${CMD[*]}"
  ( cd "${IMG_DIR}/config" && "${CMD[@]}" ) > "${OUT}/run${RUN}_corry.log" 2>&1 \
    || { echo "FAILED: ${STEP} (see ${OUT}/run${RUN}_corry.log)"; exit 1; }
  echo "done: ${STEP} (log: ${OUT}/run${RUN}_corry.log)"
}

for STEP in $STEPS; do
  case "$STEP" in
    mask|prealign|align) run_step "$STEP" "$ALIGN_RUN" ;;
    imaging)             for RUN in $IMAGE_RUNS; do run_step "$STEP" "$RUN"; done ;;
    plot) for RUN in $IMAGE_RUNS; do
            "$PYTHON" "${IMG_DIR}/scripts/plot_imaging.py" "${OUT_ROOT}/imaging/imaging_run${RUN}.root" \
              --run "$RUN" "${PLOT_ARGS[@]}"
          done ;;
    *) echo "unknown step: $STEP" >&2; exit 1 ;;
  esac
done
