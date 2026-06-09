<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth } from '$lib/auth.svelte';

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

	<div class="rounded-2xl border border-edge bg-card p-4">
		<p class="text-xs tracking-wide text-ink-dim uppercase">Coming soon</p>
		<ul class="mt-2 space-y-1.5 text-sm text-ink-dim">
			<li>· Throw distance tracking per disc</li>
			<li>· Round history & scorecards</li>
			<li>· C1/C2 putting stats</li>
		</ul>
	</div>

	<button
		class="w-full rounded-2xl border border-red-900/60 bg-red-950/40 py-3 text-sm font-semibold text-red-300 transition active:scale-[0.98]"
		onclick={logout}
	>
		Sign out
	</button>
</main>
