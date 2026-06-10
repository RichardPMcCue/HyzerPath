<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth } from '$lib/auth.svelte';
	import { api } from '$lib/api';
	import type { Course, Hand, Round, ThrowStyleRow } from '$lib/types';

	interface TokenPayload {
		user_id: number;
		exp: number;
	}

	function decodeToken(): TokenPayload | null {
		if (!auth.token) return null;
		try {
			return JSON.parse(atob(auth.token.split('.')[1]));
		} catch {
			return null;
		}
	}

	const payload = decodeToken();

	let rounds = $state<Round[]>([]);
	let courses = $state<Map<number, Course>>(new Map());
	let discCount = $state<number | null>(null);

	let username = $state('');
	let usernameLoaded = $state(false);
	let savingName = $state(false);
	let nameError = $state<string | null>(null);
	let nameSaved = $state(false);

	// Prefill once the layout's getMe() resolves
	$effect(() => {
		if (!usernameLoaded && auth.user) {
			username = auth.user.username ?? '';
			usernameLoaded = true;
		}
	});

	const usernameDirty = $derived(
		usernameLoaded && username.trim() !== (auth.user?.username ?? '') && username.trim().length > 0
	);

	async function saveUsername() {
		savingName = true;
		nameError = null;
		nameSaved = false;
		try {
			const me = await api.updateMe({ username: username.trim() });
			auth.setUser(me);
			nameSaved = true;
			setTimeout(() => (nameSaved = false), 2000);
		} catch (e) {
			nameError = (e as Error).message;
		} finally {
			savingName = false;
		}
	}

	$effect(() => {
		Promise.all([api.listRounds(), api.getCourses()])
			.then(([r, c]) => {
				rounds = r;
				courses = new Map(c.map((course) => [course.course_id, course]));
			})
			.catch(() => {});
		api
			.getDiscs()
			.then((d) => (discCount = d.length))
			.catch(() => {});
	});

	const finished = $derived(rounds.filter((r) => r.total_score !== null));

	function relativeScore(round: Round): number {
		const course = courses.get(round.course_id);
		if (!course) return 0;
		const parByHole = new Map(course.holes.map((h) => [h.hole_id, h.par]));
		return round.round_holes.reduce(
			(rel, rh) => (rh.score > 0 ? rel + rh.score - (parByHole.get(rh.hole_id) ?? 3) : rel),
			0
		);
	}

	const LAYOUT_LABELS: Record<string, string> = {
		full: 'Full course',
		front9: 'Front 9',
		back9: 'Back 9'
	};

	// Best round = lowest score relative to par
	const bestRound = $derived.by(() => {
		if (finished.length === 0 || courses.size === 0) return null;
		let best: { round: Round; rel: number } | null = null;
		for (const round of finished) {
			const rel = relativeScore(round);
			if (best === null || rel < best.rel) best = { round, rel };
		}
		return best;
	});

	const relLabel = (rel: number) => (rel === 0 ? 'E' : rel > 0 ? `+${rel}` : `${rel}`);

	// --- Throw style profile: which styles the caddie may recommend ---
	let bhOn = $state(true);
	let fhOn = $state(true);
	let bhHand = $state<Hand>('right');
	let fhHand = $state<Hand>('right');
	let pref = $state<'backhand' | 'equal' | 'forehand'>('backhand');
	let stylesLoaded = $state(false);
	let stylesSaving = $state(false);
	let stylesSaved = $state(false);
	let stylesError = $state<string | null>(null);

	$effect(() => {
		api
			.getThrowStyles()
			.then((rows) => {
				if (rows.length > 0) {
					const bh = rows.find((r) => r.throw_type === 'backhand');
					const fh = rows.find((r) => r.throw_type === 'forehand');
					bhOn = !!bh;
					fhOn = !!fh;
					if (bh) bhHand = bh.hand;
					if (fh) fhHand = fh.hand;
					if (bh && fh) {
						pref = bh.priority === fh.priority ? 'equal' : bh.priority < fh.priority ? 'backhand' : 'forehand';
					}
				}
				stylesLoaded = true;
			})
			.catch(() => (stylesLoaded = true));
	});

	async function saveStyles() {
		if (!bhOn && !fhOn) {
			stylesError = 'Enable at least one throw style';
			return;
		}
		stylesSaving = true;
		stylesError = null;
		stylesSaved = false;
		try {
			const rows: ThrowStyleRow[] = [];
			if (bhOn) {
				rows.push({
					throw_type: 'backhand',
					hand: bhHand,
					priority: pref === 'forehand' ? 2 : 1
				});
			}
			if (fhOn) {
				rows.push({
					throw_type: 'forehand',
					hand: fhHand,
					priority: pref === 'backhand' ? 2 : 1
				});
			}
			await api.setThrowStyles(rows);
			stylesSaved = true;
			setTimeout(() => (stylesSaved = false), 2000);
		} catch (e) {
			stylesError = (e as Error).message;
		} finally {
			stylesSaving = false;
		}
	}

	function logout() {
		auth.logout();
		goto('/login');
	}
