// Cache the app shell so the dashboard loads offline. API/screenshot
// responses are always fetched fresh (never cached).
const CACHE = "plateplayed-v1";
const SHELL = [
    "/",
    "/index.html",
    "/styles.css",
    "/app.js",
    "/manifest.webmanifest",
    "/icon.svg",
];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    const req = event.request;
    const url = new URL(req.url);

    // Never cache live data.
    if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/screenshots/")) {
        return; // default network behaviour
    }

    if (req.mode === "navigate") {
        event.respondWith(fetch(req).catch(() => caches.match("/index.html")));
        return;
    }
    event.respondWith(caches.match(req).then((cached) => cached || fetch(req)));
});
