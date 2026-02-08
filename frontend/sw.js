// Service Worker for StripAlerts Setup PWA
const CACHE_NAME = "stripalerts-cache-v3-testing";

// Install - skip waiting
self.addEventListener("install", (event) => {
  self.skipWaiting();
});

// Activate - delete ALL caches for testing
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) =>
        Promise.all(cacheNames.map((cacheName) => caches.delete(cacheName))),
      )
      .then(() => self.clients.claim()),
  );
});

// Fetch - network only for testing
self.addEventListener("fetch", (event) => {
  return;
});
