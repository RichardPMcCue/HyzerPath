<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { goto, replaceState } from '$app/navigation';
	import { page } from '$app/state';
	import { auth } from '$lib/auth.svelte';
	import BottomNav from '$lib/components/BottomNav.svelte';

	let { children } = $props();

	let ready = $state(false);

	onMount(() => {
		// Capture the OAuth redirect: backend sends us back with ?token=...
		const token = page.url.searchParams.get('token');
		if (token) {
			auth.login(token);
			const url = new URL(page.url.href);
			url.searchParams.delete('token');
			replaceState(url, {});
		}

		if (!auth.isLoggedIn && page.url.pathname !== '/login') {
			goto('/login', { replaceState: true });
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
