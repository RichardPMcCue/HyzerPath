<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import type { CaddieMode, Course, Disc, Hole, HolePath, Round } from '$lib/types';
	import HoleMap from '$lib/components/HoleMap.svelte';
	import SegmentCard from '$lib/components/SegmentCard.svelte';

	const roundId = $derived(Number(page.params.roundId));

	// How much to track — chosen at round setup, stored on the round:
	// disc per throw (GPS) / GPS lies / landing zones (detailed, no GPS) /
	// pure score entry
	type Tracking = 'discs' | 'lies' | 'detail' | 'score';
	let tracking = $state<Tracking>('lies');

	// --- Detail (zone) mode state ---
	type Zone = 'basket' | 'c1' | 'c2' | 'fairway' | 'off_fairway' | 'ob';
	type DropZone = 'c1' | 'c2' | 'fairway' | 'off_fairway' | 'tee_pad';
	let detailThrows = $state<{ id: number; zone: Zone; drop?: DropZone; puttFt?: number }[]>([]);
	let zoneSheet = $state<null | { step: 'landing' } | { step: 'drop' } | { step: 'putt' }>(null);
	let savingZone = $state(false);

	const startZone = $derived.by((): string => {
		const last = detailThrows[detailThrows.length - 1];
		if (!last) return 'tee';
		return last.zone === 'ob' ? (last.drop ?? 'fairway') : last.zone;
	});
	const obCount = $derived(detailThrows.filter((t) => t.zone === 'ob').length);

	const ZONE_LABELS: Record<string, string> = {
		tee: 'Tee',
		basket: '🧺',
		c1: 'C1',
		c2: 'C2',
		fairway: 'Fairway',
		off_fairway: 'Off fairway',
		ob: 'OB',
		tee_pad: 'Tee pad'
	};

	async function commitZoneThrow(zone: Zone, drop?: DropZone, puttFt?: number) {
		if (!currentHole) return;
		savingZone = true;
		try {
			const saved = await api.recordRoundThrow(roundId, currentHole.hole_id, {
				throw_number: detailThrows.length + 1,
				landing_zone: zone,
				drop_zone: drop ?? null,
				putt_distance_ft: puttFt ?? null,
				is_holed: zone === 'basket'
			});
			detailThrows = [...detailThrows, { id: saved.round_throw_id, zone, drop, puttFt }];
			// Score = throws + one penalty per OB
			await saveScore(currentHole.hole_id, detailThrows.length + obCount);
			zoneSheet = null;
			if (zone === 'basket') advanceHole();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			savingZone = false;
		}
	}

	function pickLandingZone(zone: Zone) {
		if (zone === 'ob') {
			zoneSheet = { step: 'drop' };
		} else if (zone === 'basket' && (startZone === 'c1' || startZone === 'c2')) {
			zoneSheet = { step: 'putt' };
		} else {
			commitZoneThrow(zone);
		}
	}

	async function undoZoneThrow() {
		const last = detailThrows[detailThrows.length - 1];
		if (!last || !currentHole) return;
		try {
			await api.deleteRoundThrow(roundId, last.id);
			detailThrows = detailThrows.slice(0, -1);
			await saveScore(currentHole.hole_id, detailThrows.length + obCount);
		} catch (e) {
			error = (e as Error).message;
		}
	}

	const puttBands = $derived(
		startZone === 'c2'
			? [
					{ label: '33 – 44 ft', mid: 38 },
					{ label: '44 – 55 ft', mid: 50 },
					{ label: '55 – 66 ft', mid: 61 }
				]
			: [
					{ label: '0 – 11 ft', mid: 6 },
					{ label: '11 – 22 ft', mid: 16 },
					{ label: '22 – 33 ft', mid: 28 }
				]
	);

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
		number: number;
		start: { latitude: number; longitude: number } | null;
		end: { latitude: number; longitude: number } | null;
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

	const sortedHoles = $derived.by(() => {
		if (!course) return [];
		let holes = [...course.holes].sort((a, b) => a.hole_number - b.hole_number);
		if (round?.layout === 'front9') holes = holes.filter((h) => h.hole_number <= 9);
		if (round?.layout === 'back9') holes = holes.filter((h) => h.hole_number >= 10);
		return holes;
	});
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
				tracking = r.tracking_mode; // chosen at round setup
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
		detailThrows = [];
		zoneSheet = null;
	}

	// Persists a throw to round_throws: powers C1/C2 putting, fairway hits,
	// and (when a disc is tagged) UserDiscStat for the engine.
	async function recordThrow(t: {
		number: number;
		start: { latitude: number; longitude: number } | null;
		end: { latitude: number; longitude: number } | null;
		holeOut: boolean;
		discId: number | null;
	}) {
		if (!currentHole) return;
		try {
			await api.recordRoundThrow(roundId, currentHole.hole_id, {
				throw_number: t.number,
				disc_id: t.discId,
				start_latitude: t.start?.latitude ?? null,
				start_longitude: t.start?.longitude ?? null,
				end_latitude: t.end?.latitude ?? null,
				end_longitude: t.end?.longitude ?? null,
				is_holed: t.holeOut
			});
		} catch {
			/* throw logging is best-effort; the stroke already counted */
		}
	}

	async function resolvePendingThrow(discId: number | null) {
		if (!pendingThrow) return;
		savingThrow = true;
		const p = pendingThrow;
		try {
			await recordThrow({ ...p, discId });
		} finally {
			savingThrow = false;
			pendingThrow = null;
			if (p.holeOut) advanceHole();
		}
	}

	function advanceHole() {
		if (!currentHole) return;
		lie = null;
		prevPoint = null;
		detailThrows = [];
		zoneSheet = null;
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
			const number = strokes + 1;
			const start = prevPoint ?? teeCoords;
			await saveScore(currentHole.hole_id, number);
			if (tracking === 'discs') {
				pendingThrow = { number, start, end: point, holeOut: false }; // ask which disc
			} else {
				recordThrow({ number, start, end: point, holeOut: false, discId: null });
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
		const number = strokes + 1;
		const start = prevPoint ?? teeCoords;
		await saveScore(currentHole.hole_id, number);
		const basket = path?.nodes.find((n) => n.node_type === 'basket' && n.latitude !== null);
		const end = basket ? { latitude: basket.latitude!, longitude: basket.longitude! } : null;
		if (tracking === 'discs') {
			// Ask for the disc before moving on; advance happens after the sheet
			pendingThrow = { number, start, end, holeOut: true };
			return;
		}
		recordThrow({ number, start, end, holeOut: true, discId: null });
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

	<!-- Detail mode: record throws by landing zone, uDisc-style -->
	{#if tracking === 'detail'}
		<div class="flex items-center gap-2">
			<button
				class="flex flex-1 items-center justify-center gap-2 rounded-xl bg-accent py-3.5 font-bold text-surface transition active:scale-95"
				onclick={() => (zoneSheet = { step: 'landing' })}
			>
				＋ Record throw
			</button>
			{#if detailThrows.length > 0}
				<button
					class="rounded-xl border border-edge bg-card px-4 py-3.5 text-xs font-semibold text-ink-dim transition active:scale-95"
					onclick={undoZoneThrow}
				>
					Undo
				</button>
			{/if}
		</div>
		{#if detailThrows.length > 0}
			<div class="flex flex-wrap items-center gap-1 px-1 text-xs text-ink-dim">
				<span class="rounded bg-card-raised px-1.5 py-0.5 font-semibold">Tee</span>
				{#each detailThrows as t, i (t.id)}
					<span>→</span>
					<span class="rounded bg-card-raised px-1.5 py-0.5 font-semibold {t.zone === 'ob' ? 'text-red-400' : ''}">
						{ZONE_LABELS[t.zone]}{t.puttFt ? ` ${t.puttFt} ft` : ''}{t.zone === 'ob' && t.drop ? ` → ${ZONE_LABELS[t.drop]}` : ''}
					</span>
				{/each}
			</div>
		{/if}
	{/if}

	<!-- GPS throw actions (lies / discs modes) -->
	{#if tracking === 'lies' || tracking === 'discs'}
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

	<!-- Caddie mode (tracking level was chosen at round setup) -->
	<div class="flex rounded-xl border border-edge bg-card p-1">
		{#each [['conservative', 'Safe'], ['balanced', 'Balanced'], ['aggressive', 'Send it']] as [value, label] (value)}
			<button
				class="flex-1 rounded-lg py-1.5 text-xs font-semibold transition
					{mode === value ? 'bg-accent text-surface' : 'text-ink-dim'}"
				onclick={() => (mode = value as CaddieMode)}
			>
				{label}
			</button>
		{/each}
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

<!-- Zone sheets (detail mode) -->
{#if zoneSheet}
	<div class="fixed inset-x-0 bottom-0 z-50 mx-auto max-w-md rounded-t-2xl border-t border-edge bg-card/95 p-4 pb-24 backdrop-blur">
		{#if zoneSheet.step === 'landing'}
			<div class="flex items-center justify-between">
				<div>
					<p class="text-xs text-ink-dim">From {ZONE_LABELS[startZone] ?? startZone}</p>
					<p class="text-base font-bold">Where did throw {detailThrows.length + 1} land?</p>
				</div>
				<button class="p-1 text-ink-dim" onclick={() => (zoneSheet = null)} aria-label="Close">✕</button>
			</div>
			<div class="mt-3 space-y-1.5">
				{#each [['basket', '🧺 Basket'], ['c1', '◎ Circle 1 (0–33 ft)'], ['c2', '◎ Circle 2 (33–66 ft)'], ['fairway', '⬆ Fairway'], ['off_fairway', '✕ Off the fairway'], ['ob', '⚠ OB']] as [zone, label] (zone)}
					<button
						class="flex w-full items-center justify-between rounded-xl border border-edge bg-card-raised px-4 py-3 text-left text-sm font-semibold transition active:scale-[0.98] disabled:opacity-50
							{zone === 'ob' ? 'text-red-300' : ''}"
						onclick={() => pickLandingZone(zone as Zone)}
						disabled={savingZone}
					>
						{label}
						<span class="text-ink-dim">›</span>
					</button>
				{/each}
			</div>
		{:else if zoneSheet.step === 'drop'}
			<div class="flex items-center justify-between">
				<div>
					<p class="text-xs text-red-300">OB — penalty stroke added</p>
					<p class="text-base font-bold">Select penalty / drop location</p>
				</div>
				<button class="p-1 text-ink-dim" onclick={() => (zoneSheet = null)} aria-label="Close">✕</button>
			</div>
			<div class="mt-3 space-y-1.5">
				{#each [['c1', '◎ Circle 1 (0–33 ft)'], ['c2', '◎ Circle 2 (33–66 ft)'], ['fairway', '⬆ Fairway'], ['off_fairway', '✕ Off the fairway'], ['tee_pad', '▭ Tee pad']] as [drop, label] (drop)}
					<button
						class="flex w-full items-center justify-between rounded-xl border border-edge bg-card-raised px-4 py-3 text-left text-sm font-semibold transition active:scale-[0.98] disabled:opacity-50"
						onclick={() => commitZoneThrow('ob', drop as DropZone)}
						disabled={savingZone}
					>
						{label}
						<span class="text-ink-dim">›</span>
					</button>
				{/each}
			</div>
		{:else if zoneSheet.step === 'putt'}
			<div class="flex items-center justify-between">
				<div>
					<p class="text-xs text-ink-dim">Holed from {ZONE_LABELS[startZone]}</p>
					<p class="text-base font-bold">Select putt distance</p>
				</div>
				<button class="p-1 text-ink-dim" onclick={() => (zoneSheet = null)} aria-label="Close">✕</button>
			</div>
			<div class="mt-3 grid grid-cols-3 gap-2">
				{#each puttBands as band (band.mid)}
					<button
						class="rounded-xl border border-edge bg-card-raised py-8 text-sm font-bold text-sky-300 transition active:scale-95 disabled:opacity-50"
						onclick={() => commitZoneThrow('basket', undefined, band.mid)}
						disabled={savingZone}
					>
						{band.label}
					</button>
				{/each}
			</div>
		{/if}
	</div>
{/if}

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
