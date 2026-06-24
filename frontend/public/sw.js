const CACHE_NAME = 'fbgp-v1';

self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  const { request } = event;

  if (request.method !== 'GET') return;

  event.respondWith(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      const cached = await cache.match(request);
      if (cached) return cached;

      try {
        const response = await fetch(request);
        if (response && response.status === 200) {
          await cache.put(request, response.clone());
        }
        return response;
      } catch (err) {
        return new Response(
          '{"error":"offline","message":"503 Service Unavailable: 你目前離線，此資源未被快取。"}',
          {
            status: 503,
            statusText: 'Service Unavailable',
            headers: { 'Content-Type': 'application/json; charset=utf-8' },
          }
        );
      }
    })()
  );
});
