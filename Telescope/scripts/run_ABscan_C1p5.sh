#!/bin/bash
# =============================================================================
# ABscan_C1p5 -- data-like analysis of the A = B distance scan (C = 1.5 cm) simulated by
# /home/hinata/MALTA2/Telescope/sim/config/ABscan_C1p5_run_all.sh.
#
#   A [cm] : 1.5  2.0  3.0  4.0  5.0  7.0  10   12
#   run    : 15   20   30   40   50   70   100  120      (data/run_000<run>_<0..6>.root)
#
# Per run, the usual chain starting from geometry/ABscan_C1p5/run<NNN>/init.conf:
#   Prealignment -> Alignment -> AlignmentDUT -> run_analysis (6-plane tracking)
#                                             -> run_analysis --config analysis_upstream3.conf
#                                                (tracking with the upstream RP1-3 only)
# all with --sim-data; both analyses use the same 6-plane-aligned aligned_dut.conf.
# NoiseMasking is skipped (see below): init.conf is used as geometry/masked.conf.
# The step scripts write to the fixed geometry/{masked,prealigned,aligned,aligned_dut}.conf
# and output/<step>/, so after each run those are archived to
#   geometry/ABscan_C1p5/run<NNN>/   and   output/ABscan_C1p5/run<NNN>/<step>/
# The geometry/*.conf and output/<step>/ that were there before are restored at the end.
#
# Usage (from anywhere):
#   ./run_ABscan_C1p5.sh                 # all 8 runs
#   RUNS="15 120" ./run_ABscan_C1p5.sh   # selected runs
#   EVENTS=50000 ./run_ABscan_C1p5.sh    # cap events per step (quick test)
#   UPSTREAM3_ONLY=1 ./run_ABscan_C1p5.sh   # only the upstream-3 analysis, on the aligned_dut.conf
#                                           # already archived in geometry/ABscan_C1p5/run<NNN>/
# Logs: output/ABscan_C1p5/run<NNN>/chain.log
# =============================================================================
set -e

TEL_DIR="/home/hinata/MALTA2/AnalysisTemplate/Telescope"
PYTHON="${PYTHON:-${TEL_DIR}/.venv/bin/python3}"
SCAN="ABscan_C1p5"
RUNS="${RUNS:-15 20 30 40 50 70 100 120}"
STEPS="prealign align align_dut analysis analysis_upstream3"
GEOMS="masked prealigned aligned aligned_dut"
UP3_CONF="${TEL_DIR}/config/analysis_upstream3.conf"

EVENTS_OPT=()
[ -n "${EVENTS}" ] && EVENTS_OPT=(--events "${EVENTS}")

# check all inputs before starting anything
for RUN in $RUNS; do
  R3=$(printf "%03d" "$RUN"); R6=$(printf "%06d" "$RUN")
  [ -f "${TEL_DIR}/geometry/${SCAN}/run${R3}/init.conf" ] \
    || { echo "missing geometry/${SCAN}/run${R3}/init.conf (run the sim generator)" >&2; exit 1; }
  [ -z "${UPSTREAM3_ONLY}" ] || [ -f "${TEL_DIR}/geometry/${SCAN}/run${R3}/aligned_dut.conf" ] \
    || { echo "missing geometry/${SCAN}/run${R3}/aligned_dut.conf (run without UPSTREAM3_ONLY first)" >&2; exit 1; }
  for P in 0 1 2 3 4 5 6; do
    [ -f "${TEL_DIR}/data/run_${R6}_${P}.root" ] \
      || { echo "missing data/run_${R6}_${P}.root" >&2; exit 1; }
  done
done

# set aside whatever chain geometry / step output was there before, put it back on exit
# (also after a failure or Ctrl-C). A leftover BACKUP dir means a previous restore failed.
BACKUP="${TEL_DIR}/output/.${SCAN}_backup"
[ -e "$BACKUP" ] && { echo "${BACKUP} exists -- restore it by hand first" >&2; exit 1; }
mkdir -p "${BACKUP}/geometry" "${BACKUP}/output"
for G in $GEOMS; do
  [ -f "${TEL_DIR}/geometry/${G}.conf" ] && mv "${TEL_DIR}/geometry/${G}.conf" "${BACKUP}/geometry/"
