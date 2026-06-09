<script lang="ts">
	import { api } from '$lib/api';
	import type { Disc, ThrowMeasurement, ThrowSession } from '$lib/types';

	let session = $state<ThrowSession | null>(null);
	let throws = $state<ThrowMeasurement[]>([]);
	let discs = $state<Disc[]>([]);
	let selectedDiscId = $state<number | null>(null);
	let error = $state<string | null>(null);
	let busy = $state<'start' | 'throw' | null>(null);
	let gpsAccuracy = $state<number | null>(null);

	$effect(() => {
		api
			.getDiscs()
			.then((d) => (discs = d))
			.catch(() => {});
	});

	function getPosition(): Promise<GeolocationPosition> {
		return new Promise((resolve, reject) => {
			if (!navigator.geolocation) {
				reject(new Error('GPS not available on this device'));
				return;
			}
			navigator.geolocation.getCurrentPosition(resolve, (e) => reject(new Error(e.message)), {
				enableHighAccuracy: true,
				timeout: 15000,
				maximumAge: 0
			});
		});
	}

	async function markStart() {
		busy = 'start';
		error = null;
		try {
			const pos = await getPosition();
			gpsAccuracy = pos.coords.accuracy * 3.28084;
			if (session && throws.length === 0) {
				// Re-mark before any throws: just move the existing start point
				session = await api.updateThrowSession(session.session_id, {
					start_latitude: pos.coords.latitude,
					start_longitude: pos.coords.longitude
				});
			} else {
				session = await api.createThrowSession({
					start_latitude: pos.coords.latitude,
					start_longitude: pos.coords.longitude
				});
				throws = [];
			}
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = null;
		}
	}

	async function markLanding() {
		if (!session) return;
		busy = 'throw';
		error = null;
		try {
			const pos = await getPosition();
			gpsAccuracy = pos.coords.accuracy * 3.28084;
			const throwRec = await api.recordThrow(session.session_id, {
				end_latitude: pos.coords.latitude,
				end_longitude: pos.coords.longitude,
				disc_id: selectedDiscId
			});
			throws = [throwRec, ...throws];
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = null;
		}
	}

	async function removeThrow(throwId: number) {
		if (!session) return;
		await api.deleteThrow(session.session_id, throwId);
		throws = throws.filter((t) => t.throw_id !== throwId);
	}

	function discName(discId: number | null): string {
		const disc = discs.find((d) => d.disc_id === discId);
		return disc ? disc.name : 'No disc';
	}
</script>

<header class="px-4 pt-6 pb-3">
	<h1 class="text-2xl font-bold">Measure Throws</h1>
	<p class="mt-1 text-xs text-ink-dim">
		Mark your start point once, then mark each landing spot. Tag a disc and your bag stats update
		automatically.
	</p>
</header>

<main class="space-y-4 px-4 pt-2">
	{#if error}
		<p class="rounded-xl bg-red-950/60 p-4 text-sm text-red-300">{error}</p>
	{/if}

	<!-- Disc selector -->
	{#if discs.length > 0}
		<div class="-mx-4 overflow-x-auto px-4">
			<div class="flex w-max gap-2">
				<button
					class="rounded-full border px-3.5 py-1.5 text-xs font-semibold whitespace-nowrap transition
						{selectedDiscId === null ? 'border-accent bg-accent/15 text-accent' : 'border-edge bg-card text-ink-dim'}"
					onclick={() => (selectedDiscId = null)}
				>
					No disc
				</button>
				{#each discs as disc (disc.disc_id)}
					<button
						class="rounded-full border px-3.5 py-1.5 text-xs font-semibold whitespace-nowrap transition
							{selectedDiscId === disc.disc_id
							? 'border-accent bg-accent/15 text-accent'
							: 'border-edge bg-card text-ink-dim'}"
						onclick={() => (selectedDiscId = disc.disc_id)}
					>
						{disc.name}
					</button>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Big action buttons -->
	<div class="grid grid-cols-2 gap-3">
		<button
			class="flex flex-col items-center gap-1 rounded-2xl border border-edge bg-card py-6 font-semibold transition active:scale-95 disabled:opacity-50"
			onclick={markStart}
			disabled={busy !== null}
		>
			<svg class="h-7 w-7 text-accent" fill="none" viewBox="0 0 24 24" stroke-width="1.7" stroke="currentColor">
				<path stroke-linecap="round" stroke-linejoin="round" d="M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
				<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z" />
			</svg>
			{busy === 'start' ? 'Locating…' : session ? 'New start point' : 'Mark start'}
		</button>
		<button
			class="flex flex-col items-center gap-1 rounded-2xl py-6 font-bold transition active:scale-95 disabled:opacity-40
				{session ? 'bg-accent text-surface' : 'border border-edge bg-card text-ink-dim'}"
			onclick={markLanding}
			disabled={!session || busy !== null}
		>
			<svg class="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke-width="1.7" stroke="currentColor">
				<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v6m3-3H9m12 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
			</svg>
			{busy === 'throw' ? 'Locating…' : 'Mark landing'}
		</button>
	</div>

	{#if session}
		<p class="text-center text-xs text-ink-dim">
			Start point set
			{#if gpsAccuracy}
				· GPS accuracy ±{Math.round(gpsAccuracy)} ft
			{/if}
		</p>
	{:else}
		<p class="text-center text-xs text-ink-dim">Stand where you'll throw from and mark start.</p>
	{/if}

	<!-- This session's throws -->
	{#if throws.length > 0}
		<h2 class="px-1 pt-2 text-xs font-semibold tracking-wide text-ink-dim uppercase">
			This session
		</h2>
		<div class="space-y-2">
			{#each throws as t (t.throw_id)}
				<div class="flex items-center justify-between rounded-2xl border border-edge bg-card p-3.5">
					<div>
						<p class="text-lg font-bold text-accent">{Math.round(t.distance_ft)} ft</p>
						<p class="text-xs text-ink-dim">{discName(t.disc_id)}</p>
					</div>
					<button
						class="p-1 text-ink-dim transition hover:text-red-400"
						onclick={() => removeThrow(t.throw_id)}
						aria-label="Delete throw"
					>
						<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
						</svg>
					</button>
				</div>
			{/each}
		</div>
	{/if}
</main>
