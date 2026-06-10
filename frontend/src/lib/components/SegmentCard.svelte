<script lang="ts">
	import type { SegmentRecommendation } from '$lib/types';

	let { rec, index }: { rec: SegmentRecommendation; index: number } = $props();

	const shapeStyle: Record<string, { label: string; classes: string; arrow: string }> = {
		straight: { label: 'Straight', classes: 'bg-sky-950 text-sky-300', arrow: 'M12 19V5m0 0-5 5m5-5 5 5' },
		hyzer: { label: 'Hyzer', classes: 'bg-emerald-950 text-emerald-300', arrow: 'M14 19c0-6-1-10-6-12m0 0h5M8 7v5' },
		spike_hyzer: { label: 'Spike Hyzer', classes: 'bg-emerald-950 text-emerald-200', arrow: 'M16 19C16 11 13 7 6 6m0 0h6M6 6v6' },
		anhyzer: { label: 'Anhyzer', classes: 'bg-amber-950 text-amber-300', arrow: 'M10 19c0-6 1-10 6-12m0 0h-5m5 0v5' },
		flex: { label: 'Flex', classes: 'bg-orange-950 text-orange-300', arrow: 'M8 19c4-2 4-10 8-12m0 0h-5m5 0v5' }
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
				<p class="font-semibold">{isPutt ? 'Just putt it 🎯' : rec.disc}</p>
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

	{#if rec.hazards.length > 0 || rec.skipped_node_ids.length > 0}
		<div class="mt-3 flex flex-wrap gap-1.5">
			{#each rec.hazards as hazard (hazard)}
				<span class="rounded-full bg-red-950/80 px-2.5 py-0.5 text-[11px] font-medium text-red-300">
					⚠ {hazard}
				</span>
			{/each}
			{#if rec.skipped_node_ids.length > 0}
				<span class="rounded-full bg-card-raised px-2.5 py-0.5 text-[11px] font-medium text-ink-dim">
					skips {rec.skipped_node_ids.length} node{rec.skipped_node_ids.length > 1 ? 's' : ''}
				</span>
			{/if}
		</div>
	{/if}
</div>
