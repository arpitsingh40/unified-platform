// Meta Pixel event helper. The base pixel + PageView is loaded in /public/index.html.
// All conversion events go through trackPixel() so calls stay no-ops if the pixel is
// blocked (ad blocker, SSR, etc.) and we never throw inside an analytics call.
export function trackPixel(eventName, params) {
  try {
    if (typeof window === 'undefined') return;
    const fbq = window.fbq;
    if (typeof fbq !== 'function') return;
    if (params && Object.keys(params).length > 0) {
      fbq('track', eventName, params);
    } else {
      fbq('track', eventName);
    }
  } catch (_e) {
    // never let analytics break the app
  }
}
