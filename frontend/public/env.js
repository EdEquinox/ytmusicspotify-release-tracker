# Runtime config for production (Docker/nginx). Overwritten by docker-entrypoint.sh.
# Local `yarn start` falls back to process.env / .env files.
window.__ENV__ = window.__ENV__ || {}
