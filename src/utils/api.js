/**
 * Centralized Backend API Fetch Utility
 *
 * Tries candidate backend URLs in priority order:
 *   1. Custom URL from localStorage ("solar_custom_backend_url")
 *   2. DuckDNS  (https://huz-solar.duckdns.org:8888)
 *   3. LAN      (http://192.168.18.49:8000)
 *
 * Note: when the dashboard itself is served over HTTPS, the browser blocks the
 * plain-http LAN candidate as mixed content, so that fallback only works when
 * the app is opened over http on the local network.
 *
 * Caches the last-working URL for the session to avoid redundant probing, and
 * attaches the API token (if one is configured) to every request.
 */

const DEFAULT_URLS = [
  'https://huz-solar.duckdns.org:8888',
  'http://192.168.18.49:8000'
];

let cachedWorkingUrl = null;

const TOKEN_KEY = 'solar_api_token';

/**
 * Token required by the backend's write endpoints when SOLAR_API_TOKEN is set
 * on the server. Read-only endpoints ignore it.
 */
export function getApiToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

export function setApiToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable (private mode) */
  }
}

function withAuthHeaders(options) {
  const token = getApiToken();
  if (!token) return options;
  return { ...options, headers: { ...(options.headers || {}), 'X-Solar-Token': token } };
}

export function getCandidateUrls() {
  const custom = localStorage.getItem('solar_custom_backend_url');
  const candidates = [custom, ...DEFAULT_URLS].filter(Boolean);
  // Deduplicate
  return [...new Set(candidates)];
}

/**
 * Fetch JSON from the backend API, trying candidate URLs in order.
 * Caches the first working URL for subsequent calls.
 * 
 * @param {string} endpoint - API endpoint path (e.g. '/api/telemetry')
 * @param {object} options - Optional fetch options (method, body, signal, timeout)
 * @returns {Promise<any>} Parsed JSON response
 * @throws {Error} If all candidate URLs fail
 */
export async function fetchFromBackend(endpoint, options = {}) {
  const { timeout = 5000, ...rest } = options;
  const fetchOpts = withAuthHeaders(rest);
  
  // If we have a cached working URL, try it first
  if (cachedWorkingUrl) {
    try {
      const res = await fetch(`${cachedWorkingUrl}${endpoint}`, {
        ...fetchOpts,
        signal: fetchOpts.signal || AbortSignal.timeout(timeout)
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      // Cached URL failed, clear cache and try all candidates
      cachedWorkingUrl = null;
    }
  }
  
  // Try all candidate URLs
  const candidates = getCandidateUrls();
  let lastError = null;
  
  for (const baseUrl of candidates) {
    try {
      const res = await fetch(`${baseUrl}${endpoint}`, {
        ...fetchOpts,
        signal: fetchOpts.signal || AbortSignal.timeout(timeout)
      });
      if (res.ok) {
        cachedWorkingUrl = baseUrl;
        return await res.json();
      }
    } catch (err) {
      lastError = err;
    }
  }
  
  throw lastError || new Error('All backend URLs unreachable');
}

/**
 * Reset the cached working URL (useful when user changes settings).
 */
export function resetCachedUrl() {
  cachedWorkingUrl = null;
}

/**
 * Get the currently cached working URL.
 */
export function getCachedUrl() {
  return cachedWorkingUrl;
}

// Also export the candidate list for pages that need raw access (Settings diagnostics)
export { DEFAULT_URLS };
