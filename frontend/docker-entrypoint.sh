#!/bin/sh
set -eu

js_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

URL="$(js_escape "${REACT_APP_URL:-}")"
BACKEND="$(js_escape "${REACT_APP_BACKEND_URL:-}")"
SPOTIFY_ID="$(js_escape "${REACT_APP_SPOTIFY_CLIENT_ID:-}")"
SPOTIFY_REDIRECT="$(js_escape "${REACT_APP_SPOTIFY_REDIRECT_URI:-}")"
SENTRY="$(js_escape "${REACT_APP_SENTRY_DSN:-}")"

cat > /usr/share/nginx/html/env.js <<EOF
window.__ENV__ = {
  REACT_APP_URL: "${URL}",
  REACT_APP_BACKEND_URL: "${BACKEND}",
  REACT_APP_SPOTIFY_CLIENT_ID: "${SPOTIFY_ID}",
  REACT_APP_SPOTIFY_REDIRECT_URI: "${SPOTIFY_REDIRECT}",
  REACT_APP_SENTRY_DSN: "${SENTRY}"
};
EOF

exec nginx -g 'daemon off;'
