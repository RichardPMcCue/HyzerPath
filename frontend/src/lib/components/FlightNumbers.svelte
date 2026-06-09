<script lang="ts">
	let {
		speed,
		glide,
		turn,
		fade
	}: {
		speed: number | string | null;
		glide: number | string | null;
		turn: number | string | null;
		fade: number | string | null;
	} = $props();

	const numbers = $derived([
		{ label: 'Speed', value: speed },
		{ label: 'Glide', value: glide },
		{ label: 'Turn', value: turn },
		{ label: 'Fade', value: fade }
	]);
</script>

<div class="flex gap-1.5">
	{#each numbers as n (n.label)}
		<span
			class="flex h-7 w-7 flex-col items-center justify-center rounded-md bg-card-raised text-[11px] font-bold"
			title={n.label}
		>
			{n.value ?? '–'}
		</span>
	{/each}
</div>
