<script lang="ts">
	import { page } from '$app/state';

	const tabs = [
		{
			href: '/',
			label: 'Courses',
			match: (p: string) => p === '/' || p.startsWith('/courses'),
			icon: 'M9 6.75V15m6-6v8.25m.503 3.498 4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 0 0-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0Z'
		},
		{
			href: '/bag',
			label: 'Bag',
			match: (p: string) => p.startsWith('/bag'),
			icon: 'M15.75 10.5V6a3.75 3.75 0 1 0-7.5 0v4.5m11.356-1.993 1.263 12c.07.665-.45 1.243-1.119 1.243H4.25a1.125 1.125 0 0 1-1.12-1.243l1.264-12A1.125 1.125 0 0 1 5.513 7.5h12.974c.576 0 1.059.435 1.119 1.007Z'
		},
		{
			href: '/profile',
			label: 'Profile',
			match: (p: string) => p.startsWith('/profile'),
			icon: 'M17.982 18.725A7.488 7.488 0 0 0 12 15.75a7.488 7.488 0 0 0-5.982 2.975m11.963 0a9 9 0 1 0-11.963 0m11.963 0A8.966 8.966 0 0 1 12 21a8.966 8.966 0 0 1-5.982-2.275M15 9.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z'
		}
	];
</script>

<nav
	class="fixed inset-x-0 bottom-0 z-40 border-t border-edge bg-card/95 backdrop-blur"
	style="padding-bottom: env(safe-area-inset-bottom)"
>
	<div class="mx-auto flex max-w-md items-stretch justify-around">
		{#each tabs as tab (tab.href)}
			{@const active = tab.match(page.url.pathname)}
			<a
				href={tab.href}
				class="flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-medium transition-colors
					{active ? 'text-accent' : 'text-ink-dim'}"
			>
				<svg
					class="h-6 w-6"
					fill="none"
					viewBox="0 0 24 24"
					stroke-width="1.7"
					stroke="currentColor"
				>
					<path stroke-linecap="round" stroke-linejoin="round" d={tab.icon} />
				</svg>
				{tab.label}
			</a>
		{/each}
	</div>
</nav>
