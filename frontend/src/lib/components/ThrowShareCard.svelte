<script lang="ts">
	import { onMount } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import { autoResize, satelliteStyle } from '$lib/map';

	let {
		start,
		end,
		distanceFt,
		discName,
		color,
		throwStyle,
		createdAt,
		onclose
	}: {
		start: { lat: number; lng: number };
		end: { lat: number; lng: number };
		distanceFt: number;
		discName: string;
		color: string;
		throwStyle: string | null;
		createdAt: string;
		onclose: () => void;
	} = $props();

	let mapContainer = $state<HTMLDivElement>();
	let map: maplibregl.Map | null = null;
	let mapReady = $state(false);
	let exporting = $state(false);
	let exportError = $state<string | null>(null);

	const styleSuffix = $derived(
		throwStyle === 'forehand' ? ' · FH' : throwStyle === 'backhand' ? ' · BH' : ''
	);
	const dateLabel = $derived(
		new Date(createdAt).toLocaleDateString(undefined, {
			month: 'short',
			day: 'numeric',
			year: 'numeric'
		})
	);
	const distance = $derived(Math.round(distanceFt));

	const LINE = '#34d399';
	const START_C = '#34d399';
	const END_C = '#f97316';

	onMount(() => {
		if (!mapContainer) return;
		map = new maplibregl.Map({
			container: mapContainer,
			style: satelliteStyle(),
			attributionControl: false,
			// required to capture the canvas to an image (moved here in maplibre 5)
			canvasContextAttributes: { preserveDrawingBuffer: true },
			interactive: false
		});

		map.on('load', () => {
			map!.resize();
			map!.addSource('throw', {
				type: 'geojson',
				data: {
					type: 'FeatureCollection',
					features: [
						{
							type: 'Feature',
							properties: {},
							geometry: {
								type: 'LineString',
								coordinates: [
									[start.lng, start.lat],
									[end.lng, end.lat]
								]
							}
						}
					]
				}
			});
			map!.addLayer({
				id: 'throw-line',
				type: 'line',
				source: 'throw',
				layout: { 'line-cap': 'round' },
				paint: { 'line-color': LINE, 'line-width': 4 }
			});
			// Start + end as GL circle layers so they're captured in the image
			// (DOM markers are NOT part of the WebGL canvas).
			map!.addSource('pts', {
				type: 'geojson',
				data: {
					type: 'FeatureCollection',
					features: [
						{ type: 'Feature', properties: { c: START_C }, geometry: { type: 'Point', coordinates: [start.lng, start.lat] } },
						{ type: 'Feature', properties: { c: END_C }, geometry: { type: 'Point', coordinates: [end.lng, end.lat] } }
					]
				}
			});
			map!.addLayer({
				id: 'throw-pts',
				type: 'circle',
				source: 'pts',
				paint: {
					'circle-radius': 7,
					'circle-color': ['get', 'c'],
					'circle-stroke-width': 2,
					'circle-stroke-color': '#0c1210'
				}
			});

			const bounds = new maplibregl.LngLatBounds();
			bounds.extend([start.lng, start.lat]);
			bounds.extend([end.lng, end.lat]);
			map!.fitBounds(bounds, { padding: 56, maxZoom: 19, animate: false });
			mapReady = true;
		});

		const stopResize = autoResize(map, mapContainer);
		return () => {
			stopResize();
			map?.remove();
			map = null;
		};
	});

	function onceIdle(m: maplibregl.Map): Promise<void> {
		return new Promise((resolve) => {
			m.once('idle', () => resolve());
			m.triggerRepaint();
		});
	}

	function drawOverlay(ctx: CanvasRenderingContext2D, w: number, h: number) {
		const s = w / 400; // scale relative to a 400px-wide reference card
		const pad = 16 * s;

		// bottom scrim for legibility
		const grad = ctx.createLinearGradient(0, h * 0.5, 0, h);
		grad.addColorStop(0, 'rgba(8,18,16,0)');
		grad.addColorStop(1, 'rgba(8,18,16,0.88)');
		ctx.fillStyle = grad;
		ctx.fillRect(0, h * 0.5, w, h * 0.5);

		ctx.textAlign = 'left';
		// distance
		ctx.fillStyle = '#ffffff';
		ctx.font = `700 ${46 * s}px ui-sans-serif, system-ui, -apple-system, sans-serif`;
		ctx.fillText(`${distance} ft`, pad, h - 40 * s);

		// disc swatch + name + date
		const subY = h - 16 * s;
		const dot = 9 * s;
		ctx.fillStyle = color;
		ctx.beginPath();
		ctx.arc(pad + dot / 2, subY - dot / 2 - 1 * s, dot / 2, 0, Math.PI * 2);
		ctx.fill();
		ctx.fillStyle = 'rgba(232,240,236,0.92)';
		ctx.font = `600 ${17 * s}px ui-sans-serif, system-ui, -apple-system, sans-serif`;
		ctx.fillText(`${discName}${styleSuffix} · ${dateLabel}`, pad + dot + 7 * s, subY);

		// brand, top-right
		ctx.textAlign = 'right';
		ctx.fillStyle = 'rgba(255,255,255,0.9)';
		ctx.font = `700 ${14 * s}px ui-sans-serif, system-ui, -apple-system, sans-serif`;
		ctx.fillText('HyzerPath', w - pad, 26 * s);
		ctx.textAlign = 'left';
	}

	async function save() {
		if (!map) return;
		exporting = true;
		exportError = null;
		try {
			await onceIdle(map);
			const gl = map.getCanvas();
			const out = document.createElement('canvas');
			out.width = gl.width;
			out.height = gl.height;
			const ctx = out.getContext('2d');
			if (!ctx) throw new Error('Canvas not supported');
			ctx.drawImage(gl, 0, 0);
			drawOverlay(ctx, out.width, out.height);

			const blob = await new Promise<Blob | null>((res) => out.toBlob(res, 'image/png'));
			if (!blob) throw new Error('Could not render image');
			const file = new File([blob], `hyzerpath-${distance}ft.png`, { type: 'image/png' });

			if (navigator.canShare?.({ files: [file] })) {
				await navigator.share({ files: [file], title: `${distance} ft throw` });
			} else {
				const url = URL.createObjectURL(blob);
				const a = document.createElement('a');
				a.href = url;
				a.download = file.name;
				a.click();
				URL.revokeObjectURL(url);
			}
		} catch (e) {
			// User cancelling the share sheet throws AbortError — not an error
			if ((e as Error).name !== 'AbortError') exportError = (e as Error).message;
		} finally {
			exporting = false;
		}
	}
