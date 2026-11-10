#!/bin/bash
# =============================================================================
# [simulation only] DUT residual sigma vs A = B for one or more ABscans (macros/plot_ABscan_sigma.C).
# Reads output/ABscan_C<C>/run<NNN>/{analysis,analysis_upstream3}/ written by scripts/run_ABscan.sh.
#
# Usage:
#   ./plot_ABscan_sigma.sh --c 1.5
#   ./plot_ABscan_sigma.sh --c "1.5 5"
#   --dut NAME   DUT detector (default MALTA_3)
# The run table (run, A=B) comes from <sim_config_dir>/ABscan_generate_configs.py --list-runs.
# Output: <plot_dir>/simulation_analyze/residual/ when plot_dir is set in paths.json, else
# output/ABscan_plots/   (ABscan_C<C>[_C<C2>...]_dut_sigma_vs_AB.{pdf,png,json})
# =============================================================================
set -e
TEL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "${TEL_DIR}/../common/paths.sh"

CS="1.5"; DUT="MALTA_3"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --c)   CS="$2"; shift 2 ;;
    --dut) DUT="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done
check_tools root
GEN="${SIM_CONFIG_DIR}/ABscan_generate_configs.py"
[ -f "$GEN" ] || { echo "${GEN} not found: set sim_config_dir in paths.json" >&2; exit 1; }

SPEC=""
for C in $CS; do
  RUNS="$(python3 "$GEN" --c "$C" --list-runs | awk '{printf "%s%s:%s", (n++ ? "," : ""), $2, $3}')"
  SPEC+="${SPEC:+;}ABscan_C$(printf '%g' "$C" | tr . p)|${C}|${RUNS}"
done
OUT="$(plot_kind_dir residual 1)"
OUT="${OUT:-${TEL_DIR}/output/ABscan_plots}"
run_macro "${TEL_DIR}/macros/plot_ABscan_sigma.C" "${TEL_DIR}/output" "$OUT" "$SPEC" "$DUT"
