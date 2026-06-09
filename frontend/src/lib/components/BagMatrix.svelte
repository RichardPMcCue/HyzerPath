<script lang="ts">
	import type { Disc } from '$lib/types';

	let { discs }: { discs: Disc[] } = $props();

	// Y axis: speed, high at the top down to 1
	const speeds = Array.from({ length: 14 }, (_, i) => 14 - i);
	// X axis: combined stability (turn + fade), positive (overstable) on the
	// LEFT, negative (understable) on the RIGHT
	const stabilities = Array.from({ length: 11 }, (_, i) => 5 - i); // 5 .. -5

	function net(d: Disc): number {
		return (d.turn ?? 0) + (d.fade ?? 0);
	}

	function cell(speed: number, stability: number): Disc[] {
		return discs.filter(
			(d) => Math.round(d.speed ?? 0) === speed && Math.round(net(d)) === stability
		);
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

	// Only render speed rows from the fastest disc down to 1 (skip empty top)
	const maxSpeed = $derived(
		Math.min(14, Math.max(4, ...discs.map((d) => Math.round(d.speed ?? 0))))
	);
	const visibleSpeeds = $derived(speeds.filter((s) => s <= maxSpeed));
</script>

<div class="-mx-4 overflow-x-auto px-4">
	<div class="min-w-[560px]">
		<!-- Stability axis (top) -->
		<div class="grid grid-cols-[28px_repeat(11,1fr)] gap-0.5 pb-1">
			<span class="flex items-end justify-center pb-0.5 text-[9px] text-ink-dim">spd</span>
			{#each stabilities as s (s)}
				<span class="text-center text-[11px] font-bold text-ink-dim">
					{s > 0 ? `+${s}` : s}
				</span>
			{/each}
		</div>

		{#each visibleSpeeds as speed (speed)}
			<div class="grid grid-cols-[28px_repeat(11,1fr)] gap-0.5 pb-0.5">
				<span class="flex items-center justify-center text-[11px] font-bold text-ink-dim">
					{speed}
				</span>
				{#each stabilities as stability (stability)}
					{@const cellDiscs = cell(speed, stability)}
					<div
						class="flex min-h-9 flex-col items-stretch justify-center gap-0.5 rounded border p-0.5
							{cellDiscs.length > 0 ? 'border-edge bg-card' : 'border-edge/40 bg-card/40'}"
					>
						{#each cellDiscs as disc (disc.disc_id)}
							<span
								class="truncate rounded px-1 py-0.5 text-center text-[9px] font-bold leading-tight"
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

		<div class="grid grid-cols-[28px_repeat(11,1fr)] pt-1">
			<span></span>
			<span class="col-span-4 text-left text-[10px] text-ink-dim">← overstable</span>
			<span class="col-span-3 text-center text-[10px] text-ink-dim">turn + fade</span>
			<span class="col-span-4 text-right text-[10px] text-ink-dim">understable →</span>
		</div>
	</div>
</div>
