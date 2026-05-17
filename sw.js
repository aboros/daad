/* Offline shell for DAAD Gathering schedule viewer. Bump when assets or shell change. */

const CACHE_NAME = 'daad-schedule-2026-v43';

const PRECACHE_URLS = [
  './index.html',
  './manifest.json',
  './assets/app.css',
  './assets/fontawesome/css/all.min.css',
  './data/events.json',
  './assets/fonts/barlow-latin-400-italic.woff2',
  './assets/fonts/barlow-latin-400-normal.woff2',
  './assets/fonts/barlow-latin-500-normal.woff2',
  './assets/fonts/barlow-latin-600-normal.woff2',
  './assets/fonts/barlow-latin-700-normal.woff2',
  './assets/fonts/barlow-latin-ext-400-italic.woff2',
  './assets/fonts/barlow-latin-ext-400-normal.woff2',
  './assets/fonts/barlow-latin-ext-500-normal.woff2',
  './assets/fonts/barlow-latin-ext-600-normal.woff2',
  './assets/fonts/barlow-latin-ext-700-normal.woff2',
  './assets/fonts/bebas-neue-latin-400-normal.woff2',
  './assets/fonts/bebas-neue-latin-ext-400-normal.woff2',
  './assets/fontawesome/webfonts/fa-brands-400.woff2',
  './assets/fontawesome/webfonts/fa-regular-400.woff2',
  './assets/fontawesome/webfonts/fa-solid-900.woff2',
  './assets/fontawesome/webfonts/fa-v4compatibility.woff2',
  './assets/icons/icon-192.png',
  './assets/icons/icon-512-maskable.png',
  './assets/icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) =>
        cache.addAll(PRECACHE_URLS.map((path) => new URL(path, self.location).toString())),
      ),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name)),
      ),
    ).then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).catch(() => caches.match(new URL('./index.html', self.location)));
    }),
  );
});
