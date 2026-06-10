<script lang="ts">
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/auth.svelte';
	import { createMappedHole } from '$lib/courseSave';
	import CourseMapper from '$lib/components/CourseMapper.svelte';
	import type { MapperHole } from '$lib/types';

	let name = $state('');
	let city = $state('');
	let stateName = $state('');
	let address = $state('');
	let holes = $state<MapperHole[]>([]);
	let saving = $state(false);
	let error = $state<string | null>(null);

	const completeHoles = $derived(holes.filter((h) => h.tee && h.pin));
	const canSave = $derived(name.trim().length > 0 && completeHoles.length > 0 && !saving);

	async function save() {
		if (!canSave) return;
		saving = true;
		error = null;
		try {
			const course = await api.createCourse({
				name: name.trim(),
				city: city.trim(),
				state: stateName.trim(),
				address: address.trim(),
				total_par: completeHoles.reduce((sum, h) => sum + h.par, 0)
			});
			for (const h of completeHoles) {
				await createMappedHole(course.course_id, h);
			}
			goto(`/courses/${course.course_id}`);
		} catch (e) {
			error = (e as Error).message;
			saving = false;
		}
	}
</script>

<header class="sticky top-0 z-30 bg-surface/95 px-4 pt-6 pb-3 backdrop-blur">
	<a href="/" class="mb-2 flex items-center gap-1 text-sm text-accent">
		<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
			<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
		</svg>
		Courses
	</a>
	<h1 class="text-2xl font-bold">New course</h1>
</header>

<main class="px-4 pt-2 pb-8">
	{#if !auth.isAdmin}
		<p class="rounded-xl bg-card p-4 text-sm text-ink-dim">
			Course mapping requires admin access.
		</p>
	{:else}
		<div class="space-y-2">
			<input
				type="text"
				placeholder="Course name"
				bind:value={name}
				class="w-full rounded-xl border border-edge bg-card px-4 py-2.5 text-sm placeholder:text-ink-dim focus:border-accent focus:outline-none"
			/>
			<div class="flex gap-2">
				<input
					type="text"
					placeholder="City"
					bind:value={city}
					class="min-w-0 flex-1 rounded-xl border border-edge bg-card px-4 py-2.5 text-sm placeholder:text-ink-dim focus:border-accent focus:outline-none"
				/>
				<input
					type="text"
					placeholder="State"
					bind:value={stateName}
					class="w-24 rounded-xl border border-edge bg-card px-4 py-2.5 text-sm placeholder:text-ink-dim focus:border-accent focus:outline-none"
				/>
			</div>
			<input
				type="text"
				placeholder="Address (optional)"
				bind:value={address}
				class="w-full rounded-xl border border-edge bg-card px-4 py-2.5 text-sm placeholder:text-ink-dim focus:border-accent focus:outline-none"
			/>
		</div>

		<div class="pt-3">
			<CourseMapper bind:holes />
		</div>

		{#if error}
			<p class="mt-3 rounded-xl bg-red-950/60 p-3 text-sm text-red-300">{error}</p>
		{/if}

		<button
			class="mt-4 w-full rounded-2xl bg-accent py-4 text-base font-bold text-surface transition active:scale-[0.98] disabled:opacity-50"
			onclick={save}
			disabled={!canSave}
		>
			{saving
				? 'Saving…'
				: `Save course${completeHoles.length ? ` · ${completeHoles.length} holes` : ''}`}
		</button>
	{/if}
</main>
