#!/usr/bin/env bash
# Launch an OpenAI-compatible vLLM server using a native deployment config.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash pipeline/run-deployment.sh [--dry-run] MODEL_ID [-- VLLM_ARGS...]
  bash pipeline/run-deployment.sh [--dry-run] --config PATH [-- VLLM_ARGS...]

Examples:
  bash pipeline/run-deployment.sh CohereLabs/aya-23-8B
  bash pipeline/run-deployment.sh --dry-run meta-llama/Llama-3.1-8B-Instruct
  CUDA_VISIBLE_DEVICES=0,1 bash pipeline/run-deployment.sh ai4bharat/Airavata -- --tensor-parallel-size 2

MODEL_ID selects configs/model-access/local/open-weight/vllm/<model>.deployment.config.yaml
(replace '/' with '--' in filenames). You may also pass a deployment filename
stem, for example CohereLabs--aya-23-8B.

PATH may be absolute, relative to your current directory, or relative to the
repository root. vLLM runs from that root so custom chat-template paths resolve.
Extra vLLM arguments follow '--' and override YAML values deliberately.
Install vLLM in the active environment; set VLLM_API_KEY for shared server
authentication, HF_TOKEN for gated models, and
CUDA_VISIBLE_DEVICES to choose GPUs. Dry runs do not require vLLM or load weights.
The server runs in the foreground; Ctrl+C stops it.
EOF
}

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd -- "$script_dir/.." && pwd -P)"
python_bin="${PYTHON_BIN:-python}"
command -v "$python_bin" >/dev/null 2>&1 || die 'Activate your Python environment first.'
if [[ "${SURAKSHA_ENV_LOADED:-}" != 1 ]]; then
  exec "$python_bin" "$script_dir/environment.py" --exec bash "$script_dir/run-deployment.sh" "$@"
fi
log_info() { "$python_bin" "$script_dir/logging_utils.py" deployment "$1"; }
config_dir="$repo_root/configs/model-access/local/open-weight/vllm"
dry_run=false
config_path=''
model_id=''
extra_args=()

while (($#)); do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --dry-run) dry_run=true; shift ;;
    --config)
      (($# >= 2)) || die '--config requires a path.'
      [[ -z "$config_path" && -z "$model_id" ]] || die 'Select one model or config.'
      config_path="$2"
      [[ -n "$config_path" ]] || die '--config requires a nonempty path.'
      shift 2 ;;
    --) shift; extra_args=("$@"); break ;;
    -*) die "Unknown launcher option: $1 (pass vLLM options after --)." ;;
    *)
      [[ -z "$config_path" && -z "$model_id" ]] || die 'Select one model or config.'
      model_id="$1"; shift ;;
  esac
done

if [[ -n "$model_id" ]]; then
  config_path="$config_dir/${model_id//\//--}.deployment.config.yaml"
elif [[ -n "$config_path" ]]; then
  if [[ ! -f "$config_path" && "$config_path" != /* ]]; then
    config_path="$repo_root/$config_path"
  fi
else
  usage >&2
  die 'A model ID or --config path is required.'
fi
[[ -f "$config_path" ]] || die "Deployment config not found: $config_path. Hosted API models do not have local vLLM deployments."
if ((${#extra_args[@]})); then
  for arg in "${extra_args[@]}"; do
    [[ "$arg" != --api-key && "$arg" != --api-key=* ]] || die 'Use VLLM_API_KEY for authentication; do not pass a key on the command line.'
  done
fi
config_path="$(cd -- "$(dirname -- "$config_path")" && pwd -P)/$(basename -- "$config_path")"

export PIPELINE_LOG_MODEL="${model_id:-$(basename -- "$config_path" .deployment.config.yaml)}"
export PIPELINE_LOG_RUN_ID="$("$python_bin" -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f"))')"
log_info "Deployment config validated: $config_path"

command_args=(vllm serve --config "$config_path")
if ((${#extra_args[@]})); then
  command_args+=("${extra_args[@]}")
fi
if "$dry_run"; then
  log_info "Previewing deployment config=$config_path"
  printf 'cd %q\n' "$repo_root"
  printf '%q ' "${command_args[@]}"
  printf '\n'
  exit 0
fi

command -v vllm >/dev/null 2>&1 || die 'vllm is not on PATH; activate your vLLM environment.'
[[ -n "${VLLM_API_KEY:-}" ]] || die 'Set VLLM_API_KEY for server authentication.'
log_info "Launching vLLM with deployment config=$config_path; credentials from environment"
cd -- "$repo_root"
exec "${command_args[@]}"