</script>

<div class="fixed inset-0 z-50 flex flex-col bg-black/85 p-4 backdrop-blur">
	<div class="flex justify-end">
		<button
			class="rounded-full bg-card p-2 text-ink-dim transition active:scale-95"
			onclick={onclose}
			aria-label="Close"
		>
			<svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
				<path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
			</svg>
		</button>
	</div>

	<div
		class="relative mx-auto w-full max-w-sm overflow-hidden rounded-2xl border border-edge bg-card"
		style="aspect-ratio:4/5"
	>
		<div bind:this={mapContainer} class="h-full w-full"></div>

		<!-- live preview overlay (mirrors the exported image) -->
		<div class="pointer-events-none absolute inset-0">
			<span class="absolute top-2 right-3 text-sm font-bold text-white/90 drop-shadow">HyzerPath</span>
			<div
				class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 to-transparent px-4 pt-12 pb-3"
			>
				<p class="text-3xl font-bold text-white">{distance} ft</p>
				<p class="mt-0.5 flex items-center gap-1.5 text-sm text-white/90">
					<span class="h-2.5 w-2.5 rounded-full" style="background:{color}"></span>
					{discName}{styleSuffix} · {dateLabel}
				</p>
			</div>
		</div>

		{#if !mapReady}
			<div class="absolute inset-0 flex items-center justify-center bg-card">
				<div class="h-8 w-8 animate-pulse rounded-full bg-card-raised"></div>
			</div>
		{/if}
	</div>

	<div class="mx-auto mt-4 w-full max-w-sm">
		{#if exportError}
			<p class="mb-2 rounded-xl bg-red-950/60 p-3 text-xs text-red-300">{exportError}</p>
		{/if}
		<button
			class="w-full rounded-2xl bg-accent py-3.5 text-base font-bold text-surface transition active:scale-[0.98] disabled:opacity-50"
			onclick={save}
			disabled={exporting || !mapReady}
		>
			{exporting ? 'Preparing…' : 'Save image'}
		</button>
	</div>
</div>
