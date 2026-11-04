#!/bin/bash
# =============================================================================
# Imaging online monitor (config/online.conf) for one setup, alongside a running MaltaDAQ run.
# Uses the best geometry the setup already has: aligned > prealigned > masked > init
# (hitmaps and correlations are fine with init.conf; the kink angles need the alignment, so
# align on a no-sample run first: run_imaging.sh --setup <S> --align-run <R> --steps "mask prealign align").
#
# Usage:
#   ./run_online.sh --setup dec2026_EDA --run 12
#   --data-dir DIR   where MaltaDAQ writes run_<NNNNNN>_<0..5>.root (default: ../data)
#   --geometry FILE  use this geometry instead
#   --sim-data       Malta2TreeWriter (Allpix) data
# Needs a display (X11). Snapshots every minute: output/<SETUP>/online/snapshots/
# =============================================================================
set -e

IMG_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CORRY_BIN="${CORRY_BIN:-/home/hinata/package/corryvreckan/bin/corry}"

SETUP=""; RUN=""; GEOMETRY=""; DATA_DIR="${IMG_DIR}/data"; EXTRA=()
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
GEO_DIR="${IMG_DIR}/geometry/${SETUP}"
if [ -z "$GEOMETRY" ]; then
  for G in aligned prealigned masked init; do
    [ -f "${GEO_DIR}/${G}.conf" ] && { GEOMETRY="${GEO_DIR}/${G}.conf"; break; }
  done
fi
[ -n "$GEOMETRY" ] || { echo "no geometry in ${GEO_DIR}/" >&2; exit 1; }
case "$GEOMETRY" in */aligned.conf) ;; *) echo "NOTE: using $(basename "$GEOMETRY") -- the kink angles are only meaningful after alignment" ;; esac

OUT="${IMG_DIR}/output/${SETUP}/online"
mkdir -p "${OUT}/snapshots"  # OnlineMonitor does not create auto_save_dir itself
cd "${IMG_DIR}/config"
exec "$CORRY_BIN" -c online.conf \
  -o "detectors_file=${GEOMETRY}" -o "output_directory=${OUT}" \
  -o "EventLoaderMALTA.run_number=${RUN}" -o "EventLoaderMALTA.base_path=$(cd "$DATA_DIR" && pwd)" \
  -o "OnlineMonitor.canvas_title=\"MALTA2 Imaging - ${SETUP} run ${RUN}\"" "${EXTRA[@]}"
