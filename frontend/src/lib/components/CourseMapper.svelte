<script lang="ts">
	import { onMount } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import type { FeatureCollection } from 'geojson';
	import type { MapperHole } from '$lib/types';
	import { haversineFeet } from '$lib/geo';

	let {
		holes = $bindable(),
		ondeletehole
	}: {
		holes: MapperHole[];
		/** Called for persisted holes; return false to keep the hole (e.g. delete failed) */
		ondeletehole?: (hole: MapperHole) => Promise<boolean>;
	} = $props();

	let mapContainer = $state<HTMLDivElement>();
	let map: maplibregl.Map | null = null;
	let markers: maplibregl.Marker[] = [];
	let loaded = false;
	let error = $state<string | null>(null);
	let locating = $state(false);

	// What the next tap will place
	const nextPlacement = $derived.by(() => {
		const last = holes[holes.length - 1];
		if (last && last.tee && !last.pin) return { kind: 'pin' as const, hole: last.holeNumber };
		const n = holes.length ? Math.max(...holes.map((h) => h.holeNumber)) + 1 : 1;
		return { kind: 'tee' as const, hole: n };
	});

	function holeDistance(h: MapperHole): number | null {
		if (!h.tee || !h.pin) return null;
		return Math.round(haversineFeet(h.tee.lat, h.tee.lng, h.pin.lat, h.pin.lng));
	}

	function linesGeoJSON(): FeatureCollection {
		return {
			type: 'FeatureCollection',
			features: holes
				.filter((h) => h.tee && h.pin)
				.map((h) => ({
					type: 'Feature',
					properties: {},
					geometry: {
						type: 'LineString',
						coordinates: [
							[h.tee!.lng, h.tee!.lat],
							[h.pin!.lng, h.pin!.lat]
						]
					}
				}))
		};
	}

	function makeMarkerEl(kind: 'tee' | 'pin', holeNumber: number): HTMLDivElement {
		const el = document.createElement('div');
		if (kind === 'tee') {
			el.style.cssText =
				'width:22px;height:22px;border-radius:9999px;background:#34d399;border:2px solid #0c1210;' +
				'display:flex;align-items:center;justify-content:center;font:bold 11px sans-serif;color:#0c1210;';
			el.textContent = String(holeNumber);
		} else {
			el.style.cssText =
				'width:16px;height:16px;border-radius:9999px;background:#f97316;border:2px solid #0c1210;' +
				'box-shadow:0 0 0 4px rgba(249,115,22,0.25);';
		}
		return el;
	}

	function syncMap() {
		if (!map || !loaded) return;
		markers.forEach((m) => m.remove());
		markers = [];
		for (const h of holes) {
			for (const kind of ['tee', 'pin'] as const) {
				const pt = h[kind];
				if (!pt) continue;
				// Draggable so GPS-placed points can be nudged to the real spot
				const marker = new maplibregl.Marker({
					element: makeMarkerEl(kind, h.holeNumber),
					draggable: true
				})
					.setLngLat([pt.lng, pt.lat])
					.addTo(map);
				marker.on('dragend', () => {
					const { lng, lat } = marker.getLngLat();
					h[kind] = { lat, lng };
					if (kind === 'tee') h.teeMoved = true;
					else h.pinMoved = true;
					holes = [...holes];
					const source = map?.getSource('hole-lines') as maplibregl.GeoJSONSource | undefined;
					if (source) source.setData(linesGeoJSON());
				});
				markers.push(marker);
			}
		}
		const source = map.getSource('hole-lines') as maplibregl.GeoJSONSource | undefined;
		if (source) source.setData(linesGeoJSON());
	}

	function placePoint(lat: number, lng: number) {
		const last = holes[holes.length - 1];
		if (last && last.tee && !last.pin) {
			last.pin = { lat, lng };
			last.pinMoved = true;
		} else {
			holes.push({ holeNumber: nextPlacement.hole, par: 3, tee: { lat, lng }, pin: null });
		}
		holes = [...holes];
		syncMap();
	}

	function placeAtGps() {
		if (!navigator.geolocation) {
			error = 'GPS not available on this device';
			return;
		}
		locating = true;
		error = null;
		navigator.geolocation.getCurrentPosition(
			(pos) => {
				locating = false;
				placePoint(pos.coords.latitude, pos.coords.longitude);
				map?.flyTo({ center: [pos.coords.longitude, pos.coords.latitude], zoom: 19 });
			},
			(e) => {
				locating = false;
				error = e.message;
			},
			{ enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
		);
	}

	// Undo only walks back unsaved placements; persisted holes use the chip ✕
	const canUndo = $derived(holes.length > 0 && !holes[holes.length - 1].holeId);
	function undo() {
		const last = holes[holes.length - 1];
		if (!last || last.holeId) return;
		if (last.pin) last.pin = null;
		else holes.pop();
		holes = [...holes];
		syncMap();
	}

	async function deleteHole(h: MapperHole) {
		if (h.holeId && ondeletehole) {
			try {
				const ok = await ondeletehole(h);
				if (!ok) return;
			} catch (e) {
				error = (e as Error).message;
				return;
			}
		}
		holes = holes.filter((x) => x !== h);
		syncMap();
	}

	function cyclePar(h: MapperHole) {
		h.par = h.par >= 5 ? 3 : h.par + 1;
		if (h.holeId) h.parChanged = true;
		holes = [...holes];
	}

	function focusHole(h: MapperHole) {
		const pt = h.tee ?? h.pin;
		if (pt) map?.flyTo({ center: [pt.lng, pt.lat], zoom: 18 });
	}

	onMount(() => {
		if (!mapContainer) return;
		map = new maplibregl.Map({
			container: mapContainer,
			style: {
				version: 8,
				sources: {
					satellite: {
						type: 'raster',
						tiles: [
							'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
						],
						tileSize: 256,
						// Esri imagery runs out around z19; upscale instead of blank tiles
						maxzoom: 19,
						attribution: 'Esri'
					}
				},
				layers: [{ id: 'satellite', type: 'raster', source: 'satellite' }]
			},
			center: [-93.5, 41.9],
			zoom: 4,
			attributionControl: false
		});
		map.getCanvas().style.cursor = 'crosshair';

		const geolocate = new maplibregl.GeolocateControl({
			positionOptions: { enableHighAccuracy: true },
			trackUserLocation: true,
			showAccuracyCircle: true
		});
		map.addControl(geolocate, 'top-right');

		map.on('click', (e) => placePoint(e.lngLat.lat, e.lngLat.lng));

		map.on('load', () => {
			map!.resize();
			map!.addSource('hole-lines', { type: 'geojson', data: linesGeoJSON() });
			map!.addLayer({
				id: 'hole-lines',
				type: 'line',
				source: 'hole-lines',
				layout: { 'line-cap': 'round' },
				paint: { 'line-color': '#34d399', 'line-width': 2.5, 'line-dasharray': [0.5, 1.8] }
			});
			loaded = true;
			syncMap();

			// Edit mode: frame the existing course; otherwise go find the player
			const pts = holes.flatMap((h) => [h.tee, h.pin]).filter((p) => p !== null);
			if (pts.length >= 2) {
				const bounds = new maplibregl.LngLatBounds();
				for (const p of pts) bounds.extend([p.lng, p.lat]);
				map!.fitBounds(bounds, { padding: 60, maxZoom: 18 });
			} else {
				geolocate.trigger();
			}
		});

		return () => map?.remove();
	});
</script>

<div class="relative h-[55dvh] overflow-hidden rounded-2xl border border-edge">
	<div bind:this={mapContainer} class="absolute inset-0"></div>

	<!-- What the next tap does -->
	<div
		class="pointer-events-none absolute inset-x-3 top-3 rounded-xl bg-surface/85 p-2.5 text-center text-xs font-semibold backdrop-blur"
	>
		{#if nextPlacement.kind === 'tee'}
			Tap the map to place <span class="text-accent">hole {nextPlacement.hole} tee</span>
		{:else}
			Tap the map to place <span class="text-orange-400">hole {nextPlacement.hole} basket</span>
		{/if}
		<span class="block pt-0.5 font-normal text-ink-dim">drag any marker to fine-tune</span>
	</div>

	{#if error}
		<p class="absolute inset-x-3 bottom-3 rounded-xl bg-red-950/90 p-3 text-xs text-red-300">
			{error}
		</p>
	{/if}
</div>

<div class="flex gap-2 pt-2">
	<button
		type="button"
		class="flex-1 rounded-xl border border-edge bg-card py-2.5 text-xs font-semibold transition active:scale-95 disabled:opacity-50"
		onclick={placeAtGps}
		disabled={locating}
	>
		{locating
			? 'Locating…'
			: `📍 ${nextPlacement.kind === 'tee' ? `Tee ${nextPlacement.hole}` : `Basket ${nextPlacement.hole}`} at my position`}
	</button>
	<button
		type="button"
		class="rounded-xl border border-edge bg-card px-4 py-2.5 text-xs font-semibold text-ink-dim transition active:scale-95 disabled:opacity-40"
		onclick={undo}
		disabled={!canUndo}
	>
		↩ Undo
	</button>
</div>

{#if holes.length > 0}
	<div class="space-y-1.5 pt-2">
		{#each holes as h (h)}
			<div class="flex items-center gap-2 rounded-xl border border-edge bg-card px-3 py-2">
				<button type="button" class="flex-1 text-left text-sm" onclick={() => focusHole(h)}>
					<span class="font-bold text-accent">#{h.holeNumber}</span>
					<span class="text-xs text-ink-dim">
						· {holeDistance(h) !== null ? `${holeDistance(h)} ft` : 'placing…'}
					</span>
				</button>
				<button
					type="button"
					class="rounded-lg border border-edge px-2 py-1 text-xs font-semibold text-ink-dim transition active:scale-95"
					onclick={() => cyclePar(h)}
				>
					Par {h.par}
				</button>
				<button
					type="button"
					class="p-1 text-ink-dim transition hover:text-red-400"
					onclick={() => deleteHole(h)}
					aria-label="Delete hole {h.holeNumber}"
				>
					<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
					</svg>
				</button>
			</div>
		{/each}
	</div>
{/if}
