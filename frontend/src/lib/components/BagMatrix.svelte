<script lang="ts">
	import type { Disc } from '$lib/types';

	let { discs }: { discs: Disc[] } = $props();

	// Rows: speed bands (drivers at the top, like the classic bag matrix)
	const rows = [
		{ label: 'Distance', min: 10, max: 15 },
		{ label: 'Fairway', min: 7, max: 9.5 },
		{ label: 'Midrange', min: 4, max: 6.5 },
		{ label: 'Putters', min: 0, max: 3.5 }
	];

	// Columns: net stability (turn + fade), understable -> overstable
	const cols = [
		{ label: 'Very US', min: -Infinity, max: -2 },
		{ label: 'Understable', min: -2, max: -0.5 },
		{ label: 'Stable', min: -0.5, max: 1.5 },
		{ label: 'Overstable', min: 1.5, max: 3 },
		{ label: 'Very OS', min: 3, max: Infinity }
	];

	function net(d: Disc): number {
		return (d.turn ?? 0) + (d.fade ?? 0);
	}

	function cell(row: (typeof rows)[0], col: (typeof cols)[0]): Disc[] {
		return discs.filter((d) => {
			const s = d.speed ?? 0;
			const n = net(d);
			return s >= row.min && s <= row.max && n > col.min && n <= col.max;
		});
	}

	function textColor(bg: string | null): string {
		if (!bg) return '#e8f0ec';
		const hex = bg.replace('#', '');
		if (hex.length !== 6) return '#e8f0ec';
		const lum =
			0.299 * parseInt(hex.slice(0, 2), 16) +
			0.587 * parseInt(hex.slice(2, 4), 16) +
			0.114 * parseInt(hex.slice(4, 6), 16);
		return lum > 150 ? '#0c1210' : '#ffffff';
	}
</script>

<div class="-mx-4 overflow-x-auto px-4">
	<div class="min-w-[480px]">
		<!-- Column headers -->
		<div class="grid grid-cols-[64px_repeat(5,1fr)] gap-1 pb-1">
			<span></span>
			{#each cols as col (col.label)}
				<span class="text-center text-[10px] font-semibold tracking-wide text-ink-dim uppercase">
					{col.label}
				</span>
			{/each}
		</div>

		{#each rows as row (row.label)}
			<div class="grid grid-cols-[64px_repeat(5,1fr)] gap-1 pb-1">
				<span class="flex items-center text-[10px] font-semibold tracking-wide text-ink-dim uppercase">
					{row.label}
				</span>
				{#each cols as col (col.label)}
					{@const cellDiscs = cell(row, col)}
					<div
						class="flex min-h-14 flex-col items-stretch justify-center gap-1 rounded-lg border border-edge bg-card p-1"
					>
						{#each cellDiscs as disc (disc.disc_id)}
							<span
								class="truncate rounded px-1.5 py-0.5 text-center text-[10px] font-bold"
								style="background:{disc.color || '#2a3832'};color:{textColor(disc.color)}"
								title="{disc.manufacturer} {disc.name} · {disc.speed}/{disc.glide}/{disc.turn}/{disc.fade}"
							>
								{disc.name}
							</span>
						{/each}
					</div>
				{/each}
			</div>
		{/each}
	</div>
</div>
<p class="pt-1 text-center text-[10px] text-ink-dim">
	Columns: turn + fade (understable → overstable). Gaps show where your bag is missing coverage.
</p>
