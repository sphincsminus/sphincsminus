#!/usr/bin/env bash
# Sphincs Minus — one-shot Vercel deploy script.
#
# Pre-requisites:
#   1. `vercel login` (do this once in your terminal)
#   2. populate the env vars below in your shell or a local .env you `source`
#
# Required env vars (NEVER commit these — use direnv / 1Password / Vercel CLI):
#   MINTGATE_ADDRESS         — deployed v2 MintGate
#   SIGNER_PRIVATE_KEY       — signs EIP-712 attestations
#   UPSTASH_REDIS_REST_URL
#   UPSTASH_REDIS_REST_TOKEN
#   RPC_URL                  — mainnet RPC (defaults to llamarpc)

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

: "${MINTGATE_ADDRESS:?set MINTGATE_ADDRESS}"
: "${SIGNER_PRIVATE_KEY:?set SIGNER_PRIVATE_KEY}"
: "${UPSTASH_REDIS_REST_URL:?set UPSTASH_REDIS_REST_URL}"
: "${UPSTASH_REDIS_REST_TOKEN:?set UPSTASH_REDIS_REST_TOKEN}"
RPC_URL="${RPC_URL:-https://eth.llamarpc.com}"

echo ">>> sphincs-minus root: $ROOT"

add_env() {
  local key="$1" value="$2"
  echo "    + $key"
  printf '%s' "$value" | vercel env add "$key" production --force >/dev/null 2>&1 || \
    printf '%s' "$value" | vercel env add "$key" production >/dev/null
}

# ─── 1. backend ──────────────────────────────────────────────────────────────
cd "$ROOT/backend"
echo ">>> linking backend"
vercel link --yes --project sphincs-minus-api 2>&1 | tail -3

echo ">>> setting backend env vars"
add_env UPSTASH_REDIS_REST_URL   "$UPSTASH_REDIS_REST_URL"
add_env UPSTASH_REDIS_REST_TOKEN "$UPSTASH_REDIS_REST_TOKEN"
add_env RPC_URL                  "$RPC_URL"
add_env SIGNER_PRIVATE_KEY       "$SIGNER_PRIVATE_KEY"
add_env MINTGATEV2_ADDRESS       "$MINTGATE_ADDRESS"

echo ">>> deploying backend"
BACKEND_URL=$(vercel deploy --prod --yes 2>&1 | grep -oE 'https://[a-z0-9.-]+\.vercel\.app' | tail -1)
echo ">>> backend deployed: $BACKEND_URL"

# ─── 2. frontend ─────────────────────────────────────────────────────────────
cd "$ROOT/frontend"
echo ">>> linking frontend"
vercel link --yes --project sphincs-minus 2>&1 | tail -3

echo ">>> setting frontend env vars"
add_env NEXT_PUBLIC_BACKEND_URL      "$BACKEND_URL"
add_env NEXT_PUBLIC_MINTGATE_ADDRESS "$MINTGATE_ADDRESS"

echo ">>> deploying frontend"
FRONTEND_URL=$(vercel deploy --prod --yes 2>&1 | grep -oE 'https://[a-z0-9.-]+\.vercel\.app' | tail -1)

echo
echo "════════════════════════════════════════"
echo "  DEPLOY COMPLETE"
echo "════════════════════════════════════════"
echo "  Backend  : $BACKEND_URL"
echo "  Frontend : $FRONTEND_URL"
echo "  MintGate : $MINTGATE_ADDRESS"
echo "════════════════════════════════════════"
