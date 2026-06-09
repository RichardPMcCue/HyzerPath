<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import type { CaddieMode, Course, Disc, Hole, HolePath, Round } from '$lib/types';
	import HoleMap from '$lib/components/HoleMap.svelte';
	import SegmentCard from '$lib/components/SegmentCard.svelte';

	const roundId = $derived(Number(page.params.roundId));

	// How much to track: disc per throw / GPS lies only / pure score entry
	type Tracking = 'discs' | 'lies' | 'score';
	let tracking = $state<Tracking>('lies');

	let round = $state<Round | null>(null);
	let course = $state<Course | null>(null);
	let path = $state<HolePath | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(false);
	let finishing = $state(false);

	let currentHoleId = $state<number | null>(null);
	let mode = $state<CaddieMode>('balanced');
	let lie = $state<{ latitude: number; longitude: number } | null>(null);
	let markingLie = $state(false);
	let scores = $state<Map<number, number>>(new Map());

	// Disc-tracking state: previous position (tee or last lie) and the throw
	// awaiting a disc choice
	let discs = $state<Disc[]>([]);
	let prevPoint = $state<{ latitude: number; longitude: number } | null>(null);
	let pendingThrow = $state<{
		end: { latitude: number; longitude: number };
		holeOut: boolean;
	} | null>(null);
	let savingThrow = $state(false);

	$effect(() => {
		api
			.getDiscs()
			.then((d) => (discs = d))
			.catch(() => {});
	});

	const teeCoords = $derived.by(() => {
		const tee = path?.nodes.find(
			(n) => n.node_type === 'tee' && n.hole_node_id !== 0 && n.latitude !== null
		);
		return tee ? { latitude: tee.latitude!, longitude: tee.longitude! } : null;
	});

	const sortedHoles = $derived(
		course ? [...course.holes].sort((a, b) => a.hole_number - b.hole_number) : []
	);
	const currentHole = $derived<Hole | undefined>(
		sortedHoles.find((h) => h.hole_id === currentHoleId)
	);
	const totalRelative = $derived.by(() => {
		let rel = 0;
		for (const h of sortedHoles) {
			const s = scores.get(h.hole_id);
			if (s !== undefined && s > 0) rel += s - h.par;
		}
		return rel;
	});
	const strokes = $derived(currentHole ? (scores.get(currentHole.hole_id) ?? 0) : 0);

	$effect(() => {
		(async () => {
			try {
				const r = await api.getRound(roundId);
				round = r;
				scores = new Map(r.round_holes.map((rh) => [rh.hole_id, rh.score]));
				const c = await api.getCourse(r.course_id);
				course = c;
				if (currentHoleId === null && c.holes.length > 0) {
					currentHoleId = [...c.holes].sort((a, b) => a.hole_number - b.hole_number)[0].hole_id;
				}
			} catch (e) {
				error = (e as Error).message;
			}
		})();
	});

	// Refetch the plan whenever hole / mode / lie changes
	$effect(() => {
		if (!round || currentHoleId === null) return;
		loading = true;
		api
			.getHolePath(round.course_id, currentHoleId, { mode, lie: lie ?? undefined })
			.then((p) => {
				path = p;
				error = null;
			})
			.catch((e) => {
				path = null;
				error = e.message;
			})
			.finally(() => (loading = false));
	});

	function selectHole(holeId: number) {
		if (holeId === currentHoleId) return;
		currentHoleId = holeId;
		lie = null; // new hole, new tee shot
		prevPoint = null;
		pendingThrow = null;
	}

	// Records the completed throw (prev position -> end) as a one-throw
	// measuring session so it feeds UserDiscStat, exactly like the Measure tab.
	async function recordThrowSegment(discId: number | null, end: { latitude: number; longitude: number }) {
		const start = prevPoint ?? teeCoords;
		if (!start || discId === null) return;
		try {
			const s = await api.createThrowSession({
				start_latitude: start.latitude,
				start_longitude: start.longitude,
				label: `Round ${roundId}`
			});
			await api.recordThrow(s.session_id, {
				end_latitude: end.latitude,
				end_longitude: end.longitude,
				disc_id: discId
			});
		} catch {
			/* stat logging is best-effort; the stroke already counted */
		}
	}

	async function resolvePendingThrow(discId: number | null) {
		if (!pendingThrow) return;
		savingThrow = true;
		const { end, holeOut: wasHoleOut } = pendingThrow;
		try {
			await recordThrowSegment(discId, end);
		} finally {
			savingThrow = false;
			pendingThrow = null;
			if (wasHoleOut) advanceHole();
		}
	}

	function advanceHole() {
		if (!currentHole) return;
		lie = null;
		prevPoint = null;
		const idx = sortedHoles.findIndex((h) => h.hole_id === currentHole!.hole_id);
		if (idx >= 0 && idx < sortedHoles.length - 1) {
			currentHoleId = sortedHoles[idx + 1].hole_id;
		}
	}

	async function saveScore(holeId: number, value: number) {
		scores = new Map(scores).set(holeId, value);
		try {
			await api.setHoleScore(roundId, holeId, value);
		} catch (e) {
			error = (e as Error).message;
		}
	}

	// Each marked lie IS a throw: you threw, walked to the disc, marked it.
	async function markLie() {
		if (!currentHole) return;
		markingLie = true;
		try {
			const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
				navigator.geolocation.getCurrentPosition(resolve, (e) => reject(new Error(e.message)), {
					enableHighAccuracy: true,
					timeout: 15000,
					maximumAge: 0
				});
			});
			const point = { latitude: pos.coords.latitude, longitude: pos.coords.longitude };
			await saveScore(currentHole.hole_id, strokes + 1);
			if (tracking === 'discs') {
				pendingThrow = { end: point, holeOut: false }; // ask which disc
			}
			lie = point;
			prevPoint = point;
		} catch (e) {
			error = (e as Error).message;
		} finally {
			markingLie = false;
		}
	}

	// The holing throw: counts a stroke, no lie to mark, advance to next hole.
	async function holeOut() {
		if (!currentHole) return;
		await saveScore(currentHole.hole_id, strokes + 1);
		const basket = path?.nodes.find((n) => n.node_type === 'basket' && n.latitude !== null);
		if (tracking === 'discs' && basket) {
			// Ask for the disc before moving on; advance happens after the sheet
			pendingThrow = {
				end: { latitude: basket.latitude!, longitude: basket.longitude! },
				holeOut: true
			};
			return;
		}
		advanceHole();
	}

	// Manual correction: penalty strokes (+) or deleting a misrecorded throw (−).
	// In score-only mode the stepper starts from par like a classic scorecard.
	async function bumpScore(delta: number) {
		if (!currentHole) return;
		const base = tracking === 'score' ? (scores.get(currentHole.hole_id) ?? currentHole.par) : strokes;
		const next = Math.max(tracking === 'score' ? 1 : 0, base + delta);
		await saveScore(currentHole.hole_id, next);
	}

	async function abandonRound() {
		if (!confirm('Abandon this round? Scores will be deleted.')) return;
		try {
			await api.deleteRound(roundId);
			goto('/profile');
		} catch (e) {
			error = (e as Error).message;
		}
	}

	async function finishRound() {
		finishing = true;
		try {
			await api.finishRound(roundId);
			goto('/profile'); // round history lives here
		} catch (e) {
			error = (e as Error).message;
			finishing = false;
		}
	}

	const scoreLabel = (hole: Hole) => {
		const s = scores.get(hole.hole_id);
		if (s === undefined || s === 0) return null;
		const diff = s - hole.par;
		return diff === 0 ? 'E' : diff > 0 ? `+${diff}` : `${diff}`;
	};
