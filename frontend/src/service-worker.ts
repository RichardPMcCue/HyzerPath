/// <reference types="@sveltejs/kit" />
/// <reference lib="webworker" />

import { build, files, version } from '$service-worker';

const sw = self as unknown as ServiceWorkerGlobalScope;
const CACHE = `hyzerpath-${version}`;
const ASSETS = [...build, ...files];

sw.addEventListener('install', (event) => {
	event.waitUntil(
		caches
			.open(CACHE)
			.then((cache) => cache.addAll(ASSETS))
			.then(() => sw.skipWaiting())
	);
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(
		caches.keys().then(async (keys) => {
			for (const key of keys) {
				if (key !== CACHE) await caches.delete(key);
			}
			await sw.clients.claim();
		})
	);
});

sw.addEventListener('fetch', (event) => {
	if (event.request.method !== 'GET') return;
	// Stay out of the way during development — vite serves everything
	if (import.meta.env.DEV) return;

	const url = new URL(event.request.url);

	// Never cache API calls or map tiles — always go to the network.
	// /tiles/ and /api/ are same-origin (proxied by nginx) but shouldn't
	// fill the app-shell cache.
	if (url.origin !== sw.location.origin) return;
	if (url.pathname.startsWith('/tiles/') || url.pathname.startsWith('/api/')) return;

	event.respondWith(
		(async () => {
			const cache = await caches.open(CACHE);

			// App shell assets: cache-first
			if (ASSETS.includes(url.pathname)) {
				const cached = await cache.match(url.pathname);
				if (cached) return cached;
			}

			// Everything else: network-first with cache fallback (offline support)
			try {
				const response = await fetch(event.request);
				if (response.ok) cache.put(event.request, response.clone());
				return response;
			} catch {
				const cached = await cache.match(event.request);
				if (cached) return cached;
				// SPA fallback for navigations while offline
				const fallback = await cache.match('/index.html');
				if (fallback) return fallback;
				return Response.error();
			}
		})()
	);
});
