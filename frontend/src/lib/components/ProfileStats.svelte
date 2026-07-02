<script lang="ts">
	import { api } from '$lib/api';
	import type { LifetimeStats } from '$lib/types';

	let stats = $state<LifetimeStats | null>(null);
	let error = $state<string | null>(null);

	$effect(() => {
		api
			.getLifetimeStats()
			.then((s) => (stats = s))
			.catch((e) => (error = e.message));
	});

	function pct(made: number, att: number): string {
		return att > 0 ? `${Math.round((made / att) * 100)}%` : '–';
	}

	const cards = $derived(
		stats
			? [
					{ label: 'C1 putting', value: pct(stats.c1_putts_made, stats.c1_putts_attempted), sub: `${stats.c1_putts_made}/${stats.c1_putts_attempted}` },
					{ label: 'C1X putting', value: pct(stats.c1x_putts_made, stats.c1x_putts_attempted), sub: `${stats.c1x_putts_made}/${stats.c1x_putts_attempted}` },
					{ label: 'C2 putting', value: pct(stats.c2_putts_made, stats.c2_putts_attempted), sub: `${stats.c2_putts_made}/${stats.c2_putts_attempted}` },
					{ label: 'Fairway hits', value: pct(stats.fairway_hits, stats.fairway_attempts), sub: `${stats.fairway_hits}/${stats.fairway_attempts}` },
					{ label: 'C1 in reg', value: pct(stats.gir_c1, stats.gir_attempts), sub: `${stats.gir_c1}/${stats.gir_attempts}` },
					{ label: 'C2 in reg', value: pct(stats.gir_c2, stats.gir_attempts), sub: `${stats.gir_c2}/${stats.gir_attempts}` },
					{ label: 'Parked', value: String(stats.parked), sub: 'throws' },
					{ label: 'Holes tracked', value: String(stats.holes_with_throws), sub: `${stats.rounds_played} round${stats.rounds_played === 1 ? '' : 's'}` }
				]
			: []
	);
</script>

{#if error}
	<p class="rounded-xl bg-red-950/60 p-4 text-sm text-red-300">{error}</p>
{:else if stats === null}
	<div class="grid grid-cols-2 gap-3">
		{#each Array(6) as _, i (i)}
			<div class="h-20 animate-pulse rounded-2xl bg-card"></div>
		{/each}
	</div>
{:else if stats.holes_with_throws === 0}
	<div class="pt-12 text-center">
		<p class="text-4xl">📊</p>
		<p class="mt-3 font-semibold">No stats yet</p>
		<p class="mt-1 text-sm text-ink-dim">
			Play a round with lie or detailed tracking and your putting, fairway, and
			green-in-regulation stats will show up here.
		</p>
	</div>
{:else}
	<div class="grid grid-cols-2 gap-3">
		{#each cards as card (card.label)}
			<div class="rounded-2xl border border-edge bg-card p-4">
				<p class="text-2xl font-bold text-accent">{card.value}</p>
				<p class="mt-0.5 text-sm font-semibold">{card.label}</p>
				<p class="text-xs text-ink-dim">{card.sub}</p>
			</div>
		{/each}
	</div>
	<p class="mt-3 px-1 text-xs text-ink-dim">
		C1 = inside 33 ft, C2 = inside 66 ft. C1X excludes tap-ins inside 11 ft. "In
		reg" = reached the circle within par − 2 throws.
	</p>
{/if}
