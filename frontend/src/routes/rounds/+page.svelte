<script lang="ts">
	import { api } from '$lib/api';
	import type { Course, Round, RoundStats } from '$lib/types';

	let rounds = $state<Round[]>([]);
	let courses = $state<Map<number, Course>>(new Map());
	let stats = $state<Map<number, RoundStats>>(new Map());
	let loaded = $state(false);
	let menuFor = $state<number | null>(null); // round_id whose ⋯ menu is open

	$effect(() => {
		Promise.all([api.listRounds(), api.getCourses()])
			.then(async ([r, c]) => {
				rounds = r;
				courses = new Map(c.map((course) => [course.course_id, course]));
				loaded = true;
				// Per-round stats (best-effort, finished rounds only)
				const entries = await Promise.all(
					r
						.filter((round) => round.total_score !== null)
						.map(async (round) => {
							try {
								return [round.round_id, await api.getRoundStats(round.round_id)] as const;
							} catch {
								return null;
							}
						})
				);
				stats = new Map(entries.filter((e) => e !== null));
			})
			.catch(() => (loaded = true));
	});

	function holesFor(round: Round) {
		const course = courses.get(round.course_id);
		if (!course) return [];
		const scoreByHole = new Map(round.round_holes.map((rh) => [rh.hole_id, rh.score]));
		return [...course.holes]
			.sort((a, b) => a.hole_number - b.hole_number)
			.map((h) => ({ number: h.hole_number, par: h.par, score: scoreByHole.get(h.hole_id) }));
	}

	function relative(round: Round): number {
		return holesFor(round).reduce(
			(rel, h) => (h.score && h.score > 0 ? rel + h.score - h.par : rel),
			0
		);
	}

	const relLabel = (rel: number) => (rel === 0 ? 'E' : rel > 0 ? `+${rel}` : `${rel}`);

	function scoreColor(score: number | undefined, par: number): string {
		if (!score) return 'bg-card-raised text-ink-dim';
		const diff = score - par;
		if (diff <= -2) return 'bg-teal-500 text-surface';
		if (diff === -1) return 'bg-accent text-surface';
		if (diff === 0) return 'bg-card-raised text-ink';
		if (diff === 1) return 'bg-amber-500 text-surface';
		return 'bg-red-500 text-surface';
	}

	async function removeRound(roundId: number) {
		if (!confirm('Delete this round? This cannot be undone.')) return;
		try {
			await api.deleteRound(roundId);
			rounds = rounds.filter((r) => r.round_id !== roundId);
		} catch {
			/* keep the card on failure */
		}
	}

	function pct(made: number, attempted: number): string | null {
		if (attempted === 0) return null;
		return `${Math.round((made / attempted) * 100)}%`;
	}
</script>

<header class="px-4 pt-6 pb-3">
	<h1 class="text-2xl font-bold">Rounds</h1>
</header>

<main class="space-y-3 px-4 pt-2">
	{#if !loaded}
		{#each Array(3) as _, i (i)}
			<div class="h-28 animate-pulse rounded-2xl bg-card"></div>
		{/each}
	{:else if rounds.length === 0}
		<div class="pt-16 text-center">
			<p class="text-4xl">⛳</p>
			<p class="mt-3 font-semibold">No rounds yet</p>
			<p class="mt-1 text-sm text-ink-dim">Open a course and hit ▶ Play.</p>
		</div>
	{:else}
		{#each rounds as round (round.round_id)}
			{@const course = courses.get(round.course_id)}
			{@const holes = holesFor(round)}
			{@const rel = relative(round)}
			{@const rs = stats.get(round.round_id)}
			<div class="relative rounded-2xl border border-edge bg-card p-4">
				{#if round.total_score !== null}
					<!-- Stretched link: the whole finished card opens the summary -->
					<a
						href="/rounds/{round.round_id}/summary"
						class="absolute inset-0 rounded-2xl"
						aria-label="View round summary"
					></a>
				{/if}
				<div class="flex items-start justify-between">
					<div>
						<p class="font-semibold">{course?.name ?? `Course ${round.course_id}`}</p>
						<p class="mt-0.5 text-xs text-ink-dim">
							{new Date(round.played_at).toLocaleDateString(undefined, {
								month: 'short',
								day: 'numeric',
								year: 'numeric'
							})}
						</p>
					</div>
					<div class="relative z-10 flex items-center gap-1">
						{#if round.total_score !== null}
							<div class="text-right">
								<p class="text-xl font-bold {rel > 0 ? 'text-amber-300' : 'text-accent'}">
									{relLabel(rel)}
								</p>
								<p class="text-xs text-ink-dim">{round.total_score} throws</p>
							</div>
						{:else}
							<a
								href="/rounds/{round.round_id}"
								class="rounded-lg bg-accent px-3 py-1.5 text-xs font-bold text-surface"
							>
								Resume
							</a>
						{/if}
						<div class="relative">
							<button
								class="flex h-10 w-10 items-center justify-center rounded-lg text-ink-dim transition active:scale-95"
								aria-label="Round options"
								aria-expanded={menuFor === round.round_id}
								onclick={() => (menuFor = menuFor === round.round_id ? null : round.round_id)}
							>
								<svg class="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
									<path d="M12 6.75a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3Zm0 6.75a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3Zm0 6.75a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3Z" />
								</svg>
							</button>
							{#if menuFor === round.round_id}
								<button
									class="fixed inset-0 z-40 cursor-default"
									aria-label="Close menu"
									onclick={() => (menuFor = null)}
								></button>
								<div
									class="absolute top-10 right-0 z-50 w-44 overflow-hidden rounded-xl border border-edge bg-card-raised shadow-lg"
								>
									<button
										class="w-full px-4 py-3 text-left text-sm font-semibold text-red-400 transition active:bg-card"
										onclick={() => {
											menuFor = null;
											removeRound(round.round_id);
										}}
									>
										Delete round
									</button>
								</div>
							{/if}
						</div>
					</div>
				</div>
				{#if holes.length > 0}
					<div class="mt-3 flex flex-wrap gap-1">
						{#each holes as h (h.number)}
							<span
								class="flex h-7 w-7 items-center justify-center rounded-md text-xs font-bold {scoreColor(h.score, h.par)}"
								title="Hole {h.number} · Par {h.par}"
							>
								{h.score && h.score > 0 ? h.score : '·'}
							</span>
						{/each}
					</div>
				{/if}
				{#if rs && rs.holes_with_throws > 0}
					<div class="mt-3 flex gap-4 border-t border-edge pt-2 text-xs text-ink-dim">
						{#if pct(rs.c1_putts_made, rs.c1_putts_attempted)}
							<span>C1 <span class="font-semibold text-ink">{pct(rs.c1_putts_made, rs.c1_putts_attempted)}</span></span>
						{/if}
						{#if pct(rs.c2_putts_made, rs.c2_putts_attempted)}
							<span>C2 <span class="font-semibold text-ink">{pct(rs.c2_putts_made, rs.c2_putts_attempted)}</span></span>
						{/if}
						{#if pct(rs.fairway_hits, rs.fairway_attempts)}
							<span>Fairway <span class="font-semibold text-ink">{pct(rs.fairway_hits, rs.fairway_attempts)}</span></span>
						{/if}
						{#if rs.parked > 0}
							<span>Parked <span class="font-semibold text-ink">{rs.parked}</span></span>
						{/if}
					</div>
				{/if}
			</div>
		{/each}
	{/if}
</main>
