<script lang="ts">
	import { api } from '$lib/api';
	import type { Disc, DiscItResult, DiscStat, DiscType, ThrowStyle } from '$lib/types';
	import FlightNumbers from '$lib/components/FlightNumbers.svelte';
	import BagMatrix from '$lib/components/BagMatrix.svelte';

	let view = $state<'list' | 'matrix'>('list');
	let discs = $state<Disc[] | null>(null);
	// Keyed by `${disc_id}:${throw_style}` — BH and FH carry differently
	let stats = $state<Map<string, DiscStat>>(new Map());
	let error = $state<string | null>(null);

	// disc editor (distances + flight numbers + color)
	let editingDiscId = $state<number | null>(null);
	let editStyle = $state<ThrowStyle>('backhand');
	let editVals = $state<Record<ThrowStyle, { avg: string; max: string }>>({
		backhand: { avg: '', max: '' },
		forehand: { avg: '', max: '' }
	});
	let editSpeed = $state('');
	let editGlide = $state('');
	let editTurn = $state('');
	let editFade = $state('');
	let editColor = $state('#2a3832');
	let editType = $state<DiscType>('putter');
	let savingStat = $state(false);

	// add-disc flow
	let adding = $state(false);
	let query = $state('');
	let results = $state<DiscItResult[] | null>(null);
	let searching = $state(false);
	let saving = $state(false);
	let searchTimer: ReturnType<typeof setTimeout>;

	// manual disc entry (for discs not on DiscIt)
	let manual = $state(false);
	let manualVals = $state({
		name: '',
		manufacturer: '',
		disc_type: 'putter' as DiscType,
		speed: '',
		glide: '',
		turn: '',
		fade: ''
	});

	const DISC_TYPES: [DiscType, string][] = [
		['putter', 'Putter'],
		['midrange', 'Mid'],
		['fairway_driver', 'Fairway'],
		['distance_driver', 'Distance']
	];

	function loadBag() {
		api
			.getDiscs()
			.then((d) => (discs = d))
			.catch((e) => (error = e.message));
		api
			.getDiscStats()
			.then(
				(s) =>
					(stats = new Map(s.map((stat) => [`${stat.disc_id}:${stat.throw_style}`, stat])))
			)
			.catch(() => {});
	}

	function openEditor(disc: Disc) {
		if (editingDiscId === disc.disc_id) {
			editingDiscId = null;
			return;
		}
		for (const style of ['backhand', 'forehand'] as const) {
			const stat = stats.get(`${disc.disc_id}:${style}`);
			editVals[style] = {
				avg: stat ? String(stat.avg_distance) : '',
				max: stat?.max_distance ? String(stat.max_distance) : ''
			};
		}
		editStyle = 'backhand';
		editSpeed = disc.speed !== null ? String(disc.speed) : '';
		editGlide = disc.glide !== null ? String(disc.glide) : '';
		editTurn = disc.turn !== null ? String(disc.turn) : '';
		editFade = disc.fade !== null ? String(disc.fade) : '';
		editColor = disc.color || '#2a3832';
		editType = disc.disc_type ?? 'putter';
		editingDiscId = disc.disc_id;
	}

	async function saveDisc(discId: number) {
		savingStat = true;
		try {
			// Type + flight numbers + color
			await api.updateDisc(discId, {
				disc_type: editType,
				speed: editSpeed !== '' ? Number(editSpeed) : null,
				glide: editGlide !== '' ? Number(editGlide) : null,
				turn: editTurn !== '' ? Number(editTurn) : null,
				fade: editFade !== '' ? Number(editFade) : null,
				color: editColor
			});
			// Throw distances per style (optional)
			for (const style of ['backhand', 'forehand'] as const) {
				const avg = parseInt(editVals[style].avg, 10);
				if (avg > 0) {
					const max = parseInt(editVals[style].max, 10);
					const saved = await api.setDiscStat(discId, {
						avg_distance: avg,
						max_distance: max > 0 ? max : null,
						throw_style: style
					});
					stats = new Map(stats).set(`${discId}:${style}`, saved);
				}
			}
			editingDiscId = null;
			loadBag();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			savingStat = false;
		}
	}

	$effect(() => {
		loadBag();
	});

	function onQueryInput() {
		clearTimeout(searchTimer);
		if (query.trim().length < 2) {
			results = null;
			return;
		}
		searchTimer = setTimeout(async () => {
			searching = true;
			try {
				results = await api.searchDiscs(query.trim());
			} catch {
				results = [];
			} finally {
				searching = false;
			}
		}, 350);
	}

	async function addDisc(r: DiscItResult) {
		saving = true;
		try {
			await api.createDisc({
				name: r.name,
				manufacturer: r.brand,
				disc_type: r.disc_type,
				speed: Number(r.speed),
				glide: Number(r.glide),
				turn: Number(r.turn),
				fade: Number(r.fade)
			});
			adding = false;
			query = '';
			results = null;
			loadBag();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			saving = false;
		}
	}

	const manualValid = $derived(manualVals.name.trim().length > 0);

	async function addManualDisc() {
		if (!manualValid) return;
		saving = true;
		try {
			const num = (v: string) => (v.trim() !== '' ? Number(v) : null);
			await api.createDisc({
				name: manualVals.name.trim(),
				manufacturer: manualVals.manufacturer.trim(),
				disc_type: manualVals.disc_type,
				speed: num(manualVals.speed),
				glide: num(manualVals.glide),
				turn: num(manualVals.turn),
				fade: num(manualVals.fade)
			});
			manual = false;
			adding = false;
			query = '';
			results = null;
			manualVals = {
				name: '',
				manufacturer: '',
				disc_type: 'putter',
				speed: '',
				glide: '',
				turn: '',
				fade: ''
			};
			loadBag();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			saving = false;
		}
	}

	async function removeDisc(discId: number) {
		await api.deleteDisc(discId);
		loadBag();
	}

	const typeLabel: Record<string, string> = {
		putter: 'Putter',
		midrange: 'Midrange',
		fairway_driver: 'Fairway',
		distance_driver: 'Distance'
	};

	const grouped = $derived.by(() => {
		if (!discs) return [];
		const order = ['distance_driver', 'fairway_driver', 'midrange', 'putter'];
		return order
			.map((type) => ({
				type,
				label: typeLabel[type],
				discs: discs!.filter((d) => d.disc_type === type)
			}))
			.concat([
				{ type: 'other', label: 'Other', discs: discs!.filter((d) => !d.disc_type) }
			])
			.filter((g) => g.discs.length > 0);
	});
