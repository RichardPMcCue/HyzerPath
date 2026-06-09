<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import type { CaddieMode, Course, Hole, HolePath } from '$lib/types';
	import HoleMap from '$lib/components/HoleMap.svelte';
	import SegmentCard from '$lib/components/SegmentCard.svelte';

	const courseId = $derived(Number(page.params.courseId));
	const holeId = $derived(Number(page.params.holeId));

	let course = $state<Course | null>(null);
	let path = $state<HolePath | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(false);
	let mode = $state<CaddieMode>('balanced');
	let useWind = $state(false);

	const hole = $derived<Hole | undefined>(course?.holes.find((h) => h.hole_id === holeId));

	$effect(() => {
		api
			.getCourse(courseId)
			.then((c) => (course = c))
			.catch((e) => (error = e.message));
	});

	$effect(() => {
		loading = true;
		error = null;
		api
			.getHolePath(courseId, holeId, { mode, useWind })
			.then((p) => (path = p))
			.catch((e) => (error = e.message))
			.finally(() => (loading = false));
	});

	const modes: { value: CaddieMode; label: string }[] = [
		{ value: 'conservative', label: 'Safe' },
		{ value: 'balanced', label: 'Balanced' },
		{ value: 'aggressive', label: 'Send it' }
	];
</script>

<header class="sticky top-0 z-30 bg-surface/95 px-4 pt-6 pb-3 backdrop-blur">
	<a href="/courses/{courseId}" class="mb-2 flex items-center gap-1 text-sm text-accent">
		<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
			<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
		</svg>
		{course?.name ?? 'Course'}
	</a>
	<div class="flex items-end justify-between">
		<h1 class="text-2xl font-bold">Hole {hole?.hole_number ?? '…'}</h1>
		{#if hole}
			<p class="text-sm text-ink-dim">Par {hole.par} · {hole.distance} ft</p>
		{/if}
	</div>
</header>

<main class="space-y-4 px-4 pt-2">
	{#if path}
		<HoleMap
			nodes={path.nodes}
			recommendations={path.recommendations}
			fairwayPolygon={path.fairway_polygon}
		/>
	{/if}

	<!-- Mode + wind controls -->
	<div class="flex items-center gap-2">
		<div class="flex flex-1 rounded-xl border border-edge bg-card p-1">
			{#each modes as m (m.value)}
				<button
					class="flex-1 rounded-lg py-1.5 text-xs font-semibold transition
						{mode === m.value ? 'bg-accent text-surface' : 'text-ink-dim'}"
					onclick={() => (mode = m.value)}
				>
					{m.label}
				</button>
			{/each}
		</div>
		<button
			class="flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-semibold transition
				{useWind ? 'border-accent bg-accent/15 text-accent' : 'border-edge bg-card text-ink-dim'}"
			onclick={() => (useWind = !useWind)}
		>
			<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					d="M3.75 9h12.629c1.012 0 1.871-.825 1.871-1.875a1.875 1.875 0 0 0-3.4-1.087M3.75 15h15.629c1.012 0 1.871.825 1.871 1.875a1.875 1.875 0 0 1-3.4 1.087M3.75 12h17.117"
				/>
			</svg>
			Wind
		</button>
	</div>

	{#if error}
		<p class="rounded-xl bg-red-950/60 p-4 text-sm text-red-300">{error}</p>
	{:else if loading && !path}
		<div class="space-y-3">
			{#each Array(3) as _, i (i)}
				<div class="h-20 animate-pulse rounded-2xl bg-card"></div>
			{/each}
		</div>
	{:else if path}
		<div class="flex items-center justify-between px-1">
			<h2 class="text-sm font-semibold tracking-wide text-ink-dim uppercase">
				Game plan · {path.recommendations.length} throw{path.recommendations.length === 1 ? '' : 's'}
			</h2>
			{#if loading}
				<span class="text-xs text-ink-dim">updating…</span>
			{/if}
		</div>
		<div class="space-y-3 {loading ? 'opacity-60' : ''}">
			{#each path.recommendations as rec, i (rec.from_node_id + '-' + rec.to_node_id)}
				<SegmentCard {rec} index={i} />
			{/each}
			{#if path.recommendations.length === 0}
				<p class="rounded-xl bg-card p-4 text-sm text-ink-dim">
					No recommendations — add discs and throw stats to your bag first.
				</p>
			{/if}
		</div>
	{/if}
</main>
