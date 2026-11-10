#!/bin/bash
# =============================================================================
# Telescope chain for one setup (geometry/<SETUP>/run<A>/, output/<SETUP>/run<N>/):
#
#   mask -> prealign -> align -> align_dut      (corry on the alignment run A)
#   analysis [+ upstream3]                       (corry on the analysis run N)
#
# Each step runs corry with config/<step>.conf, then the ROOT macro macros/plot_<step>.C makes the
# summary plot (PDF + PNG) next to corry's output. Needs only bash, corry and ROOT -- no python.
# Machine-dependent paths (corry, ROOT, data directory) come from ../../paths.json.
#
# The setup's z positions are in geometry/<SETUP>/init.conf (copy geometry/template/ and edit the z
# positions, or use dec2026_C1p5). Each alignment gets its own directory geometry/<SETUP>/run<A>/: the
# mask step copies init.conf there, and every step reads the previous step's geometry there and
# writes its own, so aligning another run never overwrites this one:
#   run<A>/init -> masked -> prealigned -> aligned -> aligned_dut
#
# Usage:
#   ./run_chain.sh --setup dec2026_C1p5 --run 120                 # align + analyse run 120
#   ./run_chain.sh --setup dec2026_C1p5 --align-run 120 --run 121 --steps analysis
#                                                   # analyse run 121 with the run-120 alignment
#   ./run_chain.sh --setup dec2026_C1p5 --run 120 --steps prealign      # one step only
#   --data-dir DIR   run_<NNNNNN>_<0..6>.root (default: telescope_data_dir in paths.json)
#   --steps "..."    subset of "mask prealign align align_dut analysis upstream3"
#                    (default: all but upstream3)
#   --align-run N    run for mask/prealign/align/align_dut (default: --run)
#   --events N       number_of_events for every step (quick test)
#   --sim-data       Malta2TreeWriter (Allpix) data instead of MaltaDAQ beam-test data
#   --dut NAME       make NAME the DUT from this step on (default: role = "dut" in the geometry)
#   --analysis-config FILE   config for the analysis step instead of config/analysis.conf (results in
#                    output/<SETUP>/run<N>/<last part of its output_directory>/)
#   --plot-only      skip corry, only redo the plots from the existing ROOT files
# Logs and plots: output/<SETUP>/run<N>/<step>/run<N>_*, N = the run the step reads
# (with --align-run 120 --run 121: alignment steps in run120/, analysis in run121/)
#
# Re-plot by hand (no corry):  root -l -b -q 'macros/plot_prealign.C("<root file>","<out dir>","<run>","MALTA_0,...","MALTA_3")'
# =============================================================================
set -e

TEL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "${TEL_DIR}/../common/paths.sh"

SETUP=""; RUN=""; ALIGN_RUN=""; DUT=""; EVENTS=""; SIM_DATA=""; PLOT_ONLY=""; ANA_CONFIG=""
STEPS="mask prealign align align_dut analysis"
DATA_DIR="$TELESCOPE_DATA_DIR"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --setup)     SETUP="$2"; shift 2 ;;
    --run)       RUN="$2"; shift 2 ;;
    --align-run) ALIGN_RUN="$2"; shift 2 ;;
    --steps)     STEPS="$2"; shift 2 ;;
    --data-dir)  DATA_DIR="$2"; shift 2 ;;
    --events)    EVENTS="$2"; shift 2 ;;
    --sim-data)  SIM_DATA=1; shift ;;
    --dut)       DUT="$2"; shift 2 ;;
    --plot-only) PLOT_ONLY=1; shift ;;
    --analysis-config) ANA_CONFIG="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"; shift 2 ;;
    -h|--help)   sed -n '2,/^# =====/p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done
[ -n "$SETUP" ] && [ -n "$RUN" ] || { echo "usage: $0 --setup NAME --run N [options] (see $0 --help)" >&2; exit 1; }
ALIGN_RUN="${ALIGN_RUN:-$RUN}"
SETUP_GEO="${TEL_DIR}/geometry/${SETUP}"
GEO_DIR="${SETUP_GEO}/run${ALIGN_RUN}"
[ -f "${SETUP_GEO}/init.conf" ] || [ -d "$GEO_DIR" ] \
  || { echo "geometry/${SETUP}/init.conf not found (cp -r geometry/template geometry/${SETUP} and edit its z positions)" >&2; exit 1; }
