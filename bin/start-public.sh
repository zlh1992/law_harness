#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

if [[ -z "${PUBLIC_ACCESS_PASSWORD:-}" || "${PUBLIC_ACCESS_PASSWORD:-}" == "请替换为随机高强度口令" ]]; then
  echo "请先在 $ROOT_DIR/.env 设置 PUBLIC_ACCESS_PASSWORD。" >&2
  exit 2
fi

mkdir -p "$ROOT_DIR/.logs" "$ROOT_DIR/.data"
PID_FILE="$ROOT_DIR/.data/public-stack.pid"
PROXY_LOG="$ROOT_DIR/.logs/proxy.log"
HARNESS_LOG="$ROOT_DIR/.logs/harness.log"
GATEWAY_LOG="$ROOT_DIR/.logs/public-gateway.log"
TUNNEL_LOG="$ROOT_DIR/.logs/public-tunnel.log"
CLOUDFLARED_BIN="${CLOUDFLARED_BIN:-$ROOT_DIR/.tools/cloudflared}"
PUBLIC_TUNNEL_MODE="${PUBLIC_TUNNEL_MODE:-quick}"
TAILSCALE_BIN="${TAILSCALE_BIN:-/usr/local/bin/tailscale}"

case "$PUBLIC_TUNNEL_MODE" in
  named)
    if [[ ! -x "$CLOUDFLARED_BIN" ]]; then
      echo "Stable public access requires cloudflared at $CLOUDFLARED_BIN." >&2
      exit 2
    fi
    TOKEN_FILE="${PUBLIC_TUNNEL_TOKEN_FILE:-$ROOT_DIR/.data/cloudflare-tunnel.token}"
    if [[ "$TOKEN_FILE" != /* ]]; then TOKEN_FILE="$ROOT_DIR/$TOKEN_FILE"; fi
    if [[ ! -s "$TOKEN_FILE" ]]; then
      echo "Named tunnel token file is missing or empty: $TOKEN_FILE" >&2
      exit 2
    fi
    if [[ -z "${PUBLIC_URL:-}" || ! "$PUBLIC_URL" =~ ^https://[A-Za-z0-9.-]+/?$ ]]; then
      echo "Named tunnel mode requires PUBLIC_URL=https://your-host.example.com in .env." >&2
      exit 2
    fi
    PUBLIC_URL="${PUBLIC_URL%/}"
    ;;
  tailscale)
    if [[ ! -x "$TAILSCALE_BIN" ]]; then
      echo "Tailscale Funnel requires the CLI at $TAILSCALE_BIN." >&2
      exit 2
    fi
    if ! TAILSCALE_BE_CLI=1 "$TAILSCALE_BIN" status --json 2>/dev/null | rg -q '"BackendState": "Running"'; then
      echo "Tailscale is not connected; open the Tailscale app and sign in first." >&2
      exit 2
    fi
    ;;
  quick) ;;
  *)
    echo "Invalid PUBLIC_TUNNEL_MODE=$PUBLIC_TUNNEL_MODE; expected quick, named, or tailscale." >&2
    exit 2
    ;;
esac

cleanup() {
  if [[ "${TAILSCALE_FUNNEL_STARTED:-}" == "1" ]]; then
    TAILSCALE_BE_CLI=1 "$TAILSCALE_BIN" funnel --https=443 off >/dev/null 2>&1 || true
  fi
  for child in "${TUNNEL_PID:-}" "${GATEWAY_PID:-}" "${HARNESS_PID:-}" "${PROXY_PID:-}"; do
    [[ -n "$child" ]] && kill "$child" 2>/dev/null || true
  done
  rm -f "$PID_FILE"
}
trap cleanup EXIT INT TERM

"$ROOT_DIR/bin/start-proxy.sh" >"$PROXY_LOG" 2>&1 &
PROXY_PID=$!
"$ROOT_DIR/bin/start-harness.sh" "$ROOT_DIR" >"$HARNESS_LOG" 2>&1 &
HARNESS_PID=$!

for _ in {1..30}; do
  if curl -fsS --max-time 2 "http://127.0.0.1:${HARNESS_PORT:-3080}/" >/dev/null 2>&1; then break; fi
  sleep 1
done
if ! curl -fsS --max-time 2 "http://127.0.0.1:${HARNESS_PORT:-3080}/" >/dev/null 2>&1; then
  cat "$HARNESS_LOG" >&2
  exit 1
fi

"$ROOT_DIR/bin/start-public-gateway.sh" >"$GATEWAY_LOG" 2>&1 &
GATEWAY_PID=$!
for _ in {1..10}; do
  if curl -fsS --max-time 2 "http://127.0.0.1:${PUBLIC_GATEWAY_PORT:-4180}/healthz" >/dev/null 2>&1; then break; fi
  sleep 1
done
if ! curl -fsS --max-time 2 "http://127.0.0.1:${PUBLIC_GATEWAY_PORT:-4180}/healthz" >/dev/null 2>&1; then
  cat "$GATEWAY_LOG" >&2
  exit 1
fi

printf '%s\n' "$$" > "$PID_FILE"
case "$PUBLIC_TUNNEL_MODE" in
  named)
    echo "All local services started. Connecting the Cloudflare named tunnel."
    "$CLOUDFLARED_BIN" tunnel --no-autoupdate --protocol "${CLOUDFLARED_PROTOCOL:-auto}" run --token-file "$TOKEN_FILE" >"$TUNNEL_LOG" 2>&1 &
    TUNNEL_PID=$!
    for _ in {1..30}; do
      if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
        cat "$TUNNEL_LOG" >&2
        exit 1
      fi
      if curl -fsS --max-time 3 "$PUBLIC_URL/healthz" >/dev/null 2>&1; then
        echo "Public URL: $PUBLIC_URL"
        echo "Tunnel: Cloudflare named tunnel (stable hostname)"
        echo "It is protected by the PUBLIC_ACCESS_PASSWORD in .env."
        wait "$TUNNEL_PID"
        exit $?
      fi
      sleep 1
    done
    echo "Named tunnel is running, but $PUBLIC_URL/healthz was not reachable within 30 seconds." >&2
    echo "Check that the Cloudflare published application maps $PUBLIC_URL to http://localhost:${PUBLIC_GATEWAY_PORT:-4180}; inspect $TUNNEL_LOG." >&2
    wait "$TUNNEL_PID"
    ;;
  tailscale)
    echo "All local services started. Enabling Tailscale Funnel on HTTPS port 443."
    TAILSCALE_BE_CLI=1 "$TAILSCALE_BIN" funnel --bg --yes --https=443 "http://127.0.0.1:${PUBLIC_GATEWAY_PORT:-4180}"
    TAILSCALE_FUNNEL_STARTED=1
    PUBLIC_URL="$(TAILSCALE_BE_CLI=1 "$TAILSCALE_BIN" status --json | node -e 'let s="";process.stdin.on("data",c=>s+=c).on("end",()=>{const d=JSON.parse(s).Self.DNSName||"";process.stdout.write(d ? `https://${d.replace(/\.$/, "")}` : "")})')"
    if [[ -z "$PUBLIC_URL" ]]; then
      echo "Tailscale is connected, but its stable DNS name is unavailable." >&2
      exit 1
    fi
    for _ in {1..30}; do
      if curl -fsS --max-time 3 "$PUBLIC_URL/healthz" >/dev/null 2>&1; then
        echo "Public URL: $PUBLIC_URL"
        echo "Tunnel: Tailscale Funnel (stable hostname)"
        echo "It is protected by the PUBLIC_ACCESS_PASSWORD in .env."
        wait "$GATEWAY_PID"
        exit $?
      fi
      sleep 1
    done
    echo "Tailscale Funnel is configured, but $PUBLIC_URL/healthz was not reachable within 30 seconds." >&2
    TAILSCALE_BE_CLI=1 "$TAILSCALE_BIN" funnel status >&2 || true
    wait "$GATEWAY_PID"
    ;;
  quick)
    if [[ -x "$CLOUDFLARED_BIN" ]]; then
      echo "All local services started. Creating a Cloudflare HTTPS Quick Tunnel; the URL will appear below."
      "$CLOUDFLARED_BIN" tunnel --no-autoupdate --protocol http2 --url "http://127.0.0.1:${PUBLIC_GATEWAY_PORT:-4180}" >"$TUNNEL_LOG" 2>&1 &
      TUNNEL_PID=$!
      TUNNEL_URL_PATTERN='https://[[:alnum:]-]+\.trycloudflare\.com'
      TUNNEL_NAME='Cloudflare Quick Tunnel'
    else
      echo "All local services started. cloudflared is unavailable; using HTTPS LocalTunnel fallback."
      npx --yes localtunnel --port "${PUBLIC_GATEWAY_PORT:-4180}" --local-host 127.0.0.1 >"$TUNNEL_LOG" 2>&1 &
      TUNNEL_PID=$!
      TUNNEL_URL_PATTERN='https://[^[:space:]]+\.loca\.lt'
      TUNNEL_NAME='LocalTunnel fallback'
    fi

    for _ in {1..30}; do
      URL="$(rg -o "$TUNNEL_URL_PATTERN" "$TUNNEL_LOG" 2>/dev/null | head -n 1 || true)"
      if [[ -n "$URL" ]]; then
        echo "Public URL: $URL"
        echo "Tunnel: $TUNNEL_NAME"
        echo "It is protected by the PUBLIC_ACCESS_PASSWORD in .env."
        wait "$TUNNEL_PID"
        exit $?
      fi
      sleep 1
    done

    echo "$TUNNEL_NAME started but did not report its URL within 30 seconds; inspect $TUNNEL_LOG." >&2
    wait "$TUNNEL_PID"
    ;;
esac
