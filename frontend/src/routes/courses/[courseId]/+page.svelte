<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/auth.svelte';
	import type { Course } from '$lib/types';

	const courseId = $derived(Number(page.params.courseId));

	let course = $state<Course | null>(null);
	let error = $state<string | null>(null);

	$effect(() => {
		api
			.getCourse(courseId)
			.then((c) => (course = c))
			.catch((e) => (error = e.message));
	});

	const sortedHoles = $derived(
		course ? [...course.holes].sort((a, b) => a.hole_number - b.hole_number) : []
	);
</script>

<header class="sticky top-0 z-30 bg-surface/95 px-4 pt-6 pb-3 backdrop-blur">
	<a href="/" class="mb-2 flex items-center gap-1 text-sm text-accent">
		<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
			<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
		</svg>
		Courses
	</a>
	{#if course}
		<div class="flex items-end justify-between">
			<div>
				<h1 class="text-2xl font-bold">{course.name}</h1>
				<p class="mt-0.5 text-xs text-ink-dim">
					{course.city}, {course.state} · Par {course.total_par}
				</p>
			</div>
			<div class="flex gap-2">
				{#if auth.isAdmin}
					<button
						class="rounded-xl border border-edge bg-card px-3 py-2.5 text-sm font-semibold transition active:scale-95"
						onclick={() => goto(`/courses/${courseId}/edit`)}
						aria-label="Edit course map"
					>
						✏️
					</button>
				{/if}
				<button
					class="rounded-xl bg-accent px-4 py-2.5 text-sm font-bold text-surface transition active:scale-95"
					onclick={() => goto(`/courses/${courseId}/setup`)}
				>
					▶ Play
				</button>
			</div>
		</div>
	{/if}
</header>

<main class="px-4 pt-2">
	{#if error}
		<p class="rounded-xl bg-red-950/60 p-4 text-sm text-red-300">{error}</p>
	{:else if course === null}
		<div class="grid grid-cols-3 gap-3 pt-2">
			{#each Array(9) as _, i (i)}
				<div class="h-24 animate-pulse rounded-2xl bg-card"></div>
			{/each}
		</div>
	{:else if sortedHoles.length === 0}
		<p class="pt-10 text-center text-sm text-ink-dim">No holes mapped yet.</p>
	{:else}
		<div class="grid grid-cols-3 gap-3 pt-2">
			{#each sortedHoles as hole (hole.hole_id)}
				<a
					href="/courses/{courseId}/holes/{hole.hole_id}"
					class="flex flex-col items-center rounded-2xl border border-edge bg-card py-4 transition active:scale-95"
				>
					<span class="text-[10px] font-medium tracking-widest text-ink-dim uppercase">Hole</span>
					<span class="text-2xl font-bold text-accent">{hole.hole_number}</span>
					<span class="mt-1 text-xs text-ink-dim">Par {hole.par}</span>
					<span class="text-xs text-ink-dim">{hole.distance} ft</span>
				</a>
			{/each}
		</div>
	{/if}
</main>
