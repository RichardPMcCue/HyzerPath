<script lang="ts">
	import type { SegmentRecommendation } from '$lib/types';
	import FlightNumbers from './FlightNumbers.svelte';

	let { rec, index }: { rec: SegmentRecommendation; index: number } = $props();

	const shapeStyle: Record<string, { label: string; classes: string; arrow: string }> = {
		straight: { label: 'Straight', classes: 'bg-sky-950 text-sky-300', arrow: 'M12 19V5m0 0-5 5m5-5 5 5' },
		hyzer: { label: 'Hyzer', classes: 'bg-emerald-950 text-emerald-300', arrow: 'M14 19c0-6-1-10-6-12m0 0h5M8 7v5' },
		spike_hyzer: { label: 'Spike Hyzer', classes: 'bg-emerald-950 text-emerald-200', arrow: 'M16 19C16 11 13 7 6 6m0 0h6M6 6v6' },
		anhyzer: { label: 'Anhyzer', classes: 'bg-amber-950 text-amber-300', arrow: 'M10 19c0-6 1-10 6-12m0 0h-5m5 0v5' },
		flex: { label: 'Flex', classes: 'bg-orange-950 text-orange-300', arrow: 'M8 19c4-2 4-10 8-12m0 0h-5m5 0v5' },
		hyzer_flip: { label: 'Hyzer Flip', classes: 'bg-teal-950 text-teal-300', arrow: 'M12 19c-2-5-2-9 0-12m0 0-3 4m3-4 3 4' },
		turnover: { label: 'Turnover', classes: 'bg-yellow-950 text-yellow-300', arrow: 'M9 19c1-6 4-10 9-11m0 0-4-1m4 1-1 4' }
	};

	const shape = $derived(shapeStyle[rec.shot_shape] ?? shapeStyle.straight);
	const playsDifferent = $derived(Math.abs(rec.effective_distance - rec.distance) >= 5);

	const throwTypeLabel: Record<string, string> = {
		drive: 'Drive',
		placement: 'Placement',
		approach: 'Approach',
		putt: 'Putt'
	};
	const isPutt = $derived(rec.throw_type === 'putt');
	// Inside C1 it's a putt; C1–C2 (33–66 ft) is a jump putt
	const isJumpPutt = $derived(isPutt && rec.distance > 35);

	// Intended landing zone for the approach (where the throw should leave you)
	const zoneLabel: Record<string, string> = {
		c1: 'C1 look',
		c2: 'C2 look',
		c3: 'C3 look',
		basket: 'Parked'
	};
	const showZone = $derived(!isPutt && rec.landing_zone in zoneLabel);
	const hasWear = $derived(rec.wear != null && rec.wear > 0);
</script>

<div class="rounded-2xl border border-edge bg-card p-4">
	<div class="flex items-center justify-between">
		<div class="flex items-center gap-3">
			<span
				class="flex h-8 w-8 items-center justify-center rounded-full bg-accent/15 text-sm font-bold text-accent"
			>
				{index + 1}
			</span>
			<div>
				<p class="font-semibold">
					{isPutt ? (isJumpPutt ? 'Jump putt 🎯' : 'Just putt it 🎯') : rec.disc}
				</p>
				<p class="text-xs text-ink-dim">
					<span class="font-medium text-ink">{throwTypeLabel[rec.throw_type] ?? 'Drive'}</span>
					· {rec.distance} ft
					{#if playsDifferent}
						<span class="text-amber-300"> · plays {rec.effective_distance} ft</span>
					{/if}
				</p>
			</div>
		</div>
		{#if !isPutt}
			<div class="flex shrink-0 items-center gap-1.5">
				{#if rec.throw_style === 'forehand'}
					<span class="rounded-full bg-violet-950 px-2 py-1 text-xs font-bold text-violet-300">
						FH
					</span>
				{:else}
					<span class="rounded-full bg-sky-950 px-2 py-1 text-xs font-bold text-sky-300">
						BH
					</span>
				{/if}
				<span
					class="flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold {shape.classes}"
				>
					<svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" d={shape.arrow} />
					</svg>
					{shape.label}
				</span>
			</div>
		{/if}
	</div>

	{#if !isPutt}
		<!-- Flight numbers of the recommended disc, so two copies of one mold at
		     different wear can be told apart -->
		<div class="mt-3 flex items-center gap-2">
			<FlightNumbers speed={rec.speed} glide={rec.glide} turn={rec.turn} fade={rec.fade} />
			{#if hasWear}
				<span class="rounded-md bg-card-raised px-1.5 py-0.5 text-xs font-medium text-ink-dim" title="Wear">
					wear {rec.wear}
				</span>
			{/if}
		</div>
		{#if rec.rationale}
			<p class="mt-2 text-xs leading-snug text-ink-dim">{rec.rationale}</p>
		{/if}
	{/if}

	{#if showZone || rec.hazards.length > 0 || rec.skipped_node_ids.length > 0}
		<div class="mt-3 flex flex-wrap gap-1.5">
			{#if showZone}
				<span class="rounded-full bg-accent/15 px-2.5 py-0.5 text-xs font-semibold text-accent">
					🎯 {zoneLabel[rec.landing_zone]}
				</span>
			{/if}
			{#each rec.hazards as hazard (hazard)}
				<span class="rounded-full bg-red-950/80 px-2.5 py-0.5 text-xs font-medium text-red-300">
					⚠ {hazard}
				</span>
			{/each}
			{#if rec.skipped_node_ids.length > 0}
				<span class="rounded-full bg-card-raised px-2.5 py-0.5 text-xs font-medium text-ink-dim">
					carries past {rec.skipped_node_ids.length} waypoint{rec.skipped_node_ids.length > 1 ? 's' : ''}
				</span>
			{/if}
		</div>
	{/if}
</div>
