// Curved ground track for a recommended throw. Same three-phase flight model
// as the engine's shape vocabulary: straight high-speed launch, aerodynamic
// turn mid-flight, low-speed fade at the end. Deterministic — a drawing of
// the named shape fitted to the throw's endpoints, not a physics simulation.
const LAT_FT = 364000; // feet per degree of latitude (matches geo.ts / backend)

// Per-shape template: [release angle, turn strength, fade strength] in the
// thrower's frame (+x = turn side). Tuned to read like real flight charts.
const SHAPES: Record<string, [number, number, number]> = {
	straight: [0, 0.25, 0.45],
	hyzer: [-0.22, 0, 1.1],
	spike_hyzer: [-0.35, 0, 2.6],
	hyzer_flip: [-0.3, 0.82, 0.5],
	anhyzer: [0.3, 0.55, 0.5],
	turnover: [0, 1.05, 0.55],
	flex: [0.35, 0.5, 2.6]
};

/** RHBH and LHFH finish left; RHFH and LHBH finish right (mirrors backend). */
export function styleFinishesLeft(hand: string, style: string): boolean {
	return (hand === 'right') === (style === 'backhand');
}

/**
 * [lng, lat] polyline from start to target, bowed by the shot shape and
 * mirrored for the throw style. First point is exactly the start, last is
 * exactly the target (similarity transform of the unit-space track).
 * Hand defaults to right; the profile's hand isn't plumbed to the map yet.
 */
export function flightGroundTrack(
	startLat: number,
	startLng: number,
	targetLat: number,
	targetLng: number,
	shape: string,
	style: string,
	hand = 'right',
	n = 24
): [number, number][] {
	const [release, turn, fade] = SHAPES[shape] ?? SHAPES.straight;
	// unit-space track: +x is the thrower's turn side; mirror when the style
	// finishes right so fade pulls the correct way on the map
	const mirror = styleFinishesLeft(hand, style) ? 1 : -1;
	const xs: number[] = [0];
	const ys: number[] = [0];
	let heading = release;
	let x = 0;
	let y = 0;
	for (let i = 1; i < n; i++) {
		const t = i / (n - 1);
		const turnRate = turn * Math.exp(-(((t - 0.45) / 0.16) ** 2));
		const f = Math.max(0, (t - 0.6) / 0.4);
		heading += ((turnRate - fade * f * f) * 3.2) / n;
		x += Math.sin(heading) / n;
		y += Math.cos(heading) / n;
		xs.push(x);
		ys.push(y);
	}
	// similarity transform (rotate + scale) taking the track's end onto the
	// real chord, in a local feet frame anchored at the start
	const lngFt = LAT_FT * Math.cos((startLat * Math.PI) / 180);
	const cx = (targetLng - startLng) * lngFt;
	const cy = (targetLat - startLat) * LAT_FT;
	const ex = xs[n - 1] * mirror;
	const ey = ys[n - 1];
	const d2 = ex * ex + ey * ey || 1;
	const a = (ex * cx + ey * cy) / d2;
	const b = (ex * cy - ey * cx) / d2;
	return xs.map((xi, i) => {
		const px = xi * mirror;
		const py = ys[i];
		const fx = a * px - b * py;
		const fy = b * px + a * py;
		return [startLng + fx / lngFt, startLat + fy / LAT_FT];
	});
}