if [ -z "$PLOT_ONLY" ]; then
  check_tools corry root
  [ -d "$DATA_DIR" ] || { echo "data directory ${DATA_DIR} not found (--data-dir, or telescope_data_dir in paths.json)" >&2; exit 1; }
  DATA_DIR="$(cd "$DATA_DIR" && pwd)"  # corry chdir's into output_directory: base_path must be absolute
else
  check_tools root
fi

# ---- corry INI-like files ---------------------------------------------------------------------
# ini_get FILE SECTION KEY -> value without quotes / comments
ini_get() {
  awk -v sec="$2" -v key="$3" '
    { sub(/#.*/, "") }
    /^[ \t]*\[.*\][ \t]*$/ { s = $0; gsub(/^[ \t]*\[|\][ \t]*$/, "", s); next }
    s == sec && index($0, "=") {
      k = substr($0, 1, index($0, "=") - 1); v = substr($0, index($0, "=") + 1)
      gsub(/^[ \t]+|[ \t]+$/, "", k); gsub(/^[ \t"]+|[ \t"]+$/, "", v)
      if (k == key) { print v; exit }
    }' "$1"
}
ini_has_section() { grep -q "^[[:space:]]*\[$2\]" "$1"; }
# detector names in a geometry file, in file order, comma separated
geo_detectors() { awk '/^[ \t]*\[.*\]/ { s = $0; gsub(/^[ \t]*\[|\][ \t]*$/, "", s); printf "%s%s", (n++ ? "," : ""), s }' "$1"; }
# detector(s) with role = "dut"
geo_dut() {
  awk '{ sub(/#.*/, "") }
       /^[ \t]*\[.*\]/ { s = $0; gsub(/^[ \t]*\[|\][ \t]*$/, "", s); next }
       /^[ \t]*role[ \t]*=/ { v = tolower($0); if (v ~ /"dut"|= *dut/) print s }' "$1"
}

# ---- one corry step ---------------------------------------------------------------------------
run_corry() {  # run_corry CONFIG LOG OVERRIDE...   (overrides as "key=value")
  local config="$1" log="$2"; shift 2
  local cmd=("$CORRY_BIN" -c "$config") o
  for o in "$@"; do
    case "$o" in G:*) cmd+=(-g "${o#G:}") ;; *) cmd+=(-o "$o") ;; esac
  done
  echo "+ ${cmd[*]}"
  mkdir -p "$(dirname "$log")"
  set +e
  ( cd "$(dirname "$config")" && "${cmd[@]}" ) 2>&1 | tee "$log"
  local rc=${PIPESTATUS[0]}
  set -e
  if [ "$rc" -ne 0 ]; then
    # corry occasionally aborts in its teardown ("double free or corruption") after the run is
    # complete: histograms and the updated geometry are already written and the timing table
    # printed. Keep the output in that case.
    if grep -q "Wrote histogram output file" "$log" && grep -q "Wall-clock timing" "$log"; then
      echo "[warn] corry exited with ${rc} AFTER finishing the run (crash at teardown) -- output kept, continuing"
    else
      echo "FAILED: corry exited with ${rc} (log: ${log})" >&2
      exit 1
    fi
  fi
  echo "(corry log saved to ${log})"
}

