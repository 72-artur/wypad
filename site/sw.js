/* Offline support: app shell cached on install; code and data network-first, fonts/icons cache-first. */
const VERSION = 'wypad-v1';
const SHELL = [
  './', 'index.html', 'styles.css', 'app.js', 'manifest.webmanifest',
  'fonts/fonts.css', 'fonts/big-shoulders-display-latin.woff2', 'fonts/big-shoulders-display-latin-ext.woff2',
  'fonts/figtree-latin.woff2', 'fonts/figtree-latin-ext.woff2',
  'icons/sprite.svg', 'icons/icon.svg', 'icons/icon-192.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  const immutable = url.pathname.includes('/fonts/') || url.pathname.includes('/icons/');
  if (immutable) {
    event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
    return;
  }
  // Code and data: always the fresh version when online (no stale app.js after a deploy),
  // the last cached copy when offline.
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        if (res.ok) caches.open(VERSION).then((c) => c.put(event.request, res.clone()));
        return res;
      })
      .catch(() => caches.match(event.request, { ignoreSearch: true })
        .then((r) => r || (event.request.mode === 'navigate' ? caches.match('index.html') : undefined))),
  );
});
