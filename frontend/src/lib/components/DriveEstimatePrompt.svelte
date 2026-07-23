<script lang="ts">
	import { api } from '$lib/api';
	import { auth } from '$lib/auth.svelte';

	// Shown once on first login (while estimated_drive_ft is null) to seed
	// default disc distances until the player measures real ones.
	// Typical best-drive per tier (a representative value, not a range edge —
	// clicking fills the exact field below so you can fine-tune).
	const TIERS = [
		{ label: 'Beginner', ft: 250, hint: '~250 ft' },
		{ label: 'Intermediate', ft: 350, hint: '~350 ft' },
		{ label: 'Advanced', ft: 425, hint: '~425 ft' },
		{ label: 'Pro', ft: 500, hint: '~500 ft' }
	];

	let value = $state(350);
	let saving = $state(false);

	async function save(ft: number) {
		if (saving) return;
		saving = true;
		try {
			const me = await api.updateMe({ estimated_drive_ft: ft });
			auth.setUser(me);
		} catch {
			// leave the prompt; a failed save keeps estimated_drive_ft null
			saving = false;
		}
	}
</script>

<div class="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-4 sm:items-center">
	<div class="w-full max-w-md rounded-2xl border border-edge bg-card p-5 shadow-xl">
		<h2 class="text-lg font-semibold text-ink">How far do you throw a driver?</h2>
		<p class="mt-1 text-sm text-ink-dim">
			Your best drive, roughly. We use it to estimate distances for discs you
			haven't measured yet — you can change it any time, and measuring a disc
			always overrides the estimate.
		</p>

		<div class="mt-4 grid grid-cols-2 gap-2">
			{#each TIERS as tier (tier.ft)}
				<button
					type="button"
					class="rounded-xl border px-3 py-3 text-left transition
						{value === tier.ft
						? 'border-accent bg-card-raised'
						: 'border-edge bg-surface hover:border-accent-dim'}"
					onclick={() => (value = tier.ft)}
				>
					<div class="font-medium text-ink">{tier.label}</div>
					<div class="text-xs text-ink-dim">{tier.hint}</div>
				</button>
			{/each}
		</div>

		<label class="mt-4 block text-sm text-ink-dim">
			Or set it exactly (ft)
			<input
				type="number"
				min="100"
				max="800"
				bind:value
				class="mt-1 w-full rounded-lg border border-edge bg-surface px-3 py-2 text-ink"
			/>
		</label>

		<div class="mt-5 flex gap-2">
			<button
				type="button"
				class="flex-1 rounded-xl bg-accent px-4 py-3 font-semibold text-surface disabled:opacity-60"
				disabled={saving || value < 100 || value > 800}
				onclick={() => save(value)}
			>
				{saving ? 'Saving…' : 'Save'}
			</button>
			<button
				type="button"
				class="rounded-xl border border-edge px-4 py-3 text-ink-dim"
				disabled={saving}
				onclick={() => save(350)}
			>
				Skip
			</button>
		</div>
	</div>
</div>
