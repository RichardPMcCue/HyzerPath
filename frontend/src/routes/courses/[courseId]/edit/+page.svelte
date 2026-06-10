<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { auth } from '$lib/auth.svelte';
	import { createMappedHole, holeIsDirty, saveMappedHoleChanges } from '$lib/courseSave';
	import CourseMapper from '$lib/components/CourseMapper.svelte';
	import type { Course, MapperHole } from '$lib/types';

	const courseId = $derived(Number(page.params.courseId));

	let course = $state<Course | null>(null);
	let holes = $state<MapperHole[]>([]);
	let loadingHoles = $state(true);
	let saving = $state(false);
	let deleting = $state(false);
	let error = $state<string | null>(null);

	$effect(() => {
		load(courseId);
	});

	async function load(id: number) {
		loadingHoles = true;
		error = null;
		try {
			const c = await api.getCourse(id);
			course = c;
			const sorted = [...c.holes].sort((a, b) => a.hole_number - b.hole_number);
			const mapped: MapperHole[] = [];
			for (const hole of sorted) {
				const [nodes, hazards] = await Promise.all([
					api.getHoleNodes(id, hole.hole_id),
					api.getHoleHazards(id, hole.hole_id)
				]);
				const tee = nodes.find((n) => n.node_type === 'tee');
				const basket = nodes.find((n) => n.node_type === 'basket');
				const waypoints = nodes
					.filter(
						(n) => n.node_type === 'landing_zone' && n.latitude != null && n.longitude != null
					)
					.sort((a, b) => a.sequence - b.sequence);
				mapped.push({
					holeNumber: hole.hole_number,
					par: hole.par,
					holeId: hole.hole_id,
					tee:
						tee?.latitude != null && tee?.longitude != null
							? { lat: tee.latitude, lng: tee.longitude }
							: null,
					pin:
						basket?.latitude != null && basket?.longitude != null
							? { lat: basket.latitude, lng: basket.longitude }
							: null,
					fairway: waypoints.map((n) => ({
						lat: n.latitude!,
						lng: n.longitude!,
						nodeId: n.hole_node_id
					})),
					hazards: hazards.map((hz) => ({
						hazard_type: hz.hazard_type,
						polygon: hz.polygon.map(([lat, lng]) => ({ lat, lng })),
						hazardId: hz.hazard_id
					})),
					teeNodeId: tee?.hole_node_id,
					pinNodeId: basket?.hole_node_id
				});
			}
			holes = mapped;
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loadingHoles = false;
		}
	}

	const dirtyCount = $derived(holes.filter(holeIsDirty).length);

	async function save() {
		saving = true;
		error = null;
		try {
			for (const h of holes) {
				if (!h.holeId) {
					if (h.tee && h.pin) await createMappedHole(courseId, h);
					continue;
				}
				await saveMappedHoleChanges(courseId, h);
			}
			await load(courseId); // re-pull: server recomputed distances/total par
		} catch (e) {
			error = (e as Error).message;
		} finally {
			saving = false;
		}
	}

	async function onDeleteHole(h: MapperHole): Promise<boolean> {
		if (!h.holeId) return true;
		if (!confirm(`Delete hole ${h.holeNumber}?`)) return false;
		await api.deleteHole(courseId, h.holeId);
		return true;
	}

	async function deleteCourse() {
		if (!course) return;
		if (!confirm(`Delete "${course.name}" and all its holes? This cannot be undone.`)) return;
		deleting = true;
		error = null;
		try {
			await api.deleteCourse(courseId);
			goto('/');
		} catch (e) {
			error = (e as Error).message;
			deleting = false;
		}
	}
</script>

<header class="sticky top-0 z-30 bg-surface/95 px-4 pt-6 pb-3 backdrop-blur">
	<a href="/courses/{courseId}" class="mb-2 flex items-center gap-1 text-sm text-accent">
		<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
			<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
		</svg>
		{course?.name ?? 'Course'}
	</a>
	<h1 class="text-2xl font-bold">Edit course map</h1>
</header>

<main class="px-4 pt-2 pb-8">
	{#if !auth.isAdmin}
		<p class="rounded-xl bg-card p-4 text-sm text-ink-dim">
			Course editing requires admin access.
		</p>
	{:else if loadingHoles}
		<div class="h-[55dvh] animate-pulse rounded-2xl bg-card"></div>
	{:else}
		<CourseMapper bind:holes ondeletehole={onDeleteHole} />

		{#if error}
			<p class="mt-3 rounded-xl bg-red-950/60 p-3 text-sm text-red-300">{error}</p>
		{/if}

		<button
			class="mt-4 w-full rounded-2xl bg-accent py-4 text-base font-bold text-surface transition active:scale-[0.98] disabled:opacity-50"
			onclick={save}
			disabled={saving || dirtyCount === 0}
		>
			{saving ? 'Saving…' : dirtyCount === 0 ? 'No changes' : `Save ${dirtyCount} change${dirtyCount === 1 ? '' : 's'}`}
		</button>

		<div class="mt-8 rounded-2xl border border-red-900/50 p-4">
			<p class="text-xs font-semibold tracking-widest text-red-400/80 uppercase">Danger zone</p>
			<button
				class="mt-3 w-full rounded-xl border border-red-900 bg-red-950/40 py-3 text-sm font-bold text-red-400 transition active:scale-[0.98] disabled:opacity-50"
				onclick={deleteCourse}
				disabled={deleting}
			>
				{deleting ? 'Deleting…' : 'Delete this course'}
			</button>
		</div>
	{/if}
</main>