</script>

<header class="px-4 pt-6 pb-3">
	<h1 class="text-2xl font-bold">Profile</h1>
</header>

<main class="space-y-4 px-4 pt-2">
	<div class="rounded-2xl border border-edge bg-card p-4">
		<div class="flex items-center justify-between">
			<p class="text-xs tracking-wide text-ink-dim uppercase">Signed in</p>
			{#if auth.isAdmin}
				<span class="rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-bold tracking-wide text-accent uppercase">
					Admin
				</span>
			{/if}
		</div>
		<div class="mt-2 flex gap-2">
			<input
				type="text"
				placeholder={auth.user?.name ?? 'Username'}
				bind:value={username}
				maxlength="30"
				class="min-w-0 flex-1 rounded-xl border border-edge bg-card-raised px-3 py-2 text-sm font-semibold placeholder:font-normal placeholder:text-ink-dim focus:border-accent focus:outline-none"
			/>
			{#if usernameDirty}
				<button
					class="rounded-xl bg-accent px-3.5 py-2 text-sm font-bold text-surface transition active:scale-95 disabled:opacity-50"
					onclick={saveUsername}
					disabled={savingName}
				>
					{savingName ? '…' : 'Save'}
				</button>
			{:else if nameSaved}
				<span class="flex items-center px-2 text-sm text-accent">✓</span>
			{/if}
		</div>
		{#if nameError}
			<p class="mt-1.5 text-xs text-red-400">{nameError}</p>
		{/if}
		<p class="mt-2 text-xs text-ink-dim">
			User #{auth.user?.user_id ?? payload?.user_id ?? '?'}
			{#if auth.user?.email}· {auth.user.email}{/if}
		</p>
		{#if payload}
			<p class="mt-0.5 text-xs text-ink-dim">
				Session expires {new Date(payload.exp * 1000).toLocaleDateString()}
			</p>
		{/if}
	</div>

	<!-- Lifetime stats -->
	<div class="grid grid-cols-2 gap-3">
		<div class="rounded-2xl border border-edge bg-card p-4 text-center">
			<p class="text-2xl font-bold text-accent">{finished.length}</p>
			<p class="text-xs text-ink-dim">rounds played</p>
		</div>
		<div class="rounded-2xl border border-edge bg-card p-4 text-center">
			<p class="text-2xl font-bold text-accent">{discCount ?? '–'}</p>
			<p class="text-xs text-ink-dim">discs bagged</p>
		</div>
	</div>
	<div class="rounded-2xl border border-edge bg-card p-4">
		<p class="text-xs tracking-wide text-ink-dim uppercase">Best round</p>
		{#if bestRound}
			<div class="mt-1 flex items-baseline gap-2">
				<p class="text-2xl font-bold {bestRound.rel > 0 ? 'text-amber-300' : 'text-accent'}">
					{relLabel(bestRound.rel)}
					<span class="text-base font-semibold text-ink-dim">({bestRound.round.total_score})</span>
				</p>
			</div>
			<p class="mt-0.5 text-xs text-ink-dim">
				{courses.get(bestRound.round.course_id)?.name ?? `Course ${bestRound.round.course_id}`}
				· {LAYOUT_LABELS[bestRound.round.layout] ?? bestRound.round.layout}
				· {new Date(bestRound.round.played_at).toLocaleDateString(undefined, {
					month: 'short',
					day: 'numeric',
					year: 'numeric'
				})}
			</p>
		{:else}
			<p class="mt-1 text-sm text-ink-dim">Finish a round to set one.</p>
		{/if}
	</div>

	<!-- Throw style profile -->
	<div class="rounded-2xl border border-edge bg-card p-4">
		<p class="text-xs tracking-wide text-ink-dim uppercase">Throw styles</p>
		{#if stylesLoaded}
			<div class="mt-3 space-y-2.5">
				{#each [['backhand', 'Backhand'], ['forehand', 'Forehand']] as [style, label] (style)}
					{@const on = style === 'backhand' ? bhOn : fhOn}
					{@const hand = style === 'backhand' ? bhHand : fhHand}
					<div class="flex items-center justify-between gap-2">
						<button
							class="flex items-center gap-2.5"
							onclick={() => {
								if (style === 'backhand') bhOn = !bhOn;
								else fhOn = !fhOn;
							}}
						>
							<span
								class="flex h-5 w-9 items-center rounded-full p-0.5 transition
									{on ? 'justify-end bg-accent' : 'justify-start bg-card-raised'}"
							>
								<span class="h-4 w-4 rounded-full bg-surface"></span>
							</span>
							<span class="text-sm font-semibold {on ? '' : 'text-ink-dim'}">{label}</span>
						</button>
						{#if on}
							<div class="flex gap-1 rounded-lg border border-edge p-0.5">
								{#each [['right', 'RH'], ['left', 'LH']] as [h, hLabel] (h)}
									<button
										class="rounded-md px-2.5 py-1 text-xs font-bold transition active:scale-95
											{hand === h ? 'bg-accent text-surface' : 'text-ink-dim'}"
										onclick={() => {
											if (style === 'backhand') bhHand = h as Hand;
											else fhHand = h as Hand;
										}}
									>
										{hLabel}
									</button>
								{/each}
							</div>
						{/if}
					</div>
				{/each}

				{#if bhOn && fhOn}
					<div>
						<p class="pt-1 text-xs text-ink-dim">Preference</p>
						<div class="mt-1.5 flex gap-1 rounded-lg border border-edge p-0.5">
							{#each [['backhand', 'BH first'], ['equal', 'Equal'], ['forehand', 'FH first']] as [v, label] (v)}
								<button
									class="flex-1 rounded-md py-1.5 text-xs font-bold transition active:scale-95
										{pref === v ? 'bg-accent text-surface' : 'text-ink-dim'}"
									onclick={() => (pref = v as typeof pref)}
								>
									{label}
								</button>
							{/each}
						</div>
					</div>
				{/if}

				{#if stylesError}
					<p class="text-xs text-red-400">{stylesError}</p>
				{/if}
				<button
					class="w-full rounded-xl bg-accent py-2.5 text-sm font-bold text-surface transition active:scale-[0.98] disabled:opacity-50"
					onclick={saveStyles}
					disabled={stylesSaving}
				>
					{stylesSaving ? 'Saving…' : stylesSaved ? '✓ Saved' : 'Save throw styles'}
				</button>
			</div>
		{:else}
			<div class="mt-3 h-24 animate-pulse rounded-xl bg-card-raised"></div>
		{/if}
	</div>

	{#if auth.isAdmin}
		<a
			href="/admin/users"
			class="flex items-center justify-between rounded-2xl border border-edge bg-card p-4 transition active:scale-[0.98]"
		>
			<div>
				<p class="text-sm font-semibold">Manage users</p>
				<p class="mt-0.5 text-xs text-ink-dim">Grant or revoke admin access</p>
			</div>
			<svg class="h-4 w-4 text-ink-dim" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
				<path stroke-linecap="round" stroke-linejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
			</svg>
		</a>
	{/if}

	<button
		class="w-full rounded-2xl border border-red-900/60 bg-red-950/40 py-3 text-sm font-semibold text-red-300 transition active:scale-[0.98]"
		onclick={logout}
	>
		Sign out
	</button>
</main>
