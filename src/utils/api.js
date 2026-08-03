/**
 * Centralized Backend API Fetch Utility
 * 
 * Tries candidate backend URLs in priority order:
 * 1. Custom URL from localStorage (user-configured)
 * 2. LAN (192.168.18.49:8000)
 * 3. Tailscale (100.97.146.42:8000)
 * 4. DuckDNS (huz-solar.duckdns.org)
 * 
 * Caches the last-working URL for the session to avoid redundant probing.
 */

const DEFAULT_URLS = [
  'http://192.168.18.49:8000',
  'http://100.97.146.42:8000',
  'https://huz-solar.duckdns.org'
];

let cachedWorkingUrl = null;

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
  const { timeout = 5000, ...fetchOpts } = options;
  
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
