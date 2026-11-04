#!/bin/bash
# =============================================================================
# Full telescope chain for one setup (geometry/<SETUP>/, output/<SETUP>/run<N>/):
#
#   NoiseMasking -> Prealignment -> Alignment -> AlignmentDUT     (on the alignment run)
#   run_analysis (6-plane tracking) [+ analysis_upstream3]        (on the analysis run)
#
# The setup starts from geometry/<SETUP>/init.conf (copy geometry/template/ and edit the z
# positions, or use dec2026_C1p5). Each step reads the previous step's geometry there and writes its own:
#   init -> masked -> prealigned -> aligned -> aligned_dut
#
# Usage:
#   ./run_chain.sh --setup dec2026_C1p5 --run 120                 # align + analyse run 120
#   ./run_chain.sh --setup dec2026_C1p5 --align-run 120 --run 121 --steps analysis
#                                                   # analyse run 121 with the run-120 alignment
#   --data-dir DIR   run_<NNNNNN>_<0..6>.root (default: ../data)
#   --steps "..."    subset of "mask prealign align align_dut analysis upstream3"
#                    (default: all but upstream3)
#   --align-run N    run for mask/prealign/align/align_dut (default: --run)
#   --events N       number_of_events for every step (quick test)
#   --sim-data       Malta2TreeWriter (Allpix) data instead of MaltaDAQ beam-test data
# Logs and plots: output/<SETUP>/run<N>/<step>/run<N>_*, N = the run the step reads
# (with --align-run 120 --run 121: alignment steps in run120/, analysis in run121/)
# =============================================================================
set -e

TEL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-${TEL_DIR}/.venv/bin/python3}"

SETUP=""
RUN=""
ALIGN_RUN=""
STEPS="mask prealign align align_dut analysis"
OPTS=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --setup)     SETUP="$2"; shift 2 ;;
    --run)       RUN="$2"; shift 2 ;;
    --align-run) ALIGN_RUN="$2"; shift 2 ;;
    --steps)     STEPS="$2"; shift 2 ;;
    --data-dir)  OPTS+=(--data-dir "$(cd "$2" && pwd)"); shift 2 ;;
    --events)    OPTS+=(--events "$2"); shift 2 ;;
    --sim-data)  OPTS+=(--sim-data); shift ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done
[ -n "$SETUP" ] && [ -n "$RUN" ] || { echo "usage: $0 --setup NAME --run N [options] (see header)" >&2; exit 1; }
ALIGN_RUN="${ALIGN_RUN:-$RUN}"
[ -f "${TEL_DIR}/geometry/${SETUP}/init.conf" ] \
  || { echo "geometry/${SETUP}/init.conf not found (cp -r geometry/template geometry/${SETUP} and edit its z positions)" >&2; exit 1; }

cd "${TEL_DIR}/scripts"
for STEP in $STEPS; do
  case "$STEP" in
    mask)      CMD=(NoiseMasking.py "$ALIGN_RUN") ;;
    prealign)  CMD=(Prealignment.py "$ALIGN_RUN") ;;
    align)     CMD=(Alignment.py "$ALIGN_RUN") ;;
    align_dut) CMD=(AlignmentDUT.py "$ALIGN_RUN") ;;
    analysis)  CMD=(run_analysis.py "$RUN") ;;
    upstream3) CMD=(run_analysis.py "$RUN" --config "${TEL_DIR}/config/analysis_upstream3.conf") ;;
    *) echo "unknown step: $STEP" >&2; exit 1 ;;
  esac
  echo "=== ${STEP} (setup ${SETUP}, run ${CMD[1]})"
  "$PYTHON" "${CMD[@]}" --setup "$SETUP" "${OPTS[@]}"
done
echo "Done. Geometry: ${TEL_DIR}/geometry/${SETUP}/   Results: ${TEL_DIR}/output/${SETUP}/run${RUN}/ (alignment: run${ALIGN_RUN}/)"
