# =============================================================================
# common/paths.sh -- machine-dependent paths for every script in this repository.
#
# Sourced by the run_*.sh scripts. Reads <repo>/paths.json (one per machine, not in git;
# start from paths.example.json):
#
#   env_setup           script sourced first to get ROOT/corry into the environment
#                       (e.g. thisroot.sh or an LCG setup.sh), "" = environment is already set up
#   corry_bin           corry executable ("corry" = take it from PATH)
#   root_bin            root executable ("root" = take it from PATH)
#   telescope_data_dir  default --data-dir of Telescope/ (run_<NNNNNN>_<0..6>.root)
#   imaging_data_dir    default --data-dir of Imaging/   (run_<NNNNNN>_<0..5>.root)
#   plot_dir            where Imaging / ABscan plots go: <plot_dir>/{real,simulation}_analyze/<category>/
#                       ("" = inside the output/ tree of this repository)
#   sim_config_dir      Allpix sim configs (ABscan_generate_configs.py), only for the sim-only ABscan scripts
#
# Relative paths are relative to the repository root. Environment variables override the file:
# PATHS_JSON (another json file), ENV_SETUP, CORRY_BIN, ROOT_BIN, TELESCOPE_DATA_DIR,
# IMAGING_DATA_DIR, PLOT_DIR, SIM_CONFIG_DIR.
# =============================================================================

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATHS_JSON="${PATHS_JSON:-${REPO_DIR}/paths.json}"

if [ ! -f "$PATHS_JSON" ]; then
  echo "ERROR: ${PATHS_JSON} not found." >&2
  echo "       cp ${REPO_DIR}/paths.example.json ${REPO_DIR}/paths.json  and edit it for this machine." >&2
  exit 1
fi

# json_get KEY -- string value of a top-level key ("" if missing). Uses jq when installed, else a
# plain sed reader that handles the flat {"key": "value", ...} layout of paths.json.
json_get() {
  if command -v jq > /dev/null 2>&1; then
    jq -r --arg k "$1" '.[$k] // "" | tostring' "$PATHS_JSON"
  else
    sed -n "s/^[[:space:]]*\"$1\"[[:space:]]*:[[:space:]]*\"\(.*\)\"[[:space:]]*,\{0,1\}[[:space:]]*$/\1/p" "$PATHS_JSON" | head -1
  fi
}

# abs_path P -- P made absolute against the repository root ("" stays "")
abs_path() {
  case "$1" in
    "") echo "" ;;
    /*) echo "$1" ;;
    "~"*) echo "${HOME}${1#\~}" ;;
    *) echo "${REPO_DIR}/$1" ;;
  esac
}

# a bare command name ("corry", "root") is looked up in PATH, anything with a / is a path
cmd_path() {
  case "$1" in */*) abs_path "$1" ;; *) echo "$1" ;; esac
}

ENV_SETUP="${ENV_SETUP:-$(abs_path "$(json_get env_setup)")}"
CORRY_BIN="${CORRY_BIN:-$(cmd_path "$(json_get corry_bin)")}"
ROOT_BIN="${ROOT_BIN:-$(cmd_path "$(json_get root_bin)")}"
TELESCOPE_DATA_DIR="${TELESCOPE_DATA_DIR:-$(abs_path "$(json_get telescope_data_dir)")}"
IMAGING_DATA_DIR="${IMAGING_DATA_DIR:-$(abs_path "$(json_get imaging_data_dir)")}"
PLOT_DIR="${PLOT_DIR:-$(abs_path "$(json_get plot_dir)")}"
SIM_CONFIG_DIR="${SIM_CONFIG_DIR:-$(abs_path "$(json_get sim_config_dir)")}"
CORRY_BIN="${CORRY_BIN:-corry}"
ROOT_BIN="${ROOT_BIN:-root}"
TELESCOPE_DATA_DIR="${TELESCOPE_DATA_DIR:-${REPO_DIR}/Telescope/data}"
IMAGING_DATA_DIR="${IMAGING_DATA_DIR:-${REPO_DIR}/Imaging/data}"

if [ -n "$ENV_SETUP" ]; then
  [ -f "$ENV_SETUP" ] || { echo "ERROR: env_setup ${ENV_SETUP} (paths.json) not found" >&2; exit 1; }
  # setup scripts are often not written for "set -eu"
  set +eu
  # shellcheck disable=SC1090
  source "$ENV_SETUP"
  set -e
fi

check_tools() {  # check_tools corry root ...
  local t b
  for t in "$@"; do
    case "$t" in corry) b="$CORRY_BIN" ;; root) b="$ROOT_BIN" ;; *) b="$t" ;; esac
    command -v "$b" > /dev/null 2>&1 \
      || { echo "ERROR: ${t} not found (${b}) -- set ${t}_bin / env_setup in ${PATHS_JSON}" >&2; exit 1; }
  done
}

# run_macro MACRO.C 'ARG1' 'ARG2' ... -- run a ROOT macro in batch mode. Arguments are passed as
# C++ string literals, except when they start with "=" (then the rest is passed verbatim, e.g. =3.5).
run_macro() {
  local macro="$1"; shift
  local args="" a
  for a in "$@"; do
    [ -n "$args" ] && args+=","
    case "$a" in
      =*) args+="${a#=}" ;;
      *)  a="${a//\\/\\\\}"; args+="\"${a//\"/\\\"}\"" ;;
    esac
  done
  "$ROOT_BIN" -l -b -q "${macro}(${args})"
}

# plot_kind_dir CATEGORY SIM(0/1) [SUBDIR] -- <plot_dir>/{real,simulation}_analyze/CATEGORY[/SUBDIR], or "" if
# plot_dir is not set (the caller then falls back to its own output/ tree)
plot_kind_dir() {
  [ -n "$PLOT_DIR" ] || { echo ""; return; }
  local kind="real_analyze"; [ "$2" = 1 ] && kind="simulation_analyze"
  echo "${PLOT_DIR}/${kind}/$1${3:+/$3}"
}

# geo_ok GEOMETRY -- true if every mask_file the geometry points at exists. A geometry written by the
# mask step refers to output/.../mask/ with an absolute path, so it breaks when that output is deleted
# or the geometry comes from another machine.
geo_ok() {
  local f bad=0
  while IFS= read -r f; do
    case "$f" in /*) ;; *) f="$(dirname "$1")/$f" ;; esac
    [ -f "$f" ] || { [ "$bad" = 1 ] || echo "  [skip] $1: its mask_file ${f} (and maybe more) no longer exists" >&2; bad=1; }
  done < <(sed -n 's/^[[:space:]]*mask_file[[:space:]]*=[[:space:]]*"\{0,1\}\([^"#]*\)"\{0,1\}.*/\1/p' "$1" | sed 's/[[:space:]]*$//')
  return $bad
}
