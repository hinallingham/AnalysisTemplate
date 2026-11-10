#!/bin/bash
# =============================================================================
# x/X0 calibration of the material-budget image with Al plates (macros/calibrate_xx0.C, see there
# for the model). Needs the imaging step of every calibration run first:
#   scripts/run_imaging.sh --setup V --image-run "1 10 11 12 13 14 15 16" --steps "imaging"
#
# Usage:
#   ./calibrate_xx0.sh --setup V --calib "1:0 10:0.1 11:0.2 12:0.5 13:1 14:2 15:5 16:10" --image-run "2 3"
#   --calib "RUN:T_MM ..."  calibration runs and their Al thickness in mm (0 = run without sample), >= 4
#   --image-run "N ..."    runs to convert to x/X0 (MLCC_run<N>_xx0.{pdf,png,root})
#   --momentum MEV         beam momentum (default 3000)
#   --setup V              read output/V/imaging/ (default: output/imaging/)
#   --sim-data             plots go to simulation_analyze instead of real_analyze
# Output: <plot_dir>/{real,simulation}_analyze/material_imaging/V/calib/ when plot_dir is set in
# paths.json, else output/V/plots/calib/  (calib_curve, calib_fit.txt, MLCC_run<N>_xx0)
# =============================================================================
set -e
IMG_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "${IMG_DIR}/../common/paths.sh"

VARIANT=""; CALIB=""; IMAGE_RUNS=""; MOMENTUM=3000; SIM_DATA=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --setup|--variant) VARIANT="$2"; shift 2 ;;
    --calib)     CALIB="$2"; shift 2 ;;
    --image-run) IMAGE_RUNS="$2"; shift 2 ;;
    --momentum)  MOMENTUM="$2"; shift 2 ;;
    --sim-data)  SIM_DATA=1; shift ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done
[ -n "$CALIB" ] || { echo "usage: $0 --calib \"RUN:T_MM ...\" [--image-run \"N ...\"] [--setup V] (see header)" >&2; exit 1; }
check_tools root

OUT_ROOT="${IMG_DIR}/output${VARIANT:+/${VARIANT}}"
OUT="$(plot_kind_dir material_imaging "$SIM_DATA" "${VARIANT}")"
OUT="${OUT:+${OUT}/calib}"
OUT="${OUT:-${OUT_ROOT}/plots/calib}"
run_macro "${IMG_DIR}/macros/calibrate_xx0.C" "${OUT_ROOT}/imaging" "$OUT" "$CALIB" "$IMAGE_RUNS" "=${MOMENTUM}"
echo "Output: ${OUT}"
