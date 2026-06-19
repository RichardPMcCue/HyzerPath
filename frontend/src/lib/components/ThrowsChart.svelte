<script lang="ts">
	import { api } from '$lib/api';
	import type { Disc, ThrowMeasurement } from '$lib/types';
	import ThrowShareCard from './ThrowShareCard.svelte';

	interface ThrowRow {
		t: ThrowMeasurement;
		start: { lat: number; lng: number };
		discName: string;
		color: string;
	}

	let rows = $state<ThrowRow[] | null>(null);
	let error = $state<string | null>(null);
	let sort = $state<'newest' | 'furthest' | 'shortest'>('newest');
	let shareRow = $state<ThrowRow | null>(null);

	$effect(() => {
		Promise.all([api.getThrowSessions(), api.getDiscs()])
			.then(([sessions, discs]) => {
				const byId = new Map<number, Disc>(discs.map((d) => [d.disc_id, d]));
				const flat: ThrowRow[] = [];
				for (const s of sessions) {
					for (const t of s.throws) {
						const disc = t.disc_id != null ? byId.get(t.disc_id) : undefined;
						flat.push({
							t,
							start: { lat: s.start_latitude, lng: s.start_longitude },
							discName: disc?.name ?? 'No disc',
							color: disc?.color ?? '#34d399'
						});
					}
				}
				rows = flat;
			})
			.catch((e) => (error = e.message));
	});

	const sorted = $derived.by(() => {
		if (!rows) return [];
		const arr = [...rows];
		if (sort === 'furthest') arr.sort((a, b) => b.t.distance_ft - a.t.distance_ft);
		else if (sort === 'shortest') arr.sort((a, b) => a.t.distance_ft - b.t.distance_ft);
		else arr.sort((a, b) => new Date(b.t.created_at).getTime() - new Date(a.t.created_at).getTime());
		return arr;
	});

	const maxDist = $derived(
		rows && rows.length ? Math.max(...rows.map((r) => r.t.distance_ft)) : 1
	);

	function fmtDate(iso: string): string {
		return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
	}

	const SORTS: [typeof sort, string][] = [
		['newest', 'Newest'],
		['furthest', 'Furthest'],
		['shortest', 'Shortest']
	];

	async function deleteThrow(row: ThrowRow) {
		try {
			await api.deleteThrow(row.t.session_id, row.t.throw_id);
			rows = (rows ?? []).filter((r) => r.t.throw_id !== row.t.throw_id);
			shareRow = null;
		} catch (e) {
			error = (e as Error).message;
		}
	}
</script>

{#if error}
	<p class="rounded-xl bg-red-950/60 p-4 text-sm text-red-300">{error}</p>
{:else if rows === null}
	<div class="space-y-2">
		{#each Array(6) as _, i (i)}
			<div class="h-12 animate-pulse rounded-xl bg-card"></div>
		{/each}
	</div>
{:else if rows.length === 0}
	<div class="pt-12 text-center">
		<p class="text-4xl">🎯</p>
		<p class="mt-3 font-semibold">No throws yet</p>
		<p class="mt-1 text-sm text-ink-dim">Use the Measure tab to record throws.</p>
	</div>
{:else}
	<div class="flex gap-1 rounded-xl border border-edge bg-card p-1">
		{#each SORTS as [value, label] (value)}
			<button
				class="flex-1 rounded-lg py-1.5 text-xs font-semibold transition
					{sort === value ? 'bg-accent text-surface' : 'text-ink-dim'}"
				onclick={() => (sort = value)}
			>
				{label}
			</button>
		{/each}
	</div>

	<div class="mt-3 space-y-2">
		{#each sorted as row (row.t.throw_id)}
			<button
				class="relative block w-full overflow-hidden rounded-xl border border-edge bg-card text-left transition active:scale-[0.99]"
				onclick={() => (shareRow = row)}
			>
				<!-- distance bar -->
				<div
					class="absolute inset-y-0 left-0 opacity-20"
					style="width:{(row.t.distance_ft / maxDist) * 100}%;background:{row.color}"
				></div>
				<div class="relative flex items-center justify-between px-3 py-2.5">
					<div class="flex min-w-0 items-center gap-2.5">
						<span class="h-3 w-3 shrink-0 rounded-full" style="background:{row.color}"></span>
						<div class="min-w-0">
							<p class="truncate text-sm font-semibold">{row.discName}</p>
							<p class="text-[11px] text-ink-dim">
								{fmtDate(row.t.created_at)}{row.t.throw_style === 'forehand'
									? ' · FH'
									: row.t.throw_style === 'backhand'
										? ' · BH'
										: ''}
							</p>
						</div>
					</div>
					<div class="flex shrink-0 items-center gap-2">
						<span class="text-base font-bold text-accent">{Math.round(row.t.distance_ft)} ft</span>
						<svg
							class="h-4 w-4 text-ink-dim"
							fill="none"
							viewBox="0 0 24 24"
							stroke-width="2"
							stroke="currentColor"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="M7.217 10.907a2.25 2.25 0 1 0 0 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186 9.566-5.314m-9.566 7.5 9.566 5.314m0 0a2.25 2.25 0 1 0 3.935 2.186 2.25 2.25 0 0 0-3.935-2.186Zm0-12.814a2.25 2.25 0 1 0 3.933-2.185 2.25 2.25 0 0 0-3.933 2.185Z"
							/>
						</svg>
					</div>
				</div>
			</button>
		{/each}
	</div>
{/if}

{#if shareRow}
	<ThrowShareCard
		start={shareRow.start}
		end={{ lat: shareRow.t.end_latitude, lng: shareRow.t.end_longitude }}
		distanceFt={shareRow.t.distance_ft}
		discName={shareRow.discName}
		color={shareRow.color}
		throwStyle={shareRow.t.throw_style}
		createdAt={shareRow.t.created_at}
		onclose={() => (shareRow = null)}
		ondelete={() => shareRow && deleteThrow(shareRow)}
	/>
{/if}