</script>

<header class="sticky top-0 z-30 bg-surface/95 px-4 pt-6 pb-3 backdrop-blur">
	<div class="flex items-center justify-between">
		<h1 class="text-2xl font-bold">My Bag</h1>
		<button
			class="rounded-xl bg-accent px-4 py-2 text-sm font-bold text-surface transition active:scale-95"
			onclick={() => {
				adding = !adding;
				if (!adding) manual = false;
			}}
		>
			{adding ? 'Done' : '+ Add disc'}
		</button>
	</div>
	{#if adding}
		{#if manual}
			<button
				class="mt-3 text-sm font-medium text-ink-dim transition active:scale-95"
				onclick={() => (manual = false)}
			>
				← Back to search
			</button>
		{:else}
			<input
				type="search"
				placeholder="Search any disc — e.g. Destroyer…"
				bind:value={query}
				oninput={onQueryInput}
				class="mt-3 w-full rounded-xl border border-edge bg-card px-4 py-2.5 text-sm placeholder:text-ink-dim focus:border-accent focus:outline-none"
			/>
			<button
				class="mt-2 text-xs font-medium text-accent transition active:scale-95"
				onclick={() => (manual = true)}
			>
				Can't find it? Enter disc details manually →
			</button>
		{/if}
	{:else}
		<div class="mt-3 flex rounded-xl border border-edge bg-card p-1">
			{#each [['list', 'List'], ['matrix', 'Matrix']] as [value, label] (value)}
				<button
					class="flex-1 rounded-lg py-1.5 text-xs font-semibold transition
						{view === value ? 'bg-accent text-surface' : 'text-ink-dim'}"
					onclick={() => (view = value as 'list' | 'matrix')}
				>
					{label}
				</button>
			{/each}
		</div>
	{/if}
</header>

<main class="px-4 pt-2">
	{#if adding && manual}
		<div class="space-y-3 pt-3">
			<div class="flex gap-2">
				<label class="flex-1 text-xs text-ink-dim">
					Name
					<input
						type="text"
						bind:value={manualVals.name}
						placeholder="e.g. Zone OS"
						class="mt-1 w-full rounded-lg border border-edge bg-card-raised px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
					/>
				</label>
				<label class="flex-1 text-xs text-ink-dim">
					Manufacturer
					<input
						type="text"
						bind:value={manualVals.manufacturer}
						placeholder="e.g. Discraft"
						class="mt-1 w-full rounded-lg border border-edge bg-card-raised px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
					/>
				</label>
			</div>
			<div>
				<p class="text-xs text-ink-dim">Type</p>
				<div class="mt-1 flex gap-1 rounded-lg border border-edge p-0.5">
					{#each DISC_TYPES as [value, label] (value)}
						<button
							class="flex-1 rounded-md py-1.5 text-xs font-bold transition active:scale-95
								{manualVals.disc_type === value ? 'bg-accent text-surface' : 'text-ink-dim'}"
							onclick={() => (manualVals.disc_type = value)}
						>
							{label}
						</button>
					{/each}
				</div>
			</div>
			<div class="flex gap-2">
				{#each [['speed', 'Speed'], ['glide', 'Glide'], ['turn', 'Turn'], ['fade', 'Fade']] as [key, label] (key)}
					<label class="flex-1 text-xs text-ink-dim">
						{label}
						<input
							type="number"
							step="0.5"
							bind:value={manualVals[key as 'speed' | 'glide' | 'turn' | 'fade']}
							class="mt-1 w-full rounded-lg border border-edge bg-card-raised px-2 py-2 text-center text-sm text-ink focus:border-accent focus:outline-none"
						/>
					</label>
				{/each}
			</div>
			<button
				class="w-full rounded-xl bg-accent py-2.5 text-sm font-bold text-surface transition active:scale-[0.98] disabled:opacity-50"
				onclick={addManualDisc}
				disabled={saving || !manualValid}
			>
				{saving ? 'Adding…' : 'Add disc'}
			</button>
		</div>
	{:else if adding}
		{#if searching}
			<p class="pt-4 text-center text-sm text-ink-dim">Searching…</p>
		{:else if results}
			<div class="space-y-2 pt-1">
				{#each results.slice(0, 12) as r (r.brand + r.name)}
					<button
						class="flex w-full items-center justify-between rounded-2xl border border-edge bg-card p-3.5 text-left transition active:scale-[0.98] disabled:opacity-50"
						onclick={() => addDisc(r)}
						disabled={saving}
					>
						<div>
							<p class="text-sm font-semibold">{r.name}</p>
							<p class="text-xs text-ink-dim">{r.brand} · {r.category}</p>
						</div>
						<FlightNumbers speed={r.speed} glide={r.glide} turn={r.turn} fade={r.fade} />
					</button>
				{/each}
				{#if results.length === 0}
					<p class="pt-4 text-center text-sm text-ink-dim">No discs found.</p>
				{/if}
			</div>
		{/if}
	{:else if error}
		<p class="rounded-xl bg-red-950/60 p-4 text-sm text-red-300">{error}</p>
	{:else if discs === null}
		<div class="space-y-3 pt-2">
			{#each Array(5) as _, i (i)}
				<div class="h-16 animate-pulse rounded-2xl bg-card"></div>
			{/each}
		</div>
	{:else if discs.length === 0}
		<div class="pt-16 text-center">
			<p class="text-4xl">🥏</p>
			<p class="mt-3 font-semibold">Your bag is empty</p>
			<p class="mt-1 text-sm text-ink-dim">Add discs so the caddie knows what you throw.</p>
		</div>
	{:else if view === 'matrix'}
		<div class="pt-2">
			<BagMatrix {discs} />
		</div>
	{:else}
		{#each grouped as group (group.type)}
			<h2 class="px-1 pt-4 pb-2 text-xs font-semibold tracking-wide text-ink-dim uppercase">
				{group.label}
			</h2>
			<div class="space-y-2">
				{#each group.discs as disc (disc.disc_id)}
					{@const bh = stats.get(`${disc.disc_id}:backhand`)}
					{@const fh = stats.get(`${disc.disc_id}:forehand`)}
					<div class="rounded-2xl border border-edge bg-card">
						<button class="flex w-full items-center justify-between p-3.5 text-left" onclick={() => openEditor(disc)}>
							<div class="flex items-center gap-3">
								<span
									class="h-9 w-9 shrink-0 rounded-full border-2 border-edge"
									style="background:{disc.color || '#2a3832'}"
								></span>
								<div>
									<p class="text-sm font-semibold">{disc.name}</p>
									<p class="text-xs text-ink-dim">{disc.manufacturer}</p>
									{#if bh || fh}
										<p class="text-xs font-medium text-accent">
											{[
												bh && `BH ${bh.avg_distance}${bh.max_distance ? `/${bh.max_distance}` : ''} ft`,
												fh && `FH ${fh.avg_distance}${fh.max_distance ? `/${fh.max_distance}` : ''} ft`
											]
												.filter(Boolean)
												.join(' · ')}
										</p>
									{:else}
										<p class="text-xs font-medium text-amber-300">Set throw distance →</p>
									{/if}
								</div>
							</div>
							<FlightNumbers
								speed={disc.speed}
								glide={disc.glide}
								turn={disc.turn}
								fade={disc.fade}
							/>
						</button>
						{#if editingDiscId === disc.disc_id}
							<div class="border-t border-edge p-3.5">
								<p class="mb-1 text-xs text-ink-dim">Disc type</p>
								<div class="mb-3 flex gap-1 rounded-lg border border-edge p-0.5">
									{#each DISC_TYPES as [value, label] (value)}
										<button
											class="flex-1 rounded-md py-1.5 text-xs font-bold transition active:scale-95
												{editType === value ? 'bg-accent text-surface' : 'text-ink-dim'}"
											onclick={() => (editType = value)}
										>
											{label}
										</button>
									{/each}
								</div>
								<div class="flex gap-1 rounded-lg border border-edge p-0.5">
									{#each [['backhand', 'Backhand'], ['forehand', 'Forehand']] as [style, label] (style)}
										<button
											class="flex-1 rounded-md py-1.5 text-xs font-bold transition active:scale-95
												{editStyle === style ? 'bg-accent text-surface' : 'text-ink-dim'}"
											onclick={() => (editStyle = style as ThrowStyle)}
										>
											{label}
										</button>
									{/each}
								</div>
								<div class="mt-2 flex gap-2">
									<label class="flex-1 text-xs text-ink-dim">
										Avg distance (ft)
										<input
											type="number"
											inputmode="numeric"
											bind:value={editVals[editStyle].avg}
											placeholder="300"
											class="mt-1 w-full rounded-lg border border-edge bg-card-raised px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
										/>
									</label>
									<label class="flex-1 text-xs text-ink-dim">
										Max distance (ft)
										<input
											type="number"
											inputmode="numeric"
											bind:value={editVals[editStyle].max}
											placeholder="optional"
											class="mt-1 w-full rounded-lg border border-edge bg-card-raised px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none"
										/>
									</label>
								</div>
								<div class="mt-2 flex items-end gap-2">
									<label class="flex-1 text-xs text-ink-dim">
										Speed
										<input type="number" step="0.5" bind:value={editSpeed}
											class="mt-1 w-full rounded-lg border border-edge bg-card-raised px-2 py-2 text-center text-sm text-ink focus:border-accent focus:outline-none" />
									</label>
									<label class="flex-1 text-xs text-ink-dim">
										Glide
										<input type="number" step="0.5" bind:value={editGlide}
											class="mt-1 w-full rounded-lg border border-edge bg-card-raised px-2 py-2 text-center text-sm text-ink focus:border-accent focus:outline-none" />
									</label>
									<label class="flex-1 text-xs text-ink-dim">
										Turn
										<input type="number" step="0.5" bind:value={editTurn}
											class="mt-1 w-full rounded-lg border border-edge bg-card-raised px-2 py-2 text-center text-sm text-ink focus:border-accent focus:outline-none" />
									</label>
									<label class="flex-1 text-xs text-ink-dim">
										Fade
										<input type="number" step="0.5" bind:value={editFade}
											class="mt-1 w-full rounded-lg border border-edge bg-card-raised px-2 py-2 text-center text-sm text-ink focus:border-accent focus:outline-none" />
									</label>
									<label class="text-xs text-ink-dim">
										Color
										<input
											type="color"
											bind:value={editColor}
											class="mt-1 block h-9 w-12 cursor-pointer rounded-lg border border-edge bg-card-raised"
										/>
									</label>
								</div>
								<div class="mt-3 flex items-center justify-between">
									<button
										class="text-xs font-medium text-red-400"
										onclick={() => removeDisc(disc.disc_id)}
									>
										Remove from bag
									</button>
									<button
										class="rounded-lg bg-accent px-4 py-2 text-xs font-bold text-surface transition active:scale-95 disabled:opacity-50"
										disabled={savingStat}
										onclick={() => saveDisc(disc.disc_id)}
									>
										{savingStat ? 'Saving…' : 'Save'}
									</button>
								</div>
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/each}
	{/if}
</main>
