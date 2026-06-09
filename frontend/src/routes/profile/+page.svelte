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

	$effect(() => {
		Promise.all([api.listRounds(), api.getCourses()])
			.then(([r, c]) => {
				rounds = r;
				courses = new Map(c.map((course) => [course.course_id, course]));
			})
			.catch(() => {});
	});

	function holesFor(round: Round) {
		const course = courses.get(round.course_id);
		if (!course) return [];
		const scoreByHole = new Map(round.round_holes.map((rh) => [rh.hole_id, rh.score]));
		return [...course.holes]
			.sort((a, b) => a.hole_number - b.hole_number)
			.map((h) => ({
				number: h.hole_number,
				par: h.par,
				score: scoreByHole.get(h.hole_id)
			}));
	}

	function relative(round: Round): number {
		return holesFor(round).reduce(
			(rel, h) => (h.score && h.score > 0 ? rel + h.score - h.par : rel),
			0
		);
	}

	function relLabel(rel: number): string {
		return rel === 0 ? 'E' : rel > 0 ? `+${rel}` : `${rel}`;
	}

	// uDisc-style score coloring
	function scoreColor(score: number | undefined, par: number): string {
		if (!score) return 'bg-card-raised text-ink-dim';
		const diff = score - par;
		if (diff <= -2) return 'bg-teal-500 text-surface';
		if (diff === -1) return 'bg-accent text-surface';
		if (diff === 0) return 'bg-card-raised text-ink';
		if (diff === 1) return 'bg-amber-500 text-surface';
		return 'bg-red-500 text-surface';
	}

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

	<!-- Round history -->
	<h2 class="px-1 pt-2 text-xs font-semibold tracking-wide text-ink-dim uppercase">Rounds</h2>
	{#if rounds.length === 0}
		<p class="rounded-2xl border border-edge bg-card p-4 text-sm text-ink-dim">
			No rounds yet — open a course and hit ▶ Play.
		</p>
	{:else}
		{#each rounds as round (round.round_id)}
			{@const course = courses.get(round.course_id)}
			{@const holes = holesFor(round)}
			{@const rel = relative(round)}
			<div class="rounded-2xl border border-edge bg-card p-4">
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
				</div>
				{#if holes.length > 0}
					<div class="mt-3 flex flex-wrap gap-1">
						{#each holes as h (h.number)}
							<span
								class="flex h-7 w-7 items-center justify-center rounded-md text-[11px] font-bold {scoreColor(h.score, h.par)}"
								title="Hole {h.number} · Par {h.par}"
							>
								{h.score && h.score > 0 ? h.score : '·'}
							</span>
						{/each}
					</div>
				{/if}
			</div>
		{/each}
	{/if}

	<button
		class="w-full rounded-2xl border border-red-900/60 bg-red-950/40 py-3 text-sm font-semibold text-red-300 transition active:scale-[0.98]"
		onclick={logout}
	>
		Sign out
	</button>
</main>
