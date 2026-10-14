#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
python_bin="${PYTHON_BIN:-python}"
command -v "$python_bin" >/dev/null 2>&1 || { echo 'Activate your Python environment first.' >&2; exit 1; }
exec "$python_bin" "$script_dir/environment.py" --python "$script_dir/generate_safety_dashboard.py" "$@"
