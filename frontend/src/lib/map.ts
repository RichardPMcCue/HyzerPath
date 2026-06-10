import type { Map as MapLibreMap, StyleSpecification } from 'maplibre-gl';

/**
 * Keep the canvas in sync with its container. MapLibre measures the container
 * once at construction — if flex/dvh layout settles afterwards (mobile URL bar,
 * PWA chrome, font load) the canvas stays at the stale (possibly zero) size
 * and the map looks blank. Returns a cleanup function.
 */
export function autoResize(map: MapLibreMap, container: HTMLElement): () => void {
	const observer = new ResizeObserver(() => map.resize());
	observer.observe(container);
	return () => observer.disconnect();
}

/**
 * Esri World Imagery, proxied through our own origin (`/tiles/...` → nginx →
 * server.arcgisonline.com). Third-party tile requests get killed by tracker
 * blockers (Vivaldi shields, uBlock) — same-origin requests don't.
 * In dev, vite.config.ts proxies /tiles the same way.
 */
export function satelliteStyle(): StyleSpecification {
	return {
		version: 8,
		sources: {
			satellite: {
				type: 'raster',
				tiles: [`${window.location.origin}/tiles/{z}/{y}/{x}`],
				tileSize: 256,
				// Esri imagery runs out around z19; upscale instead of blank tiles
				maxzoom: 19,
				attribution: 'Esri'
			}
		},
		layers: [{ id: 'satellite', type: 'raster', source: 'satellite' }]
	};
}
