/* Offline support: the app shell is cached on install; deal data is network-first with a cached fallback. */
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
  const isData = url.pathname.includes('/data/');
  if (isData || event.request.mode === 'navigate') {
    // Fresh deals when online, last known deals when offline.
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          if (res.ok) caches.open(VERSION).then((c) => c.put(event.request, res.clone()));
          return res;
        })
        .catch(() => caches.match(event.request, { ignoreSearch: true }).then((r) => r || caches.match('index.html'))),
    );
    return;
  }
  // App files: answer from cache instantly, refresh the cache in the background (next launch gets updates).
  event.respondWith(
    caches.open(VERSION).then((cache) => cache.match(event.request).then((cached) => {
      const fresh = fetch(event.request).then((res) => {
        if (res.ok) cache.put(event.request, res.clone());
        return res;
      }).catch(() => cached);
      return cached || fresh;
    })),
  );
});
