import type { StyleSpecification } from 'maplibre-gl';

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
