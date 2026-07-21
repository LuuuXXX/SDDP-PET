#!/usr/bin/env bash
# DeepSeek as OpenAI-compatible provider for SDDP Dev-Phase 0 (plumbing verification only).
#
# NOTE: per analysis/04-llm-provider-strategy.md the Dev-Phase 0 Go baseline is
# OpenAI (Tier-S Structured Outputs). DeepSeek is Tier-B (json_object only,
# schema enforced client-side via pydantic), so D0-13 compliance may be < 99%.
# Use this for tasks 7.3/7.4 plumbing verification; do NOT re-baseline DoD.
#
# Secret handling: this file reads DEEPSEEK_API_KEY from the environment or from
# a gitignored sibling file `deepseek-env.local.sh`. Copy `deepseek-env.sh.example`
# to `deepseek-env.local.sh` and fill in your key.
#
# Source:  source scripts/deepseek-env.sh

_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_local="${_script_dir}/deepseek-env.local.sh"
if [ -z "${DEEPSEEK_API_KEY:-}" ] && [ -f "$_local" ]; then
    # shellcheck disable=SC1090
    source "$_local"
fi

if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
    echo "[deepseek-env] ERROR: DEEPSEEK_API_KEY not set. Either:" >&2
    echo "[deepseek-env]   - export DEEPSEEK_API_KEY=sk-... before sourcing, or" >&2
    echo "[deepseek-env]   - copy scripts/deepseek-env.sh.example -> scripts/deepseek-env.local.sh" >&2
    echo "[deepseek-env]          and fill in your key (deepseek-env.local.sh is gitignored)" >&2
    return 1 2>/dev/null || exit 1
fi

export OPENAI_API_KEY="$DEEPSEEK_API_KEY"
export OPENAI_BASE_URL="https://api.deepseek.com/v1"
export SDDP_LLM_MODEL="deepseek-chat"
export SDDP_PROVIDER_TIER="B"  # informational: Tier-S=OpenAI, Tier-B=DeepSeek
echo "[deepseek-env] OPENAI_BASE_URL=$OPENAI_BASE_URL  SDDP_LLM_MODEL=$SDDP_LLM_MODEL (Tier-$SDDP_PROVIDER_TIER)"