for STEP in $STEPS; do
  CONFIG="${TEL_DIR}/config/${STEP}.conf"
  N="$ALIGN_RUN"
  case "$STEP" in
    mask)      GEO_IN=init;        GEO_OUT=masked ;;
    prealign)  GEO_IN=masked;      GEO_OUT=prealigned ;;
    align)     GEO_IN=prealigned;  GEO_OUT=aligned ;;
    align_dut) GEO_IN=aligned;     GEO_OUT=aligned_dut ;;
    analysis)  GEO_IN=aligned_dut; GEO_OUT=""; N="$RUN"; CONFIG="${ANA_CONFIG:-$CONFIG}" ;;
    upstream3) GEO_IN=aligned_dut; GEO_OUT=""; N="$RUN"; CONFIG="${TEL_DIR}/config/analysis_upstream3.conf" ;;
    *) echo "unknown step: $STEP" >&2; exit 1 ;;
  esac
  # output/<setup>/run<N>/<last part of the config's output_directory> (e.g. analysis_upstream3)
  OUT_NAME="$(basename "$(ini_get "$CONFIG" Corryvreckan output_directory)")"
  OUT="${TEL_DIR}/output/${SETUP}/run${N}/${OUT_NAME}"
  ROOT_FILE="${OUT}/$(ini_get "$CONFIG" Corryvreckan histogram_file)"
  echo "=== ${STEP} (setup ${SETUP}, run ${N}, alignment run${ALIGN_RUN})"

  if [ "$STEP" = mask ] && [ -z "$PLOT_ONLY" ]; then
    # every alignment starts from a snapshot of the setup's init.conf, kept next to its results
    [ -f "${SETUP_GEO}/init.conf" ] || { echo "geometry/${SETUP}/init.conf not found" >&2; exit 1; }
    mkdir -p "$GEO_DIR"
    cp -p "${SETUP_GEO}/init.conf" "${GEO_DIR}/init.conf"
  fi
  GEO_FILE="${GEO_DIR}/${GEO_IN}.conf"
  [ -f "$GEO_FILE" ] || { echo "${GEO_FILE} not found: run the earlier alignment steps for run ${ALIGN_RUN} first (or pass --align-run with an aligned run)" >&2; exit 1; }
  DETS="$(geo_detectors "$GEO_FILE")"
  CUR_DUT="$(geo_dut "$GEO_FILE")"
  [ "$(echo "$CUR_DUT" | grep -c .)" -le 1 ] || { echo "${GEO_FILE}: more than one detector with role = \"dut\"" >&2; exit 1; }

  OVERRIDES=("EventLoaderMALTA.run_number=$((10#$N))" "EventLoaderMALTA.base_path=${DATA_DIR}"
             "detectors_file=${GEO_FILE}" "output_directory=${OUT}")
  [ -n "$GEO_OUT" ] && OVERRIDES+=("detectors_file_updated=${GEO_DIR}/${GEO_OUT}.conf")
  # number_of_events is a global [Corryvreckan] key: pass it unprefixed
  [ -n "$EVENTS" ] && OVERRIDES+=("number_of_events=${EVENTS}")
  [ -n "$SIM_DATA" ] && OVERRIDES+=("EventLoaderMALTA.real_data=false")

  STEP_DUT="$CUR_DUT"
  if [ -n "$DUT" ] && [ "$DUT" != "$CUR_DUT" ]; then
    echo ",${DETS}," | grep -q ",${DUT}," || { echo "--dut ${DUT}: not in ${GEO_FILE} (${DETS})" >&2; exit 1; }
    # move the dut role with -g overrides (corry writes it into this step's output geometry, so
    # later steps inherit it) and keep the new DUT out of the tracking
    echo "DUT override: ${CUR_DUT:-none} (in $(basename "$GEO_FILE")) -> ${DUT}"
    [ -n "$CUR_DUT" ] && OVERRIDES+=("G:${CUR_DUT}.role=none")
    OVERRIDES+=("G:${DUT}.role=dut")
    if ini_has_section "$CONFIG" Tracking4D; then
      OVERRIDES+=("Tracking4D.require_detectors=$(echo ",${DETS}," | sed "s/,${DUT},/,/; s/^,//; s/,$//")")
    fi
    STEP_DUT="$DUT"
  else
    echo "DUT (from geometry, $(basename "$GEO_FILE")): ${CUR_DUT:-none}"
  fi

  if [ -z "$PLOT_ONLY" ]; then
    run_corry "$CONFIG" "${OUT}/run${N}_corry.log" "${OVERRIDES[@]}"
  fi
  [ -f "$ROOT_FILE" ] || { echo "${ROOT_FILE} not found" >&2; exit 1; }

  case "$STEP" in
    mask)      run_macro "${TEL_DIR}/macros/plot_mask.C"      "$ROOT_FILE" "$OUT" "$N" "$DETS" ;;
    prealign)  run_macro "${TEL_DIR}/macros/plot_prealign.C"  "$ROOT_FILE" "$OUT" "$N" "$DETS" "$STEP_DUT" ;;
    align)     run_macro "${TEL_DIR}/macros/plot_align.C"     "$ROOT_FILE" "$OUT" "$N" ;;
    align_dut) run_macro "${TEL_DIR}/macros/plot_align_dut.C" "$ROOT_FILE" "$OUT" "$N" "$STEP_DUT" ;;
    analysis|upstream3)
               run_macro "${TEL_DIR}/macros/plot_analysis.C"  "$ROOT_FILE" "$OUT" "$N" "$DETS" "$STEP_DUT" ;;
  esac
  [ -n "$GEO_OUT" ] && [ -z "$PLOT_ONLY" ] && echo "Updated geometry written to: ${GEO_DIR}/${GEO_OUT}.conf"
  echo "Summary: ${OUT}/run${N}_summary.png"
done
echo "Done. Geometry: ${GEO_DIR}/   Results: ${TEL_DIR}/output/${SETUP}/run${RUN}/ (alignment: run${ALIGN_RUN}/)"
