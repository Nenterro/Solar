/* Solar service worker.
 *
 * Push only. The dashboard is live telemetry, so nothing is cached: a stale
 * reading is worse than a loading screen. The worker exists to show the
 * notifications the home server's push hub sends (see src/utils/push.js) and
 * to open the app at the right page when one is tapped.
 */

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

// Every push must show a notification: iOS withdraws the subscription from an
// app that receives pushes silently.
self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data ? event.data.text() : '' };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || 'Solar', {
      body: data.body || '',
      tag: data.tag,
      icon: '/pwa-192.png',
      data: { url: data.url || '/' }
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = new URL(event.notification.data?.url || '/', self.location.origin).href;
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      for (const client of windows) {
        if ('focus' in client) {
          await client.focus();
          if ('navigate' in client) await client.navigate(url).catch(() => {});
          return;
        }
      }
      await self.clients.openWindow(url);
    })()
  );
});
