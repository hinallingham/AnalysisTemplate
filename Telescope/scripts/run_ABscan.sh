#!/bin/bash
# =============================================================================
# [simulation only] ABscan_C<C> -- data-like analysis of the A = B distance scan with C fixed
# (C=<cm>, required), simulated by <sim_config_dir>/ABscan_run_all.sh.
#
#   A [cm]       : 1.5    2.0    3.0    4.0    5.0    7.0    10     12
#   run (C=1.5)  : 15     20     30     40     50     70     100    120
#   run (C=5)    : 50015  50020  50030  50040  50050  50070  50100  50120
#   (run_<NNNNNN>_<0..6>.root in telescope_data_dir; the run list comes from
#    <sim_config_dir>/ABscan_generate_configs.py --list-runs, sim_config_dir from paths.json)
#
# Per run, scripts/run_chain.sh with setup ABscan_C<C> and alignment run <NNN> (3 digits), starting
# from geometry/ABscan_C<C>/run<NNN>/init.conf written by the generator:
#   prealign -> align -> align_dut -> analysis (6-plane tracking)
#                                  -> upstream3 (tracking with the upstream RP1-3 only)
# all with --sim-data; both analyses use the same 6-plane-aligned aligned_dut.conf.
# NoiseMasking is skipped: sim has no noisy pixels, and mask_dead_pixels would mark everything outside
# the beam spot dead, so AnalysisEfficiency would drop nearly every track. init.conf is used as masked.conf.
# Results: geometry/ABscan_C<C>/run<NNN>/, output/ABscan_C<C>/run<NNN>/<step>/
#
# Usage (from anywhere):
#   C=5 ./run_ABscan.sh                        # all 8 runs
#   C=5 RUNS="50015 50120" ./run_ABscan.sh     # selected runs
#   C=5 EVENTS=50000 ./run_ABscan.sh           # cap events per step (quick test)
#   C=5 UPSTREAM3_ONLY=1 ./run_ABscan.sh       # only the upstream-3 analysis, on the existing aligned_dut.conf
# Logs: output/ABscan_C<C>/run<NNN>/chain.log
# Then: scripts/plot_ABscan_sigma.sh --c "1.5 5"
# =============================================================================
set -e

[ -n "${C}" ] || { echo "set C (cm), e.g. C=5 $0" >&2; exit 1; }

TEL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "${TEL_DIR}/../common/paths.sh"
GEN="${SIM_CONFIG_DIR}/ABscan_generate_configs.py"
SCAN="ABscan_C$(printf '%g' "$C" | tr . p)"
if [ -z "${RUNS}" ]; then
  [ -f "$GEN" ] || { echo "${GEN} not found: set sim_config_dir in paths.json, or give RUNS=\"...\"" >&2; exit 1; }
  RUNS="$(python3 "$GEN" --c "$C" --list-runs | awk '{print $2}' | xargs)"
fi
STEPS="prealign align align_dut analysis upstream3"
[ -n "${UPSTREAM3_ONLY}" ] && STEPS="upstream3"
OPTS=(--sim-data)
[ -n "${EVENTS}" ] && OPTS+=(--events "${EVENTS}")

# check all inputs before starting anything
for RUN in $RUNS; do
  R3=$(printf "%03d" "$RUN"); R6=$(printf "%06d" "$RUN")
  GEO="${TEL_DIR}/geometry/${SCAN}/run${R3}"
  [ -f "${GEO}/init.conf" ] || { echo "missing ${GEO}/init.conf (run the sim generator)" >&2; exit 1; }
  [ -z "${UPSTREAM3_ONLY}" ] || [ -f "${GEO}/aligned_dut.conf" ] \
    || { echo "missing ${GEO}/aligned_dut.conf (run without UPSTREAM3_ONLY first)" >&2; exit 1; }
  for P in 0 1 2 3 4 5 6; do
    [ -f "${TELESCOPE_DATA_DIR}/run_${R6}_${P}.root" ] || { echo "missing ${TELESCOPE_DATA_DIR}/run_${R6}_${P}.root" >&2; exit 1; }
  done
done

START=$(date +%s)
for RUN in $RUNS; do
  R3=$(printf "%03d" "$RUN")
  GEO="${TEL_DIR}/geometry/${SCAN}/run${R3}"
  ANA_OUT="${TEL_DIR}/output/${SCAN}/run${R3}"
  mkdir -p "$ANA_OUT"
  LOG="${ANA_OUT}/chain${UPSTREAM3_ONLY:+_upstream3}.log"
  echo "run ${RUN}: ${STEPS} (log: ${LOG})"
  [ -n "${UPSTREAM3_ONLY}" ] || cp "${GEO}/init.conf" "${GEO}/masked.conf"
  "${TEL_DIR}/scripts/run_chain.sh" --setup "$SCAN" --run "$R3" --steps "$STEPS" "${OPTS[@]}" > "$LOG" 2>&1 \
    || { echo "FAILED: run ${RUN} (see ${LOG})"; exit 1; }
  echo "done:  run ${RUN} ($(( $(date +%s) - START ))s) -> ${ANA_OUT}"
done
echo "All done. Total time: $(( $(date +%s) - START ))s"
