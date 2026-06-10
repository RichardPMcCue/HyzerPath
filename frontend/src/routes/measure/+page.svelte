<script lang="ts">
	import { onMount } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import type { FeatureCollection } from 'geojson';
	import { api } from '$lib/api';
	import type { Disc, ThrowMeasurement, ThrowSession } from '$lib/types';

	let mapContainer: HTMLDivElement | undefined = $state();
	let map: maplibregl.Map | null = null;
	let markers: maplibregl.Marker[] = [];

	let session = $state<ThrowSession | null>(null);
	let throws = $state<ThrowMeasurement[]>([]);
	let pendingEnd = $state<{ latitude: number; longitude: number } | null>(null);
	let discs = $state<Disc[]>([]);
	let error = $state<string | null>(null);
	let busy = $state(false);
	let saving = $state(false);
	let gpsAccuracy = $state<number | null>(null);

	$effect(() => {
		api
			.getDiscs()
			.then((d) => (discs = d))
			.catch(() => {});
	});

	function getPosition(): Promise<GeolocationPosition> {
		return new Promise((resolve, reject) => {
			if (!navigator.geolocation) {
				reject(new Error('GPS not available on this device'));
				return;
			}
			navigator.geolocation.getCurrentPosition(resolve, (e) => reject(new Error(e.message)), {
				enableHighAccuracy: true,
				timeout: 15000,
				maximumAge: 0
			});
		});
	}

	onMount(() => {
		if (!mapContainer) return;
		// Render the map immediately — never block on the GPS permission prompt
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
						// Esri imagery runs out around z19 in many areas; without this
						// MapLibre requests missing tiles and renders blank instead of
						// upscaling the deepest available zoom.
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

		// Live "you are here" dot + recenter button
		const geolocate = new maplibregl.GeolocateControl({
			positionOptions: { enableHighAccuracy: true },
			trackUserLocation: true,
			showAccuracyCircle: true
		});
		map.addControl(geolocate, 'top-right');
		geolocate.on('geolocate', (pos) => {
			gpsAccuracy = pos.coords.accuracy * 3.28084;
		});

		map.on('load', () => {
			map!.resize(); // container may have settled after construction
			map!.addSource('lines', { type: 'geojson', data: linesGeoJSON() });
			map!.addLayer({
				id: 'throw-lines',
				type: 'line',
				source: 'lines',
				layout: { 'line-cap': 'round' },
				paint: { 'line-color': '#34d399', 'line-width': 3, 'line-dasharray': [0.5, 1.8] }
			});
			// Fly to the player and start tracking as soon as GPS resolves
			geolocate.trigger();
		});

		return () => map?.remove();
	});

	function linesGeoJSON(): FeatureCollection {
		if (!session) return { type: 'FeatureCollection', features: [] };
		const start = [session.start_longitude, session.start_latitude];
		const ends = [...throws.map((t) => [t.end_longitude, t.end_latitude])];
		if (pendingEnd) ends.push([pendingEnd.longitude, pendingEnd.latitude]);
		return {
			type: 'FeatureCollection',
			features: ends.map((end) => ({
				type: 'Feature',
				properties: {},
				geometry: { type: 'LineString', coordinates: [start, end] }
			}))
		};
	}

	function addMarker(lngLat: [number, number], color: string, size = 14) {
		const el = document.createElement('div');
		el.style.cssText = `width:${size}px;height:${size}px;border-radius:9999px;background:${color};border:2px solid #0c1210;box-shadow:0 0 0 4px ${color}44`;
		const marker = new maplibregl.Marker({ element: el }).setLngLat(lngLat).addTo(map!);
		markers.push(marker);
	}

	function redraw() {
		if (!map) return;
		markers.forEach((m) => m.remove());
		markers = [];
		const source = map.getSource('lines') as maplibregl.GeoJSONSource | undefined;
		if (source) source.setData(linesGeoJSON());
		if (!session) return;
		addMarker([session.start_longitude, session.start_latitude], '#34d399', 16);
		for (const t of throws) addMarker([t.end_longitude, t.end_latitude], '#f97316');
		if (pendingEnd) addMarker([pendingEnd.longitude, pendingEnd.latitude], '#38bdf8');

		const bounds = new maplibregl.LngLatBounds();
		bounds.extend([session.start_longitude, session.start_latitude]);
		for (const t of throws) bounds.extend([t.end_longitude, t.end_latitude]);
		if (pendingEnd) bounds.extend([pendingEnd.longitude, pendingEnd.latitude]);
		if (throws.length > 0 || pendingEnd) map.fitBounds(bounds, { padding: 60, maxZoom: 19 });
	}

	async function markStart() {
		busy = true;
		error = null;
		try {
			const pos = await getPosition();
			gpsAccuracy = pos.coords.accuracy * 3.28084;
			session = await api.createThrowSession({
				start_latitude: pos.coords.latitude,
				start_longitude: pos.coords.longitude
			});
			throws = [];
			pendingEnd = null;
			map?.flyTo({ center: [pos.coords.longitude, pos.coords.latitude], zoom: 18 });
			redraw();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	async function markEnd() {
		busy = true;
		error = null;
		try {
			const pos = await getPosition();
			gpsAccuracy = pos.coords.accuracy * 3.28084;
			pendingEnd = { latitude: pos.coords.latitude, longitude: pos.coords.longitude };
			redraw();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	// Disc chosen (or skipped) for the pending end point: save the throw
	async function saveThrow(discId: number | null) {
		if (!session || !pendingEnd) return;
		saving = true;
		try {
			const t = await api.recordThrow(session.session_id, {
				end_latitude: pendingEnd.latitude,
				end_longitude: pendingEnd.longitude,
				disc_id: discId
			});
			throws = [t, ...throws];
			pendingEnd = null;
			redraw();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			saving = false;
		}
	}

	async function removeThrow(throwId: number) {
		if (!session) return;
		await api.deleteThrow(session.session_id, throwId);
		throws = throws.filter((t) => t.throw_id !== throwId);
		redraw();
	}

	function reset() {
		session = null;
		throws = [];
		pendingEnd = null;
		redraw();
	}

	function discName(discId: number | null): string {
		const disc = discs.find((d) => d.disc_id === discId);
		return disc ? disc.name : 'No disc';
	}
</script>

<div class="flex h-dvh flex-col pb-20">
	<header class="px-4 pt-6 pb-3">
		<div class="flex items-end justify-between">
			<h1 class="text-2xl font-bold">Measure</h1>
			{#if gpsAccuracy}
				<span class="text-xs text-ink-dim">GPS ±{Math.round(gpsAccuracy)} ft</span>
			{/if}
		</div>
	</header>

	<!-- Big satellite map -->
	<div class="relative mx-4 flex-1 overflow-hidden rounded-2xl border border-edge">
		<div bind:this={mapContainer} class="absolute inset-0"></div>

		{#if error}
			<p class="absolute inset-x-3 top-3 rounded-xl bg-red-950/90 p-3 text-xs text-red-300">
				{error}
			</p>
		{/if}

		<!-- Disc picker sheet after marking an end -->
		{#if pendingEnd}
			<div class="absolute inset-x-0 bottom-0 rounded-t-2xl border-t border-edge bg-card/95 p-4 backdrop-blur">
				<p class="text-sm font-semibold">What did you throw?</p>
				<div class="mt-2 -mx-1 overflow-x-auto px-1">
					<div class="flex w-max gap-2">
						{#each discs as disc (disc.disc_id)}
							<button
								class="rounded-full border border-edge bg-card-raised px-3.5 py-2 text-xs font-semibold whitespace-nowrap transition active:scale-95 disabled:opacity-50"
								onclick={() => saveThrow(disc.disc_id)}
								disabled={saving}
							>
								{disc.name}
							</button>
						{/each}
					</div>
				</div>
				<div class="mt-3 flex gap-2">
					<button
						class="flex-1 rounded-xl border border-edge py-2.5 text-xs font-semibold text-ink-dim transition active:scale-95"
						onclick={() => saveThrow(null)}
						disabled={saving}
					>
						Skip — just the distance
					</button>
					<button
						class="rounded-xl border border-edge px-4 py-2.5 text-xs font-semibold text-red-400 transition active:scale-95"
						onclick={() => {
							pendingEnd = null;
							redraw();
						}}
					>
						Cancel
					</button>
				</div>
			</div>
		{/if}
	</div>

	<!-- Action bar -->
	<div class="space-y-2 px-4 pt-3">
		{#if !session}
			<button
				class="w-full rounded-2xl bg-accent py-4 text-base font-bold text-surface transition active:scale-[0.98] disabled:opacity-50"
				onclick={markStart}
				disabled={busy}
			>
				{busy ? 'Locating…' : '📍 Mark start — stand where you throw from'}
			</button>
		{:else if !pendingEnd}
			<div class="flex gap-2">
				<button
					class="flex-1 rounded-2xl bg-accent py-4 text-base font-bold text-surface transition active:scale-[0.98] disabled:opacity-50"
					onclick={markEnd}
					disabled={busy}
				>
					{busy ? 'Locating…' : throws.length === 0 ? '🥏 Mark landing' : '🥏 Mark another landing'}
				</button>
				<button
					class="rounded-2xl border border-edge bg-card px-4 text-xs font-semibold text-ink-dim transition active:scale-95"
					onclick={reset}
				>
					New start
				</button>
			</div>
		{/if}

		{#if throws.length > 0}
			<div class="max-h-32 space-y-1.5 overflow-y-auto">
				{#each throws as t (t.throw_id)}
					<div class="flex items-center justify-between rounded-xl border border-edge bg-card px-3 py-2">
						<p class="text-sm">
							<span class="font-bold text-accent">{Math.round(t.distance_ft)} ft</span>
							<span class="text-xs text-ink-dim"> · {discName(t.disc_id)}</span>
						</p>
						<button
							class="p-1 text-ink-dim transition hover:text-red-400"
							onclick={() => removeThrow(t.throw_id)}
							aria-label="Delete throw"
						>
							<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
								<path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
							</svg>
						</button>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>
