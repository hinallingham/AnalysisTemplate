#!/bin/bash
# =============================================================================
# Online monitor (config/online.conf) for one setup, alongside a running MaltaDAQ run.
# Uses the best geometry the setup already has: aligned_dut > aligned > prealigned > init
# (correlations and hitmaps are fine with init.conf; residuals/efficiency need an alignment).
#
# Usage:
#   ./run_online.sh --setup dec2026_C1p5 --run 121
#   --data-dir DIR   where MaltaDAQ writes run_<NNNNNN>_<0..6>.root (default: ../data)
#   --geometry FILE  use this geometry instead
#   --sim-data       Malta2TreeWriter (Allpix) data
# Needs a display (X11). Snapshots every minute: output/<SETUP>/run<N>/online/snapshots/
# =============================================================================
set -e

TEL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CORRY_BIN="${CORRY_BIN:-/home/hinata/package/corryvreckan/bin/corry}"

SETUP=""; RUN=""; GEOMETRY=""; DATA_DIR="${TEL_DIR}/data"; EXTRA=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --setup)    SETUP="$2"; shift 2 ;;
    --run)      RUN="$2"; shift 2 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --geometry) GEOMETRY="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"; shift 2 ;;
    --sim-data) EXTRA+=(-o EventLoaderMALTA.real_data=false); shift ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done
[ -n "$SETUP" ] && [ -n "$RUN" ] || { echo "usage: $0 --setup NAME --run N [options] (see header)" >&2; exit 1; }
GEO_DIR="${TEL_DIR}/geometry/${SETUP}"
if [ -z "$GEOMETRY" ]; then
  for G in aligned_dut aligned prealigned init; do
    [ -f "${GEO_DIR}/${G}.conf" ] && { GEOMETRY="${GEO_DIR}/${G}.conf"; break; }
  done
fi
[ -n "$GEOMETRY" ] || { echo "no geometry in ${GEO_DIR}/" >&2; exit 1; }
case "$GEOMETRY" in */aligned_dut.conf) ;; *) echo "NOTE: using $(basename "$GEOMETRY") -- residuals/efficiency are only meaningful after the alignment chain" ;; esac

OUT="${TEL_DIR}/output/${SETUP}/run${RUN}/online"
mkdir -p "${OUT}/snapshots"  # OnlineMonitor does not create auto_save_dir itself
# base_path must be absolute: corry chdir's into output_directory (see config/online.conf)
cd "${TEL_DIR}/config"
exec "$CORRY_BIN" -c online.conf \
  -o "detectors_file=${GEOMETRY}" -o "output_directory=${OUT}" \
  -o "EventLoaderMALTA.run_number=${RUN}" -o "EventLoaderMALTA.base_path=$(cd "$DATA_DIR" && pwd)" \
  -o "OnlineMonitor.canvas_title=\"MALTA2 Telescope - ${SETUP} run ${RUN}\"" "${EXTRA[@]}"
