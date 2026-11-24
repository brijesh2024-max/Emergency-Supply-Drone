// Offline viewing for the synthetic exercise. API writes always go to the server.
const CACHE = "aeris-static-v1";
const CORE = [
  ...Array.from(
    { length: 24 },
    (_, i) => "/scene/frames/" + String(i).padStart(2, "0") + ".jpg",
  ),
  "/scene/sos.png",
  "/",
  "/scene/map.png",
  "/scene/camera-still.png",
  "/scene/camera.png",
  "/scene/camera.json",
  "/vendor/leaflet/leaflet.css",
  "/vendor/leaflet/leaflet.js",
  "/fonts/geist.woff2",
  "/fonts/geist-mono.woff2",
];
self.addEventListener("install", (event) =>
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      await cache.addAll(CORE);
      const html = await (await cache.match("/")).text();
      const files = [
        ...html.matchAll(/(?:src|href)="(\/_next\/static\/[^"]+)"/g),
      ].map((m) => m[1].replaceAll("&amp;", "&"));
      await cache.addAll([...new Set(files)]);
      await self.skipWaiting();
    })(),
  ),
);
self.addEventListener("activate", (event) =>
  event.waitUntil(
    (async () => {
      for (const key of await caches.keys()) {
        if (key.startsWith("aeris-static-") && key !== CACHE)
          await caches.delete(key);
      }
      await self.clients.claim();
    })(),
  ),
);
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (
    event.request.method !== "GET" ||
    url.origin !== location.origin ||
    url.pathname.startsWith("/api/") ||
    url.pathname === "/worker.js"
  )
    return;
  if (
    event.request.mode !== "navigate" &&
    !CORE.includes(url.pathname) &&
    !url.pathname.startsWith("/_next/static/")
  )
    return;
  event.respondWith(
    (async () => {
      const cache = await caches.open(CACHE);
      if (event.request.mode !== "navigate") {
        const hit = await cache.match(event.request);
        if (hit) return hit;
      }
      try {
        const res = await fetch(event.request);
        if (res.ok) await cache.put(event.request, res.clone());
        return res;
      } catch (err) {
        const saved =
          (await cache.match(event.request)) || (await cache.match("/"));
        if (saved) return saved;
        throw err;
      }
    })(),
  );
});
