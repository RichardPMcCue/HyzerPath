<script lang="ts">
	import { onMount } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import type { Feature, FeatureCollection } from 'geojson';
	import { autoResize, satelliteStyle } from '$lib/map';
	import type { MapperHazard, MapperHole } from '$lib/types';
	import { haversineFeet, orderFairwayWaypoints } from '$lib/geo';

	let {
		holes = $bindable(),
		ondeletehole
	}: {
		holes: MapperHole[];
		/** Called for persisted holes; return false to keep the hole (e.g. delete failed) */
		ondeletehole?: (hole: MapperHole) => Promise<boolean>;
	} = $props();

	type Mode = 'layout' | 'fairway' | 'hazard';
	const HAZARD_TYPES = ['ob', 'water', 'trees'] as const;
	const HAZARD_COLORS: Record<string, string> = {
		ob: '#ef4444',
		water: '#38bdf8',
		trees: '#a3e635'
	};

	let mapContainer = $state<HTMLDivElement>();
	let map: maplibregl.Map | null = null;
	let markers: maplibregl.Marker[] = [];
	let loaded = false;
	let error = $state<string | null>(null);
	let locating = $state(false);

	let mode = $state<Mode>('layout');
	let draftHazard = $state<{ lat: number; lng: number }[]>([]);
	let draftType = $state<string>('ob');

	// Fairway/hazard taps apply to the selected hole (tap a hole chip to
	// switch), defaulting to the most recent hole with a tee
	let selectedHoleNumber = $state<number | null>(null);
	const activeHole = $derived(
		holes.find((h) => h.holeNumber === selectedHoleNumber && h.tee) ??
			[...holes].reverse().find((h) => h.tee) ??
			null
	);

	// Keep the corridor sane: waypoints always follow the best-fit chain from
	// tee to pin, no matter what order they were tapped or dragged in
	function applyFairwayOrder(h: MapperHole) {
		if (!h.tee || h.fairway.length < 2) return;
		const ordered = orderFairwayWaypoints(h.tee, h.fairway, h.pin);
		if (ordered.some((wp, i) => wp !== h.fairway[i])) {
			h.fairway = ordered;
			if (h.holeId) h.fairwayChanged = true;
		}
	}

	// What the next tap will place in layout mode
	const nextPlacement = $derived.by(() => {
		const last = holes[holes.length - 1];
		if (last && last.tee && !last.pin) return { kind: 'pin' as const, hole: last.holeNumber };
		const n = holes.length ? Math.max(...holes.map((h) => h.holeNumber)) + 1 : 1;
		return { kind: 'tee' as const, hole: n };
	});

	function holeChain(h: MapperHole): { lat: number; lng: number }[] {
		return [h.tee, ...h.fairway, h.pin].filter((p) => p !== null) as {
			lat: number;
			lng: number;
		}[];
	}

	function holeDistance(h: MapperHole): number | null {
		if (!h.tee || !h.pin) return null;
		const chain = holeChain(h);
		let total = 0;
		for (let i = 0; i < chain.length - 1; i++) {
			total += haversineFeet(chain[i].lat, chain[i].lng, chain[i + 1].lat, chain[i + 1].lng);
		}
		return Math.round(total);
	}

	function linesGeoJSON(): FeatureCollection {
		return {
			type: 'FeatureCollection',
			features: holes
				.filter((h) => holeChain(h).length >= 2)
				.map((h) => ({
					type: 'Feature',
					properties: {},
					geometry: {
						type: 'LineString',
						coordinates: holeChain(h).map((p) => [p.lng, p.lat])
					}
				}))
		};
	}

	function hazardsGeoJSON(): FeatureCollection {
		const features: Feature[] = [];
		for (const h of holes) {
			for (const hz of h.hazards) {
				if (hz.polygon.length < 3) continue;
				const ring = hz.polygon.map((p) => [p.lng, p.lat]);
				ring.push(ring[0]);
				features.push({
					type: 'Feature',
					properties: { color: HAZARD_COLORS[hz.hazard_type] ?? '#ef4444' },
					geometry: { type: 'Polygon', coordinates: [ring] }
				});
			}
		}
		return { type: 'FeatureCollection', features };
	}

	function draftGeoJSON(): FeatureCollection {
		if (draftHazard.length < 2) return { type: 'FeatureCollection', features: [] };
		return {
			type: 'FeatureCollection',
			features: [
				{
					type: 'Feature',
					properties: {},
					geometry: {
						type: 'LineString',
						coordinates: draftHazard.map((p) => [p.lng, p.lat])
					}
				}
			]
		};
	}

	function makeMarkerEl(kind: 'tee' | 'pin' | 'waypoint' | 'vertex', holeNumber?: number) {
		const el = document.createElement('div');
		if (kind === 'tee') {
			el.style.cssText =
				'width:22px;height:22px;border-radius:9999px;background:#34d399;border:2px solid #0c1210;' +
				'display:flex;align-items:center;justify-content:center;font:bold 11px sans-serif;color:#0c1210;';
			el.textContent = String(holeNumber);
		} else if (kind === 'pin') {
			el.style.cssText =
				'width:16px;height:16px;border-radius:9999px;background:#f97316;border:2px solid #0c1210;' +
				'box-shadow:0 0 0 4px rgba(249,115,22,0.25);';
		} else if (kind === 'waypoint') {
			el.style.cssText =
				'width:12px;height:12px;border-radius:9999px;background:#2dd4bf;border:2px solid #0c1210;';
		} else {
			el.style.cssText =
				'width:10px;height:10px;border-radius:9999px;background:#ef4444;border:2px solid #0c1210;';
		}
		return el;
	}

	function setSource(id: string, data: FeatureCollection) {
		const source = map?.getSource(id) as maplibregl.GeoJSONSource | undefined;
		if (source) source.setData(data);
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
					applyFairwayOrder(h);
					holes = [...holes];
					syncMap();
				});
				markers.push(marker);
			}
			for (const wp of h.fairway) {
				const marker = new maplibregl.Marker({
					element: makeMarkerEl('waypoint'),
					draggable: true
				})
					.setLngLat([wp.lng, wp.lat])
					.addTo(map);
				marker.on('dragend', () => {
					const { lng, lat } = marker.getLngLat();
					wp.lat = lat;
					wp.lng = lng;
					wp.moved = true;
					applyFairwayOrder(h);
					holes = [...holes];
					syncMap();
				});
				markers.push(marker);
			}
		}
		for (const v of draftHazard) {
			markers.push(
				new maplibregl.Marker({ element: makeMarkerEl('vertex') })
					.setLngLat([v.lng, v.lat])
					.addTo(map)
			);
		}
		setSource('hole-lines', linesGeoJSON());
		setSource('hazards', hazardsGeoJSON());
		setSource('hazard-draft', draftGeoJSON());
	}

	function placePoint(lat: number, lng: number) {
		error = null;
		if (mode === 'hazard') {
			draftHazard = [...draftHazard, { lat, lng }];
			syncMap();
			return;
		}
		if (mode === 'fairway') {
			if (!activeHole) {
				error = 'Place a tee first, then add fairway waypoints';
				return;
			}
			activeHole.fairway.push({ lat, lng });
			if (activeHole.holeId) activeHole.fairwayChanged = true;
			applyFairwayOrder(activeHole);
			holes = [...holes];
			syncMap();
			return;
		}
		const last = holes[holes.length - 1];
		if (last && last.tee && !last.pin) {
			last.pin = { lat, lng };
			last.pinMoved = true;
			applyFairwayOrder(last);
		} else {
			holes.push({
				holeNumber: nextPlacement.hole,
				par: 3,
				tee: { lat, lng },
				pin: null,
				fairway: [],
				hazards: []
			});
			selectedHoleNumber = nextPlacement.hole;
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

	function closeDraftHazard() {
		if (!activeHole) {
			error = 'Place a tee first — hazards belong to a hole';
			return;
		}
		if (draftHazard.length < 3) {
			error = 'Tap at least 3 points to outline the area';
			return;
		}
		activeHole.hazards.push({ hazard_type: draftType, polygon: draftHazard });
		draftHazard = [];
		holes = [...holes];
		syncMap();
	}

	function removeHazard(h: MapperHole, hz: MapperHazard) {
		if (hz.hazardId) {
			h.removedHazardIds = [...(h.removedHazardIds ?? []), hz.hazardId];
		}
		h.hazards = h.hazards.filter((x) => x !== hz);
		holes = [...holes];
		syncMap();
	}

	const canUndo = $derived.by(() => {
		if (mode === 'hazard') return draftHazard.length > 0;
		if (mode === 'fairway') return (activeHole?.fairway.length ?? 0) > 0;
		return holes.length > 0 && !holes[holes.length - 1].holeId;
	});

	function undo() {
		if (mode === 'hazard') {
			draftHazard = draftHazard.slice(0, -1);
			syncMap();
			return;
		}
		if (mode === 'fairway') {
			if (!activeHole || activeHole.fairway.length === 0) return;
			const wp = activeHole.fairway.pop()!;
			if (wp.nodeId) {
				activeHole.removedNodeIds = [...(activeHole.removedNodeIds ?? []), wp.nodeId];
			}
			if (activeHole.holeId) activeHole.fairwayChanged = true;
			holes = [...holes];
			syncMap();
			return;
		}
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
		selectedHoleNumber = h.holeNumber;
		const pt = h.tee ?? h.pin;
		if (pt) map?.flyTo({ center: [pt.lng, pt.lat], zoom: 18 });
	}

	onMount(() => {
		if (!mapContainer) return;
		map = new maplibregl.Map({
			container: mapContainer,
			style: satelliteStyle(),
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
			map!.addSource('hazards', { type: 'geojson', data: hazardsGeoJSON() });
			map!.addLayer({
				id: 'hazard-fill',
				type: 'fill',
				source: 'hazards',
				paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.25 }
			});
			map!.addLayer({
				id: 'hazard-outline',
				type: 'line',
				source: 'hazards',
				paint: { 'line-color': ['get', 'color'], 'line-width': 1.5, 'line-opacity': 0.8 }
			});
			map!.addSource('hazard-draft', { type: 'geojson', data: draftGeoJSON() });
			map!.addLayer({
				id: 'hazard-draft-line',
				type: 'line',
				source: 'hazard-draft',
				paint: { 'line-color': '#ef4444', 'line-width': 2, 'line-dasharray': [1, 1.5] }
			});
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
			const pts = holes.flatMap((h) => holeChain(h));
			if (pts.length >= 2) {
				const bounds = new maplibregl.LngLatBounds();
				for (const p of pts) bounds.extend([p.lng, p.lat]);
				map!.fitBounds(bounds, { padding: 60, maxZoom: 18 });
			} else {
				geolocate.trigger();
			}
		});

		const stopResize = autoResize(map, mapContainer);
		return () => {
			stopResize();
			map?.remove();
		};
	});
</script>

<!-- Mode switcher -->
<div class="flex gap-1 rounded-xl border border-edge bg-card p-1">
	{#each [['layout', '📍 Tee · Basket'], ['fairway', '〰 Fairway'], ['hazard', '⚠️ Hazard']] as [m, label] (m)}
		<button
			type="button"
			class="flex-1 rounded-lg py-2 text-xs font-semibold transition active:scale-95
				{mode === m ? 'bg-accent text-surface' : 'text-ink-dim'}"
			onclick={() => {
				mode = m as Mode;
				error = null;
			}}
		>
			{label}
		</button>
	{/each}
</div>

<div class="relative mt-2 h-[55dvh] overflow-hidden rounded-2xl border border-edge">
	<!-- h-full instead of absolute: maplibre's CSS forces position:relative
	     on this element, which would collapse an inset-0 box to 0 height -->
	<div bind:this={mapContainer} class="h-full w-full"></div>

	<!-- What the next tap does -->
	<div
		class="pointer-events-none absolute inset-x-3 top-3 rounded-xl bg-surface/85 p-2.5 text-center text-xs font-semibold backdrop-blur"
	>
		{#if mode === 'layout'}
			{#if nextPlacement.kind === 'tee'}
				Tap the map to place <span class="text-accent">hole {nextPlacement.hole} tee</span>
			{:else}
				Tap the map to place <span class="text-orange-400">hole {nextPlacement.hole} basket</span>
			{/if}
			<span class="block pt-0.5 font-normal text-ink-dim">drag any marker to fine-tune</span>
		{:else if mode === 'fairway'}
			{#if activeHole}
				Tap along the fairway of <span class="text-teal-300">hole {activeHole.holeNumber}</span>
				<span class="block pt-0.5 font-normal text-ink-dim">
					any order works — the line auto-fits tee → pin · tap a hole below to switch
				</span>
			{:else}
				Place a tee first (Tee · Basket mode)
			{/if}
		{:else if activeHole}
			Outline a <span style="color:{HAZARD_COLORS[draftType]}">{draftType}</span> area on
			<span class="text-teal-300">hole {activeHole.holeNumber}</span>
			<span class="block pt-0.5 font-normal text-ink-dim">
				tap corners in order, then “Close area” · {draftHazard.length} point{draftHazard.length ===
				1
					? ''
					: 's'} · tap a hole below to switch
			</span>
		{:else}
			Place a tee first (Tee · Basket mode)
		{/if}
	</div>

	{#if error}
		<p class="absolute inset-x-3 bottom-3 rounded-xl bg-red-950/90 p-3 text-xs text-red-300">
			{error}
		</p>
	{/if}
</div>

{#if mode === 'hazard'}
	<div class="flex gap-2 pt-2">
		{#each HAZARD_TYPES as t (t)}
			<button
				type="button"
				class="rounded-xl border px-3 py-2 text-xs font-semibold transition active:scale-95
					{draftType === t ? 'border-transparent text-surface' : 'border-edge bg-card text-ink-dim'}"
				style={draftType === t ? `background:${HAZARD_COLORS[t]}` : ''}
				onclick={() => (draftType = t)}
			>
				{t.toUpperCase()}
			</button>
		{/each}
		<button
			type="button"
			class="flex-1 rounded-xl bg-accent py-2 text-xs font-bold text-surface transition active:scale-95 disabled:opacity-50"
			onclick={closeDraftHazard}
			disabled={draftHazard.length < 3}
		>
			✓ Close area
		</button>
		<button
			type="button"
			class="rounded-xl border border-edge bg-card px-3 py-2 text-xs font-semibold text-ink-dim transition active:scale-95 disabled:opacity-40"
			onclick={undo}
			disabled={!canUndo}
		>
			↩
		</button>
	</div>
{:else}
	<div class="flex gap-2 pt-2">
		<button
			type="button"
			class="flex-1 rounded-xl border border-edge bg-card py-2.5 text-xs font-semibold transition active:scale-95 disabled:opacity-50"
			onclick={placeAtGps}
			disabled={locating}
		>
			{#if locating}
				Locating…
			{:else if mode === 'fairway'}
				📍 Waypoint at my position
			{:else}
				📍 {nextPlacement.kind === 'tee'
					? `Tee ${nextPlacement.hole}`
					: `Basket ${nextPlacement.hole}`} at my position
			{/if}
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
{/if}

{#if holes.length > 0}
	<div class="space-y-1.5 pt-2">
		{#each holes as h (h)}
			<div
				class="rounded-xl border bg-card px-3 py-2 transition
					{h === activeHole && mode !== 'layout' ? 'border-accent' : 'border-edge'}"
			>
				<div class="flex items-center gap-2">
					<button type="button" class="flex-1 text-left text-sm" onclick={() => focusHole(h)}>
						<span class="font-bold text-accent">#{h.holeNumber}</span>
						<span class="text-xs text-ink-dim">
							· {holeDistance(h) !== null ? `${holeDistance(h)} ft` : 'placing…'}
							{#if h.fairway.length > 0}
								· {h.fairway.length} wp
							{/if}
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
				{#if h.hazards.length > 0}
					<div class="mt-1.5 flex flex-wrap gap-1.5">
						{#each h.hazards as hz (hz)}
							<button
								type="button"
								class="rounded-full border border-edge px-2 py-0.5 text-[10px] font-bold uppercase transition active:scale-95"
								style="color:{HAZARD_COLORS[hz.hazard_type] ?? '#ef4444'}"
								onclick={() => removeHazard(h, hz)}
								title="Remove {hz.hazard_type} area"
							>
								{hz.hazard_type} ✕
							</button>
						{/each}
					</div>
				{/if}
			</div>
		{/each}
	</div>
{/if}
