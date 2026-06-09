<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth } from '$lib/auth.svelte';
	import { api } from '$lib/api';
	import type { Round } from '$lib/types';

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
	let discCount = $state<number | null>(null);

	$effect(() => {
		api
			.listRounds()
			.then((r) => (rounds = r))
			.catch(() => {});
		api
			.getDiscs()
			.then((d) => (discCount = d.length))
			.catch(() => {});
	});

	const finished = $derived(rounds.filter((r) => r.total_score !== null));
	const bestScore = $derived(
		finished.length > 0 ? Math.min(...finished.map((r) => r.total_score!)) : null
	);

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
	<div class="grid grid-cols-3 gap-3">
		<div class="rounded-2xl border border-edge bg-card p-4 text-center">
			<p class="text-2xl font-bold text-accent">{finished.length}</p>
			<p class="text-xs text-ink-dim">rounds played</p>
		</div>
		<div class="rounded-2xl border border-edge bg-card p-4 text-center">
			<p class="text-2xl font-bold text-accent">{bestScore ?? '–'}</p>
			<p class="text-xs text-ink-dim">best round</p>
		</div>
		<div class="rounded-2xl border border-edge bg-card p-4 text-center">
			<p class="text-2xl font-bold text-accent">{discCount ?? '–'}</p>
			<p class="text-xs text-ink-dim">discs bagged</p>
		</div>
	</div>

	<button
		class="w-full rounded-2xl border border-red-900/60 bg-red-950/40 py-3 text-sm font-semibold text-red-300 transition active:scale-[0.98]"
		onclick={logout}
	>
		Sign out
	</button>
</main>
