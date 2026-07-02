<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import type { Course, Round, RoundStats } from '$lib/types';

	const roundId = $derived(Number(page.params.roundId));

	let round = $state<Round | null>(null);
	let course = $state<Course | null>(null);
	let stats = $state<RoundStats | null>(null);
	let error = $state<string | null>(null);

	$effect(() => {
		(async () => {
			try {
				const r = await api.getRound(roundId);
				round = r;
				course = await api.getCourse(r.course_id);
				try {
					stats = await api.getRoundStats(roundId);
				} catch {
					/* stats are best-effort — score-only rounds have none */
				}
			} catch (e) {
				error = (e as Error).message;
			}
		})();
	});

	const holes = $derived.by(() => {
		if (!course || !round) return [];
		const scoreByHole = new Map(round.round_holes.map((rh) => [rh.hole_id, rh.score]));
		let hs = [...course.holes].sort((a, b) => a.hole_number - b.hole_number);
		if (round.layout === 'front9') hs = hs.filter((h) => h.hole_number <= 9);
		if (round.layout === 'back9') hs = hs.filter((h) => h.hole_number >= 10);
		return hs.map((h) => ({
			number: h.hole_number,
			par: h.par,
			score: scoreByHole.get(h.hole_id)
		}));
	});

	const rel = $derived(
		holes.reduce((acc, h) => (h.score && h.score > 0 ? acc + h.score - h.par : acc), 0)
	);
	const relLabel = $derived(rel === 0 ? 'E' : rel > 0 ? `+${rel}` : `${rel}`);
	const throwsLabel = $derived(round?.total_score ?? null);

	const layoutLabel: Record<string, string> = {
		full: 'Full course',
		front9: 'Front 9',
		back9: 'Back 9'
	};

	function scoreColor(score: number | undefined, par: number): string {
		if (!score) return 'bg-card-raised text-ink-dim';
		const diff = score - par;
		if (diff <= -2) return 'bg-teal-500 text-surface';
		if (diff === -1) return 'bg-accent text-surface';
		if (diff === 0) return 'bg-card-raised text-ink';
		if (diff === 1) return 'bg-amber-500 text-surface';
		return 'bg-red-500 text-surface';
	}

	function pct(made: number, attempted: number): string | null {
		if (attempted === 0) return null;
		return `${Math.round((made / attempted) * 100)}%`;
	}

	const statCards = $derived.by(() => {
		if (!stats || stats.holes_with_throws === 0) return [];
		const cards: { value: string; label: string }[] = [];
		const c1 = pct(stats.c1_putts_made, stats.c1_putts_attempted);
		if (c1) cards.push({ value: c1, label: 'C1 putting' });
		const c2 = pct(stats.c2_putts_made, stats.c2_putts_attempted);
		if (c2) cards.push({ value: c2, label: 'C2 putting' });
		const fw = pct(stats.fairway_hits, stats.fairway_attempts);
		if (fw) cards.push({ value: fw, label: 'Fairway hits' });
		if (stats.parked > 0) cards.push({ value: String(stats.parked), label: 'Parked' });
		return cards;
	});
</script>

<header class="sticky top-0 z-30 bg-surface/95 px-4 pt-6 pb-3 backdrop-blur">
	<a href="/rounds" class="mb-2 flex items-center gap-1 text-sm text-accent">
		<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
			<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
		</svg>
		Rounds
	</a>
	<h1 class="text-2xl font-bold">Round complete</h1>
	{#if round && course}
		<p class="mt-0.5 text-xs text-ink-dim">
			{course.name} · {new Date(round.played_at).toLocaleDateString(undefined, {
				month: 'short',
				day: 'numeric',
				year: 'numeric'
			})} · {layoutLabel[round.layout] ?? round.layout}
		</p>
	{/if}
</header>

<main class="space-y-5 px-4 pt-2 pb-8">
	{#if error}
		<p class="rounded-xl bg-red-950/60 p-4 text-sm text-red-300">{error}</p>
	{:else if round === null || course === null}
		<div class="space-y-3 pt-2">
			<div class="h-32 animate-pulse rounded-2xl bg-card"></div>
			<div class="h-24 animate-pulse rounded-2xl bg-card"></div>
		</div>
	{:else}
		<!-- Big score -->
		<div class="rounded-2xl border border-edge bg-card p-6 text-center">
			<p class="text-5xl font-bold {rel > 0 ? 'text-amber-300' : 'text-accent'}">{relLabel}</p>
			{#if throwsLabel !== null}
				<p class="mt-2 text-sm text-ink-dim">{throwsLabel} throws</p>
			{/if}
		</div>

		<!-- Scorecard -->
		{#if holes.length > 0}
			<section>
				<h2 class="px-1 pb-2 text-xs font-semibold tracking-wide text-ink-dim uppercase">
					Scorecard
				</h2>
				<div class="flex flex-wrap gap-1.5">
					{#each holes as h (h.number)}
						<span
							class="flex h-9 w-9 items-center justify-center rounded-lg text-xs font-bold {scoreColor(
								h.score,
								h.par
							)}"
							title="Hole {h.number} · Par {h.par}"
						>
							{h.score && h.score > 0 ? h.score : '·'}
						</span>
					{/each}
				</div>
			</section>
		{/if}

		<!-- Stats -->
		{#if statCards.length > 0}
			<section>
				<h2 class="px-1 pb-2 text-xs font-semibold tracking-wide text-ink-dim uppercase">
					This round
				</h2>
				<div class="grid grid-cols-2 gap-3">
					{#each statCards as card (card.label)}
						<div class="rounded-2xl border border-edge bg-card p-4 text-center">
							<p class="text-2xl font-bold text-accent">{card.value}</p>
							<p class="mt-0.5 text-xs text-ink-dim">{card.label}</p>
						</div>
					{/each}
				</div>
			</section>
		{/if}

		<a
			href="/rounds"
			class="block w-full rounded-2xl bg-accent py-4 text-center text-base font-bold text-surface transition active:scale-[0.98]"
		>
			Done
		</a>
	{/if}
</main>
