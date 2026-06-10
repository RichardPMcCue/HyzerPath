<script lang="ts">
	import { api } from '$lib/api';
	import { auth } from '$lib/auth.svelte';
	import type { Course } from '$lib/types';

	let courses = $state<Course[] | null>(null);
	let error = $state<string | null>(null);
	let search = $state('');

	$effect(() => {
		api
			.getCourses()
			.then((c) => (courses = c))
			.catch((e) => (error = e.message));
	});

	const filtered = $derived(
		courses?.filter(
			(c) =>
				c.name.toLowerCase().includes(search.toLowerCase()) ||
				c.city.toLowerCase().includes(search.toLowerCase())
		) ?? []
	);
</script>

<header class="sticky top-0 z-30 bg-surface/95 px-4 pt-6 pb-3 backdrop-blur">
	<div class="flex items-center justify-between">
		<h1 class="text-2xl font-bold">Courses</h1>
		{#if auth.isAdmin}
			<a
				href="/courses/new"
				class="rounded-xl bg-accent px-3.5 py-2 text-sm font-bold text-surface transition active:scale-95"
			>
				+ New
			</a>
		{/if}
	</div>
	<input
		type="search"
		placeholder="Search courses or cities…"
		bind:value={search}
		class="mt-3 w-full rounded-xl border border-edge bg-card px-4 py-2.5 text-sm placeholder:text-ink-dim focus:border-accent focus:outline-none"
	/>
</header>

<main class="px-4 pt-2">
	{#if error}
		<p class="rounded-xl bg-red-950/60 p-4 text-sm text-red-300">{error}</p>
	{:else if courses === null}
		<div class="space-y-3 pt-2">
			{#each Array(4) as _, i (i)}
				<div class="h-24 animate-pulse rounded-2xl bg-card"></div>
			{/each}
		</div>
	{:else if filtered.length === 0}
		<p class="pt-10 text-center text-sm text-ink-dim">No courses found.</p>
	{:else}
		<div class="space-y-3 pt-2">
			{#each filtered as course (course.course_id)}
				<a
					href="/courses/{course.course_id}"
					class="block rounded-2xl border border-edge bg-card p-4 transition active:scale-[0.98]"
				>
					<div class="flex items-start justify-between">
						<div>
							<h2 class="font-semibold">{course.name}</h2>
							<p class="mt-0.5 text-xs text-ink-dim">{course.city}, {course.state}</p>
						</div>
						<svg
							class="mt-1 h-4 w-4 shrink-0 text-ink-dim"
							fill="none"
							viewBox="0 0 24 24"
							stroke-width="2"
							stroke="currentColor"
						>
							<path stroke-linecap="round" stroke-linejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
						</svg>
					</div>
					<div class="mt-3 flex gap-4 text-xs text-ink-dim">
						<span><span class="font-semibold text-ink">{course.holes.length}</span> holes</span>
						<span>Par <span class="font-semibold text-ink">{course.total_par}</span></span>
					</div>
				</a>
			{/each}
		</div>
	{/if}
</main>
