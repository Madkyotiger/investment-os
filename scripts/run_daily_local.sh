#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${INVESTMENT_OS_ENV_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/investment-os/runtime.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ENV_FILE"
  set +a
elif [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ ! -x .venv/bin/investment-os ]]; then
  printf '%s\n' 'investment-os runtime is missing; run: uv sync --frozen --extra dev --extra market' >&2
  exit 2
fi

exec .venv/bin/investment-os daily "$@"
