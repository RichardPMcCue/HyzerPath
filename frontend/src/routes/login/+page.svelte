<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/auth.svelte';
	import { loginUrl } from '$lib/api';

	onMount(() => {
		if (auth.isLoggedIn) goto('/', { replaceState: true });
	});
</script>

<div class="flex min-h-dvh flex-col items-center justify-center gap-10 px-8">
	<div class="flex flex-col items-center gap-4">
		<img src="/icon.svg" alt="HyzerPath" class="h-24 w-24 rounded-3xl shadow-lg shadow-accent/20" />
		<h1 class="text-4xl font-bold tracking-tight">
			Hyzer<span class="text-accent">Path</span>
		</h1>
		<p class="text-center text-sm text-ink-dim">
			Your intelligent disc golf caddie.<br />
			The right disc, the right line, every throw.
		</p>
	</div>

	<a
		href={loginUrl()}
		class="flex w-full max-w-xs items-center justify-center gap-3 rounded-xl bg-white py-3.5 font-semibold text-gray-800 shadow-lg transition active:scale-95"
	>
		<svg class="h-5 w-5" viewBox="0 0 24 24">
			<path
				fill="#4285F4"
				d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1Z"
			/>
			<path
				fill="#34A853"
				d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z"
			/>
			<path
				fill="#FBBC05"
				d="M5.84 14.1A6.6 6.6 0 0 1 5.5 12c0-.73.13-1.44.34-2.1V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84Z"
			/>
			<path
				fill="#EA4335"
				d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15A11 11 0 0 0 12 1 11 11 0 0 0 2.18 7.06l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38Z"
			/>
		</svg>
		Continue with Google
	</a>
</div>