done
for S in $STEPS; do
  [ -d "${TEL_DIR}/output/${S}" ] && mv "${TEL_DIR}/output/${S}" "${BACKUP}/output/"
done
restore() {
  for G in $GEOMS; do
    rm -f "${TEL_DIR}/geometry/${G}.conf"
    [ -f "${BACKUP}/geometry/${G}.conf" ] && mv "${BACKUP}/geometry/${G}.conf" "${TEL_DIR}/geometry/"
  done
  for S in $STEPS; do
    rm -rf "${TEL_DIR}/output/${S}"
    [ -d "${BACKUP}/output/${S}" ] && mv "${BACKUP}/output/${S}" "${TEL_DIR}/output/"
  done
  rm -rf "${BACKUP}"
}
trap restore EXIT

cd "${TEL_DIR}/scripts"
START=$(date +%s)
for RUN in $RUNS; do
  R3=$(printf "%03d" "$RUN")
  GEO_OUT="${TEL_DIR}/geometry/${SCAN}/run${R3}"
  ANA_OUT="${TEL_DIR}/output/${SCAN}/run${R3}"
  mkdir -p "${ANA_OUT}"
  # no stale geometry from the previous run may leak into this one
  for G in $GEOMS; do rm -f "${TEL_DIR}/geometry/${G}.conf"; done
  for S in $STEPS; do rm -rf "${TEL_DIR}/output/${S}"; done
  if [ -n "${UPSTREAM3_ONLY}" ]; then
    LOG="${ANA_OUT}/chain_upstream3.log"
    echo "run ${RUN}: upstream-3 analysis only (log: ${LOG})"
    cp "${GEO_OUT}/aligned_dut.conf" "${TEL_DIR}/geometry/aligned_dut.conf"
    "$PYTHON" run_analysis.py "$RUN" --sim-data "${EVENTS_OPT[@]}" --config "$UP3_CONF" > "$LOG" 2>&1 \
      || { echo "FAILED: run ${RUN} (see ${LOG})"; exit 1; }
    rm -rf "${ANA_OUT:?}/analysis_upstream3"; cp -rp "${TEL_DIR}/output/analysis_upstream3" "${ANA_OUT}/"
    echo "done:  run ${RUN} ($(( $(date +%s) - START ))s) -> ${ANA_OUT}/analysis_upstream3"
    continue
  fi
  LOG="${ANA_OUT}/chain.log"
  echo "run ${RUN}: analysing (log: ${LOG})"
  # && chain: set -e is ignored inside a "{ ...; } || ..." list, so stop explicitly on the first failure
  {
    # NoiseMasking is skipped: sim has no noisy pixels, and mask_dead_pixels marks everything
    # outside the beam spot (~86k of 115k pixels) dead, so AnalysisEfficiency would drop nearly
    # every track as "next to a masked pixel". Prealignment reads geometry/masked.conf, so the
    # chain starts from this run's init.conf in its place.
    cp "${GEO_OUT}/init.conf" "${TEL_DIR}/geometry/masked.conf" &&
    "$PYTHON" Prealignment.py "$RUN" --sim-data "${EVENTS_OPT[@]}" &&
    "$PYTHON" Alignment.py    "$RUN" --sim-data "${EVENTS_OPT[@]}" &&
    "$PYTHON" AlignmentDUT.py "$RUN" --sim-data "${EVENTS_OPT[@]}" &&
    "$PYTHON" run_analysis.py "$RUN" --sim-data "${EVENTS_OPT[@]}" &&
    "$PYTHON" run_analysis.py "$RUN" --sim-data "${EVENTS_OPT[@]}" --config "$UP3_CONF"
  } > "$LOG" 2>&1 || { echo "FAILED: run ${RUN} (see ${LOG})"; exit 1; }
  for G in $GEOMS; do cp -p "${TEL_DIR}/geometry/${G}.conf" "${GEO_OUT}/"; done
  for S in $STEPS; do rm -rf "${ANA_OUT:?}/${S}"; cp -rp "${TEL_DIR}/output/${S}" "${ANA_OUT}/"; done
  echo "done:  run ${RUN} ($(( $(date +%s) - START ))s) -> ${ANA_OUT}"
done
echo "All done. Total time: $(date -u -d @$(( $(date +%s) - START )) +"%H時間%M分%S秒")"
