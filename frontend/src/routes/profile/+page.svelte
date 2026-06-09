<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth } from '$lib/auth.svelte';
	import { api } from '$lib/api';
	import type { Course, Round } from '$lib/types';

	interface TokenPayload {
		user_id: number;
		exp: number;
	}

	function decodeToken(): TokenPayload | null {
		if (!auth.token) return null;
		try {
			return JSON.parse(atob(auth.token.split('.')[1]));
		} catch {
			return null;
		}
	}

	const payload = decodeToken();

	let rounds = $state<Round[]>([]);
	let courses = $state<Map<number, Course>>(new Map());
	let discCount = $state<number | null>(null);

	$effect(() => {
		Promise.all([api.listRounds(), api.getCourses()])
			.then(([r, c]) => {
				rounds = r;
				courses = new Map(c.map((course) => [course.course_id, course]));
			})
			.catch(() => {});
		api
			.getDiscs()
			.then((d) => (discCount = d.length))
			.catch(() => {});
	});

	const finished = $derived(rounds.filter((r) => r.total_score !== null));

	function relativeScore(round: Round): number {
		const course = courses.get(round.course_id);
		if (!course) return 0;
		const parByHole = new Map(course.holes.map((h) => [h.hole_id, h.par]));
		return round.round_holes.reduce(
			(rel, rh) => (rh.score > 0 ? rel + rh.score - (parByHole.get(rh.hole_id) ?? 3) : rel),
			0
		);
	}

	const LAYOUT_LABELS: Record<string, string> = {
		full: 'Full course',
		front9: 'Front 9',
		back9: 'Back 9'
	};

	// Best round = lowest score relative to par
	const bestRound = $derived.by(() => {
		if (finished.length === 0 || courses.size === 0) return null;
		let best: { round: Round; rel: number } | null = null;
		for (const round of finished) {
			const rel = relativeScore(round);
			if (best === null || rel < best.rel) best = { round, rel };
		}
		return best;
	});

	const relLabel = (rel: number) => (rel === 0 ? 'E' : rel > 0 ? `+${rel}` : `${rel}`);

	function logout() {
		auth.logout();
		goto('/login');
	}
</script>

<header class="px-4 pt-6 pb-3">
	<h1 class="text-2xl font-bold">Profile</h1>
</header>

<main class="space-y-4 px-4 pt-2">
	<div class="rounded-2xl border border-edge bg-card p-4">
		<p class="text-xs tracking-wide text-ink-dim uppercase">Signed in</p>
		<p class="mt-1 font-semibold">User #{payload?.user_id ?? '?'}</p>
		{#if payload}
			<p class="mt-0.5 text-xs text-ink-dim">
				Session expires {new Date(payload.exp * 1000).toLocaleDateString()}
			</p>
		{/if}
	</div>

	<!-- Lifetime stats -->
	<div class="grid grid-cols-2 gap-3">
		<div class="rounded-2xl border border-edge bg-card p-4 text-center">
			<p class="text-2xl font-bold text-accent">{finished.length}</p>
			<p class="text-xs text-ink-dim">rounds played</p>
		</div>
		<div class="rounded-2xl border border-edge bg-card p-4 text-center">
			<p class="text-2xl font-bold text-accent">{discCount ?? '–'}</p>
			<p class="text-xs text-ink-dim">discs bagged</p>
		</div>
	</div>
	<div class="rounded-2xl border border-edge bg-card p-4">
		<p class="text-xs tracking-wide text-ink-dim uppercase">Best round</p>
		{#if bestRound}
			<div class="mt-1 flex items-baseline gap-2">
				<p class="text-2xl font-bold {bestRound.rel > 0 ? 'text-amber-300' : 'text-accent'}">
					{relLabel(bestRound.rel)}
					<span class="text-base font-semibold text-ink-dim">({bestRound.round.total_score})</span>
				</p>
			</div>
			<p class="mt-0.5 text-xs text-ink-dim">
				{courses.get(bestRound.round.course_id)?.name ?? `Course ${bestRound.round.course_id}`}
				· {LAYOUT_LABELS[bestRound.round.layout] ?? bestRound.round.layout}
				· {new Date(bestRound.round.played_at).toLocaleDateString(undefined, {
					month: 'short',
					day: 'numeric',
					year: 'numeric'
				})}
			</p>
		{:else}
			<p class="mt-1 text-sm text-ink-dim">Finish a round to set one.</p>
		{/if}
	</div>

	<button
		class="w-full rounded-2xl border border-red-900/60 bg-red-950/40 py-3 text-sm font-semibold text-red-300 transition active:scale-[0.98]"
		onclick={logout}
	>
		Sign out
	</button>
</main>
