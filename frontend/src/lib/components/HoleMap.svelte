<script lang="ts">
	import { onMount } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import type { Feature, FeatureCollection } from 'geojson';
	import { autoResize, satelliteStyle } from '$lib/map';
	import type { Hazard, HoleNode, SegmentRecommendation } from '$lib/types';

	let {
		nodes,
		recommendations,
		fairwayPolygon = [],
		hazards = []
	}: {
		nodes: HoleNode[];
		recommendations: SegmentRecommendation[];
		fairwayPolygon?: [number, number][];
		hazards?: Hazard[];
	} = $props();

	const HAZARD_COLORS: Record<string, string> = {
		ob: '#ef4444',
		water: '#38bdf8',
		trees: '#a3e635'
	};

	let container = $state<HTMLDivElement>()!;
	let map: maplibregl.Map | null = null;
	let loaded = $state(false);
	let fittedNodesKey = '';

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
		const features: Feature[] = [];
		for (const rec of recommendations) {
			if (rec.start_latitude == null || rec.target_latitude == null) continue;
			features.push({
				type: 'Feature',
				properties: {},
				geometry: {
					type: 'LineString',
					coordinates: [
						[rec.start_longitude!, rec.start_latitude],
						[rec.target_longitude!, rec.target_latitude]
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

	function hazardsGeoJSON(): FeatureCollection {
		const features: Feature[] = [];
		for (const hz of hazards) {
			if (hz.polygon.length < 3) continue;
			// API sends [lat, lon]; GeoJSON wants [lon, lat]
			const ring = hz.polygon.map(([lat, lon]) => [lon, lat]);
			ring.push(ring[0]);
			features.push({
				type: 'Feature',
				properties: { color: HAZARD_COLORS[hz.hazard_type] ?? '#ef4444' },
				geometry: { type: 'Polygon', coordinates: [ring] }
			});
		}
		return { type: 'FeatureCollection', features };
	}

	function render() {
		if (!map || !loaded) return;

		// New hole (or new lie) → re-frame the camera to fit it. Scorecards keep
		// this component mounted across holes, so mount-time bounds go stale.
		const nodesKey = gpsNodes.map((n) => n.hole_node_id).join(',');
		if (nodesKey !== fittedNodesKey && gpsNodes.length >= 2) {
			fittedNodesKey = nodesKey;
			const bounds = new maplibregl.LngLatBounds();
			for (const n of gpsNodes) bounds.extend([n.longitude!, n.latitude!]);
			map.fitBounds(bounds, { padding: 48, maxZoom: 19 });
		}

		const fairwaySource = map.getSource('fairway') as maplibregl.GeoJSONSource | undefined;
		if (fairwaySource) fairwaySource.setData(fairwayGeoJSON());

		const hazardSource = map.getSource('hazards') as maplibregl.GeoJSONSource | undefined;
		if (hazardSource) hazardSource.setData(hazardsGeoJSON());

		const source = map.getSource('throws') as maplibregl.GeoJSONSource | undefined;
		if (source) source.setData(throwLineGeoJSON());

		document.querySelectorAll('.hole-marker').forEach((el) => el.remove());
		for (const node of gpsNodes) {
			const el = document.createElement('div');
			el.className = 'hole-marker';
			el.style.cssText = `width:16px;height:16px;
				border-radius:9999px;background:${nodeColor(node.node_type)};
				border:2px solid #0c1210;`;
			new maplibregl.Marker({ element: el })
				.setLngLat([node.longitude!, node.latitude!])
				.addTo(map);
		}
		// Landing targets: where each recommended throw should come down
		for (const rec of recommendations) {
			if (rec.target_latitude == null || rec.landing_zone === 'basket') continue;
			const el = document.createElement('div');
			el.className = 'hole-marker';
			el.style.cssText = `width:14px;height:14px;border-radius:9999px;
				background:transparent;border:3px solid #34d399;
				box-shadow:0 0 0 3px rgba(52,211,153,0.25);`;
			new maplibregl.Marker({ element: el })
				.setLngLat([rec.target_longitude!, rec.target_latitude])
				.addTo(map);
		}
		// The player's lie is the first throw's start when planning mid-hole
		const first = recommendations[0];
		if (first?.start_latitude != null && first.is_recovery !== undefined) {
			const isTee = gpsNodes.some(
				(n) =>
					n.node_type === 'tee' &&
					Math.abs((n.latitude ?? 0) - first.start_latitude!) < 1e-7 &&
					Math.abs((n.longitude ?? 0) - first.start_longitude!) < 1e-7
			);
			if (!isTee) {
				const el = document.createElement('div');
				el.className = 'hole-marker';
				el.style.cssText = `width:16px;height:16px;border-radius:9999px;
					background:#38bdf8;border:2px solid #0c1210;
					box-shadow:0 0 0 5px rgba(56,189,248,0.3);`;
				new maplibregl.Marker({ element: el })
					.setLngLat([first.start_longitude!, first.start_latitude])
					.addTo(map);
			}
		}
	}

	onMount(() => {
		if (gpsNodes.length < 2) return;

		fittedNodesKey = gpsNodes.map((n) => n.hole_node_id).join(',');
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

			// Hazard/OB areas above the fairway, below the throw lines
			map!.addSource('hazards', { type: 'geojson', data: hazardsGeoJSON() });
			map!.addLayer({
				id: 'hazard-fill',
				type: 'fill',
				source: 'hazards',
				paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.22 }
			});
			map!.addLayer({
				id: 'hazard-outline',
				type: 'line',
				source: 'hazards',
				paint: { 'line-color': ['get', 'color'], 'line-width': 1.5, 'line-opacity': 0.8 }
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

		const stopResize = autoResize(map, container);
		return () => {
			stopResize();
			map?.remove();
		};
	});

	$effect(() => {
		recommendations;
		fairwayPolygon;
		hazards;
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
