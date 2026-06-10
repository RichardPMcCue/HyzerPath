<script lang="ts">
	import { onMount } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import type { Feature, FeatureCollection } from 'geojson';
	import { satelliteStyle } from '$lib/map';
	import type { HoleNode, SegmentRecommendation } from '$lib/types';

	let {
		nodes,
		recommendations,
		fairwayPolygon = []
	}: {
		nodes: HoleNode[];
		recommendations: SegmentRecommendation[];
		fairwayPolygon?: [number, number][];
	} = $props();

	let container = $state<HTMLDivElement>()!;
	let map: maplibregl.Map | null = null;
	let loaded = $state(false);

	const gpsNodes = $derived(nodes.filter((n) => n.latitude !== null && n.longitude !== null));

	function nodeColor(type: string): string {
		switch (type) {
			case 'tee':
				return '#34d399';
			case 'basket':
				return '#f97316';
			case 'mando':
				return '#eab308';
			default:
				return '#e8f0ec';
		}
	}

	function throwLineGeoJSON(): FeatureCollection {
		const nodeById = new Map(nodes.map((n) => [n.hole_node_id, n]));
		const features: Feature[] = [];
		for (const rec of recommendations) {
			const from = nodeById.get(rec.from_node_id);
			const to = nodeById.get(rec.to_node_id);
			if (!from?.latitude || !to?.latitude) continue;
			features.push({
				type: 'Feature',
				properties: {},
				geometry: {
					type: 'LineString',
					coordinates: [
						[from.longitude!, from.latitude!],
						[to.longitude!, to.latitude!]
					]
				}
			});
		}
		return { type: 'FeatureCollection', features };
	}

	function fairwayGeoJSON(): FeatureCollection {
		if (fairwayPolygon.length < 4) return { type: 'FeatureCollection', features: [] };
		return {
			type: 'FeatureCollection',
			features: [
				{
					type: 'Feature',
					properties: {},
					geometry: {
						type: 'Polygon',
						// API sends [lat, lon]; GeoJSON wants [lon, lat]
						coordinates: [fairwayPolygon.map(([lat, lon]) => [lon, lat])]
					}
				}
			]
		};
	}

	function render() {
		if (!map || !loaded) return;

		const fairwaySource = map.getSource('fairway') as maplibregl.GeoJSONSource | undefined;
		if (fairwaySource) fairwaySource.setData(fairwayGeoJSON());

		const source = map.getSource('throws') as maplibregl.GeoJSONSource | undefined;
		if (source) source.setData(throwLineGeoJSON());

		document.querySelectorAll('.hole-marker').forEach((el) => el.remove());
		const skipped = new Set(recommendations.flatMap((r) => r.skipped_node_ids));
		for (const node of gpsNodes) {
			const el = document.createElement('div');
			el.className = 'hole-marker';
			const dim = skipped.has(node.hole_node_id);
			const isLie = node.hole_node_id === 0; // virtual node at the player's position
			const big = isLie || node.node_type === 'tee' || node.node_type === 'basket';
			el.style.cssText = `width:${big ? 16 : 11}px;
				height:${big ? 16 : 11}px;
				border-radius:9999px;background:${isLie ? '#38bdf8' : nodeColor(node.node_type)};
				border:2px solid #0c1210;opacity:${dim ? 0.45 : 1};
				${isLie ? 'box-shadow:0 0 0 5px rgba(56,189,248,0.3);' : ''}`;
			new maplibregl.Marker({ element: el })
				.setLngLat([node.longitude!, node.latitude!])
				.addTo(map);
		}
	}

	onMount(() => {
		if (gpsNodes.length < 2) return;

		const bounds = new maplibregl.LngLatBounds();
		for (const n of gpsNodes) bounds.extend([n.longitude!, n.latitude!]);

		map = new maplibregl.Map({
			container,
			style: satelliteStyle(),
			bounds,
			fitBoundsOptions: { padding: 48 },
			attributionControl: false
		});

		map.on('load', () => {
			// Fairway corridor under everything else: shows *why* the line goes
			// where it does (doglegs, no-fly zones are simply outside it)
			map!.addSource('fairway', { type: 'geojson', data: fairwayGeoJSON() });
			map!.addLayer({
				id: 'fairway-fill',
				type: 'fill',
				source: 'fairway',
				paint: { 'fill-color': '#34d399', 'fill-opacity': 0.14 }
			});
			map!.addLayer({
				id: 'fairway-outline',
				type: 'line',
				source: 'fairway',
				paint: { 'line-color': '#34d399', 'line-opacity': 0.45, 'line-width': 1.5 }
			});

			map!.addSource('throws', { type: 'geojson', data: throwLineGeoJSON() });
			map!.addLayer({
				id: 'throw-lines',
				type: 'line',
				source: 'throws',
				layout: { 'line-cap': 'round' },
				paint: {
					'line-color': '#34d399',
					'line-width': 3,
					'line-dasharray': [0.5, 1.8]
				}
			});
			loaded = true;
			render();
		});

		return () => map?.remove();
	});

	$effect(() => {
		recommendations;
		fairwayPolygon;
		render();
	});
</script>

{#if gpsNodes.length >= 2}
	<div bind:this={container} class="h-72 w-full rounded-2xl border border-edge"></div>
{:else}
	<div
		class="flex h-40 items-center justify-center rounded-2xl border border-edge bg-card text-sm text-ink-dim"
	>
		No GPS data for this hole yet
	</div>
{/if}
