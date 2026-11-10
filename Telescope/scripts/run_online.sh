#!/bin/bash
# =============================================================================
# Online monitor (config/online.conf) for one setup, alongside a running MaltaDAQ run.
# Geometry: the alignment of --align-run A (geometry/<SETUP>/run<A>/, best of aligned_dut > aligned >
# prealigned > init), else the most recent finished alignment of the setup (newest
# run*/aligned_dut.conf), else the setup's init.conf (correlations and hitmaps are fine with it;
# residuals/efficiency need an alignment).
#
# Usage:
#   ./run_online.sh --setup dec2026_C1p5 --run 121
#   --data-dir DIR   where MaltaDAQ writes run_<NNNNNN>_<0..6>.root (default: telescope_data_dir in paths.json)
#   --align-run A    use the alignment made on run A
#   --geometry FILE  use this geometry instead
#   --sim-data       Malta2TreeWriter (Allpix) data
# Needs a display (X11). Snapshots every minute: output/<SETUP>/run<N>/online/snapshots/
# =============================================================================
set -e

TEL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "${TEL_DIR}/../common/paths.sh"   # corry / data paths from paths.json

SETUP=""; RUN=""; ALIGN_RUN=""; GEOMETRY=""; DATA_DIR="${TELESCOPE_DATA_DIR}"; EXTRA=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --setup)    SETUP="$2"; shift 2 ;;
    --run)      RUN="$2"; shift 2 ;;
    --align-run) ALIGN_RUN="$2"; shift 2 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --geometry) GEOMETRY="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"; shift 2 ;;
    --sim-data) EXTRA+=(-o EventLoaderMALTA.real_data=false); shift ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done
[ -n "$SETUP" ] && [ -n "$RUN" ] || { echo "usage: $0 --setup NAME --run N [options] (see header)" >&2; exit 1; }
check_tools corry
GEO_DIR="${TEL_DIR}/geometry/${SETUP}"
if [ -z "$GEOMETRY" ] && [ -n "$ALIGN_RUN" ]; then
  for G in aligned_dut aligned prealigned init; do
    [ -f "${GEO_DIR}/run${ALIGN_RUN}/${G}.conf" ] && geo_ok "${GEO_DIR}/run${ALIGN_RUN}/${G}.conf" && { GEOMETRY="${GEO_DIR}/run${ALIGN_RUN}/${G}.conf"; break; }
  done
  [ -n "$GEOMETRY" ] || { echo "no usable alignment of run ${ALIGN_RUN} in ${GEO_DIR}/run${ALIGN_RUN}/ (align it again with run_chain.sh)" >&2; exit 1; }
fi
if [ -z "$GEOMETRY" ]; then
  # newest finished alignment whose mask files still exist
  for G in $(ls -t "${GEO_DIR}"/run*/aligned_dut.conf 2>/dev/null); do
    geo_ok "$G" && { GEOMETRY="$G"; break; }
  done
  [ -n "$GEOMETRY" ] || GEOMETRY="${GEO_DIR}/init.conf"
fi
[ -f "$GEOMETRY" ] || { echo "no geometry: ${GEOMETRY}" >&2; exit 1; }
geo_ok "$GEOMETRY" || { echo "${GEOMETRY} refers to mask files that no longer exist" >&2; exit 1; }
echo "geometry: ${GEOMETRY}"
case "$GEOMETRY" in */aligned_dut.conf) ;; *) echo "NOTE: using $(basename "$GEOMETRY") -- residuals/efficiency are only meaningful after the alignment chain" ;; esac

OUT="${TEL_DIR}/output/${SETUP}/run${RUN}/online"
mkdir -p "${OUT}/snapshots"  # OnlineMonitor does not create auto_save_dir itself
# base_path must be absolute: corry chdir's into output_directory (see config/online.conf)
cd "${TEL_DIR}/config"
exec "$CORRY_BIN" -c online.conf \
  -o "detectors_file=${GEOMETRY}" -o "output_directory=${OUT}" \
  -o "EventLoaderMALTA.run_number=${RUN}" -o "EventLoaderMALTA.base_path=$(cd "$DATA_DIR" && pwd)" \
  -o "OnlineMonitor.canvas_title=\"MALTA2 Telescope - ${SETUP} run ${RUN}\"" "${EXTRA[@]}"
