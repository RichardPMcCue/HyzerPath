<script lang="ts">
	import { api } from '$lib/api';
	import { auth } from '$lib/auth.svelte';
	import type { Me } from '$lib/types';

	let users = $state<Me[] | null>(null);
	let error = $state<string | null>(null);
	let busyId = $state<number | null>(null);

	$effect(() => {
		if (!auth.isAdmin) return;
		api
			.listUsers()
			.then((u) => (users = u))
			.catch((e) => (error = e.message));
	});

	async function toggleAdmin(user: Me) {
		busyId = user.user_id;
		error = null;
		try {
			const updated = await api.setUserAdmin(user.user_id, !(user.is_admin === true));
			users = users!.map((u) => (u.user_id === updated.user_id ? updated : u));
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busyId = null;
		}
	}
</script>

<header class="sticky top-0 z-30 bg-surface/95 px-4 pt-6 pb-3 backdrop-blur">
	<a href="/profile" class="mb-2 flex items-center gap-1 text-sm text-accent">
		<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
			<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
		</svg>
		Profile
	</a>
	<h1 class="text-2xl font-bold">Users</h1>
</header>

<main class="px-4 pt-2 pb-8">
	{#if !auth.isAdmin}
		<p class="rounded-xl bg-card p-4 text-sm text-ink-dim">This page requires admin access.</p>
	{:else if error}
		<p class="rounded-xl bg-red-950/60 p-4 text-sm text-red-300">{error}</p>
	{:else if users === null}
		<div class="space-y-3 pt-2">
			{#each Array(3) as _, i (i)}
				<div class="h-16 animate-pulse rounded-2xl bg-card"></div>
			{/each}
		</div>
	{:else}
		<div class="space-y-2 pt-2">
			{#each users as user (user.user_id)}
				<div class="flex items-center gap-3 rounded-2xl border border-edge bg-card px-4 py-3">
					<div class="min-w-0 flex-1">
						<p class="truncate text-sm font-semibold">
							{user.username ?? user.name ?? `User #${user.user_id}`}
							{#if user.user_id === auth.user?.user_id}
								<span class="text-xs font-normal text-ink-dim">(you)</span>
							{/if}
						</p>
						<p class="truncate text-xs text-ink-dim">#{user.user_id} · {user.email}</p>
					</div>
					<button
						class="shrink-0 rounded-xl px-3 py-2 text-xs font-bold transition active:scale-95 disabled:opacity-50
							{user.is_admin
							? 'bg-accent/15 text-accent'
							: 'border border-edge text-ink-dim'}"
						onclick={() => toggleAdmin(user)}
						disabled={busyId === user.user_id ||
							(user.user_id === auth.user?.user_id && user.is_admin === true)}
					>
						{busyId === user.user_id ? '…' : user.is_admin ? 'Admin ✓' : 'Make admin'}
					</button>
				</div>
			{/each}
		</div>
	{/if}
</main>
