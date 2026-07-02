<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import type { Course, RoundLayout, TrackingMode } from '$lib/types';

	const courseId = $derived(Number(page.params.courseId));

	let course = $state<Course | null>(null);
	let error = $state<string | null>(null);
	let starting = $state(false);

	let layout = $state<RoundLayout>('full');
	let mode = $state<TrackingMode>('lies');

	$effect(() => {
		api
			.getCourse(courseId)
			.then((c) => (course = c))
			.catch((e) => (error = e.message));
	});

	const hasBackNine = $derived((course?.holes.length ?? 0) > 9);

	const layouts: { value: RoundLayout; label: string; detail: string }[] = $derived([
		{ value: 'full', label: 'Full course', detail: `All ${course?.holes.length ?? '–'} holes` },
		...(hasBackNine
			? [
					{ value: 'front9' as RoundLayout, label: 'Front 9', detail: 'Holes 1–9' },
					{ value: 'back9' as RoundLayout, label: 'Back 9', detail: 'Holes 10+' }
				]
			: [])
	]);

	const modes: { value: TrackingMode; title: string; description: string }[] = [
		{
			value: 'score',
			title: 'Scores only',
			description: 'The traditional experience. Enter your score after every hole.'
		},
		{
			value: 'detail',
			title: 'Throw tracker (zones)',
			description:
				'Tap where each throw lands — basket, C1, C2, fairway, OB — and get putting percentages and driving accuracy. No GPS needed.'
		},
		{
			value: 'lies',
			title: 'GPS lies',
			description:
				'Mark each lie with GPS. The caddie replans from where you actually are, and stats come from real positions.'
		},
		{
			value: 'discs',
			title: 'GPS lies + discs (full stats)',
			description:
				'Everything in GPS lies, plus pick the disc after each throw. Builds your per-disc distance data automatically.'
		}
	];

	async function start() {
		starting = true;
		try {
			const round = await api.startRound(courseId, { tracking_mode: mode, layout });
			goto(`/rounds/${round.round_id}`, { replaceState: true });
		} catch (e) {
			error = (e as Error).message;
			starting = false;
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
	<h1 class="text-2xl font-bold">Round setup</h1>
	{#if course}
		<p class="mt-0.5 text-xs text-ink-dim">{course.name} · Par {course.total_par}</p>
	{/if}
</header>

<main class="space-y-5 px-4 pt-2 pb-8">
	{#if error}
		<p class="rounded-xl bg-red-950/60 p-4 text-sm text-red-300">{error}</p>
	{/if}

	<!-- Layout -->
	<section>
		<h2 class="px-1 pb-2 text-xs font-semibold tracking-wide text-ink-dim uppercase">Layout</h2>
		<div class="flex gap-2">
			{#each layouts as l (l.value)}
				<button
					class="flex-1 rounded-xl border p-3 text-left transition active:scale-[0.98]
						{layout === l.value ? 'border-accent bg-accent/10' : 'border-edge bg-card'}"
					onclick={() => (layout = l.value)}
				>
					<p class="text-sm font-semibold {layout === l.value ? 'text-accent' : ''}">{l.label}</p>
					<p class="mt-0.5 text-xs text-ink-dim">{l.detail}</p>
				</button>
			{/each}
		</div>
	</section>

	<!-- Record stats -->
	<section>
		<h2 class="px-1 pb-2 text-xs font-semibold tracking-wide text-ink-dim uppercase">
			Record stats
		</h2>
		<div class="space-y-2">
			{#each modes as m (m.value)}
				<button
					class="flex w-full items-start justify-between gap-3 rounded-2xl border p-4 text-left transition active:scale-[0.99]
						{mode === m.value ? 'border-accent bg-accent/10' : 'border-edge bg-card'}"
					onclick={() => (mode = m.value)}
				>
					<div>
						<p class="font-semibold {mode === m.value ? 'text-accent' : ''}">{m.title}</p>
						<p class="mt-1 text-xs leading-relaxed text-ink-dim">{m.description}</p>
					</div>
					{#if mode === m.value}
						<svg class="mt-1 h-5 w-5 shrink-0 text-accent" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5" />
						</svg>
					{/if}
				</button>
			{/each}
		</div>
	</section>

	<button
		class="w-full rounded-2xl bg-accent py-4 text-base font-bold text-surface transition active:scale-[0.98] disabled:opacity-50"
		onclick={start}
		disabled={starting || !course}
	>
		{starting ? 'Starting…' : '▶ Start round'}
	</button>
</main>