</script>

<header class="sticky top-0 z-30 bg-surface/95 px-4 pt-6 pb-3 backdrop-blur">
	<div class="flex items-center justify-between">
		<div>
			<p class="text-xs tracking-wide text-ink-dim uppercase">Playing</p>
			<h1 class="text-lg font-bold">{course?.name ?? '…'}</h1>
		</div>
		<div class="text-right">
			<p class="text-2xl font-bold {totalRelative > 0 ? 'text-amber-300' : 'text-accent'}">
				{totalRelative === 0 ? 'E' : totalRelative > 0 ? `+${totalRelative}` : totalRelative}
			</p>
			<div class="flex gap-3">
				<button class="text-xs font-medium text-red-400/80 underline" onclick={abandonRound}>
					Abandon
				</button>
				<button class="text-xs font-medium text-ink-dim underline" onclick={finishRound} disabled={finishing}>
					{finishing ? 'Saving…' : 'Finish round'}
				</button>
			</div>
		</div>
	</div>

	<!-- Hole strip -->
	<div class="-mx-4 mt-3 overflow-x-auto px-4">
		<div class="flex w-max gap-1.5">
			{#each sortedHoles as hole (hole.hole_id)}
				{@const label = scoreLabel(hole)}
				<button
					class="flex h-12 w-10 flex-col items-center justify-center rounded-lg border text-xs font-bold transition
						{hole.hole_id === currentHoleId
						? 'border-accent bg-accent/15 text-accent'
						: 'border-edge bg-card text-ink-dim'}"
					onclick={() => selectHole(hole.hole_id)}
				>
					{hole.hole_number}
					{#if label}
						<span class="text-[10px] font-semibold {label.startsWith('+') ? 'text-amber-300' : 'text-accent'}">{label}</span>
					{/if}
				</button>
			{/each}
		</div>
	</div>
</header>

<main class="space-y-4 px-4 pt-2">
	{#if currentHole}
		<div class="flex items-center justify-between px-1">
			<p class="text-sm text-ink-dim">
				Hole {currentHole.hole_number} · Par {currentHole.par} · {currentHole.distance} ft
			</p>
			{#if lie}
				<button class="text-xs font-medium text-sky-400" onclick={() => (lie = null)}>
					✕ back to tee view
				</button>
			{/if}
		</div>
	{/if}

	{#if path}
		<HoleMap
			nodes={path.nodes}
			recommendations={path.recommendations}
			fairwayPolygon={path.fairway_polygon}
		/>
	{/if}

	<!-- Throw actions (hidden in score-only mode) -->
	{#if tracking !== 'score'}
		<div class="flex items-center gap-2">
			<button
				class="flex flex-1 items-center justify-center gap-2 rounded-xl py-3.5 font-bold transition active:scale-95 disabled:opacity-50
					{lie ? 'border border-sky-500/40 bg-sky-500/20 text-sky-300' : 'bg-accent text-surface'}"
				onclick={markLie}
				disabled={markingLie}
			>
				<svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
					<path stroke-linecap="round" stroke-linejoin="round" d="M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
					<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z" />
				</svg>
				{markingLie ? 'Locating…' : 'Mark my lie'}
			</button>
			<button
				class="flex flex-1 items-center justify-center gap-2 rounded-xl border border-edge bg-card py-3.5 font-bold text-ink transition active:scale-95"
				onclick={holeOut}
			>
				🧺 In the basket
			</button>
		</div>
	{/if}

	<!-- Caddie mode + tracking level -->
	<div class="flex gap-2">
		<div class="flex flex-1 rounded-xl border border-edge bg-card p-1">
			{#each [['conservative', 'Safe'], ['balanced', 'Bal'], ['aggressive', 'Send']] as [value, label] (value)}
				<button
					class="flex-1 rounded-lg py-1.5 text-xs font-semibold transition
						{mode === value ? 'bg-accent text-surface' : 'text-ink-dim'}"
					onclick={() => (mode = value as CaddieMode)}
				>
					{label}
				</button>
			{/each}
		</div>
		<div class="flex flex-1 rounded-xl border border-edge bg-card p-1" title="How much to track">
			{#each [['discs', '🥏 Discs'], ['lies', '📍 Lies'], ['score', '# Score']] as [value, label] (value)}
				<button
					class="flex-1 rounded-lg py-1.5 text-[11px] font-semibold whitespace-nowrap transition
						{tracking === value ? 'bg-sky-500/25 text-sky-300' : 'text-ink-dim'}"
					onclick={() => (tracking = value as Tracking)}
				>
					{label}
				</button>
			{/each}
		</div>
	</div>

	{#if error}
		<p class="rounded-xl bg-red-950/60 p-4 text-sm text-red-300">{error}</p>
	{:else if path}
		<div class="space-y-3 {loading ? 'opacity-60' : ''}">
			{#each path.recommendations as rec, i (rec.from_node_id + '-' + rec.to_node_id)}
				<SegmentCard {rec} index={i} />
			{/each}
		</div>
	{/if}

	<!-- Stroke count: auto-counts from marked lies + holing out; −/+ for
	     deleting a misrecorded throw or adding a penalty. Score-only mode
	     works like a classic scorecard starting from par. -->
	{#if currentHole}
		{@const displayed = tracking === 'score' ? (scores.get(currentHole.hole_id) ?? currentHole.par) : strokes}
		<div class="flex items-center justify-between rounded-2xl border border-edge bg-card p-4">
			<button
				class="flex h-12 w-12 items-center justify-center rounded-xl bg-card-raised text-2xl font-bold transition active:scale-90 disabled:opacity-40"
				onclick={() => bumpScore(-1)}
				disabled={tracking !== 'score' && strokes === 0}
				aria-label="Remove a throw"
			>
				−
			</button>
			<div class="text-center">
				<p class="text-3xl font-bold {displayed === 0 ? 'text-ink-dim' : ''}">{displayed}</p>
				<p class="text-xs text-ink-dim">
					{tracking === 'score'
						? scores.has(currentHole.hole_id)
							? 'strokes'
							: 'tap − / + to score'
						: strokes === 0
							? 'tee off, then mark your lie'
							: `throw${strokes === 1 ? '' : 's'}`}
				</p>
			</div>
			<button
				class="flex h-12 w-12 items-center justify-center rounded-xl bg-card-raised text-2xl font-bold transition active:scale-90"
				onclick={() => bumpScore(1)}
				aria-label="Add a penalty throw"
			>
				+
			</button>
		</div>
	{/if}
</main>

<!-- Disc picker sheet: which disc was that throw? -->
{#if pendingThrow}
	<div class="fixed inset-x-0 bottom-0 z-50 mx-auto max-w-md rounded-t-2xl border-t border-edge bg-card/95 p-4 pb-24 backdrop-blur">
		<p class="text-sm font-semibold">
			{pendingThrow.holeOut ? 'Holed out! What did you putt with?' : 'What did you throw?'}
		</p>
		<div class="-mx-1 mt-2 overflow-x-auto px-1">
			<div class="flex w-max gap-2">
				{#each discs as disc (disc.disc_id)}
					<button
						class="rounded-full border border-edge bg-card-raised px-3.5 py-2 text-xs font-semibold whitespace-nowrap transition active:scale-95 disabled:opacity-50"
						onclick={() => resolvePendingThrow(disc.disc_id)}
						disabled={savingThrow}
					>
						{disc.name}
					</button>
				{/each}
			</div>
		</div>
		<button
			class="mt-3 w-full rounded-xl border border-edge py-2.5 text-xs font-semibold text-ink-dim transition active:scale-95"
			onclick={() => resolvePendingThrow(null)}
			disabled={savingThrow}
		>
			Skip
		</button>
	</div>
{/if}
