/**
 * Read env from runtime `window.__ENV__` (Docker/nginx) or CRA `process.env` (local yarn start).
 *
 * @param {string} key
 * @param {string} [fallback]
 * @returns {string}
 */
export function getRuntimeEnv(key, fallback = '') {
  const runtime =
    typeof window !== 'undefined' && window.__ENV__ && typeof window.__ENV__ === 'object'
      ? window.__ENV__[key]
      : undefined
  if (runtime != null && String(runtime) !== '') return String(runtime)

  const buildTime = process.env[key]
  if (buildTime != null && String(buildTime) !== '') return String(buildTime)

  return fallback
}
