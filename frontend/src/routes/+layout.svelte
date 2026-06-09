<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { auth } from '$lib/auth.svelte';
	import BottomNav from '$lib/components/BottomNav.svelte';

	let { children } = $props();

	let ready = $state(false);

	onMount(() => {
		// Capture the OAuth redirect: backend sends us back with ?token=...
		// Native history API here — SvelteKit's router isn't initialized yet
		// when the root layout mounts in SPA mode.
		const params = new URLSearchParams(window.location.search);
		const token = params.get('token');
		if (token) {
			auth.login(token);
			const url = new URL(window.location.href);
			url.searchParams.delete('token');
			window.history.replaceState(window.history.state, '', url);
		}

		if (!auth.isLoggedIn && window.location.pathname !== '/login') {
			goto('/login', { replaceState: true }).catch(() => window.location.replace('/login'));
		}
		ready = true;
	});

	const onLoginPage = $derived(page.url.pathname === '/login');
</script>

{#if ready}
	<div class="mx-auto min-h-dvh max-w-md {onLoginPage ? '' : 'pb-20'}">
		{@render children()}
	</div>
	{#if !onLoginPage && auth.isLoggedIn}
		<BottomNav />
	{/if}
{/if}
