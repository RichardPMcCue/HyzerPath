type Pt = { lat: number; lng: number };

/** Distance in feet from a point to a segment (local planar projection). */
function pointToSegmentFeet(p: Pt, a: Pt, b: Pt): number {
	const latFt = 364000;
	const lonFt = 364000 * Math.cos((p.lat * Math.PI) / 180);
	const px = (p.lng - a.lng) * lonFt;
	const py = (p.lat - a.lat) * latFt;
	const dx = (b.lng - a.lng) * lonFt;
	const dy = (b.lat - a.lat) * latFt;
	const len2 = dx * dx + dy * dy;
	if (len2 === 0) return Math.hypot(px, py);
	const t = Math.max(0, Math.min(1, (px * dx + py * dy) / len2));
	return Math.hypot(t * dx - px, t * dy - py);
}

export const FAIRWAY_FIT_TOLERANCE_FT = 40;
export const SMOOTHING_MIN_POINTS = 6; // keep in sync with backend utils.py

/** Single-pass weighted moving average (0.25 prev / 0.5 self / 0.25 next)
 *  on interior points; endpoints fixed. Corridor-outline taps zigzag laterally
 *  and average out to the centerline. Skipped for sparse chains
 *  (< SMOOTHING_MIN_POINTS) so deliberately placed dogleg corners survive. */
function smoothChain(points: Pt[]): Pt[] {
	if (points.length < SMOOTHING_MIN_POINTS) return [...points];
	const out: Pt[] = [points[0]];
	for (let i = 1; i < points.length - 1; i++) {
		const p = points[i - 1];
		const c = points[i];
		const n = points[i + 1];
		out.push({
			lat: 0.25 * p.lat + 0.5 * c.lat + 0.25 * n.lat,
			lng: 0.25 * p.lng + 0.5 * c.lng + 0.25 * n.lng
		});
	}
	out.push(points[points.length - 1]);
	return out;
}

/** Douglas-Peucker: drop points within tolerance of the line so distance
 *  follows the best-fit fairway line, not every lateral waypoint tap. */
function simplifyChain<T extends Pt>(
	points: T[],
	toleranceFt: number = FAIRWAY_FIT_TOLERANCE_FT
): T[] {
	if (points.length < 3) return [...points];
	const a = points[0];
	const b = points[points.length - 1];
	let maxIdx = 0;
	let maxDev = 0;
	for (let i = 1; i < points.length - 1; i++) {
		const dev = pointToSegmentFeet(points[i], a, b);
		if (dev > maxDev) {
			maxIdx = i;
			maxDev = dev;
		}
	}
	if (maxDev <= toleranceFt) return [a, b];
	const left = simplifyChain(points.slice(0, maxIdx + 1), toleranceFt);
	const right = simplifyChain(points.slice(maxIdx), toleranceFt);
	return [...left.slice(0, -1), ...right];
}

/** Length in feet of the best-fit line through a chain of points. */
export function chainDistanceFeet(points: Pt[], toleranceFt?: number): number {
	const simplified = simplifyChain(smoothChain(points), toleranceFt);
	let total = 0;
	for (let i = 0; i < simplified.length - 1; i++) {
		total += haversineFeet(
			simplified[i].lat,
			simplified[i].lng,
			simplified[i + 1].lat,
			simplified[i + 1].lng
		);
	}
	return total;
}

/**
 * Order fairway waypoints into the best-fit chain from tee to pin so the
 * corridor never doubles back, regardless of the order they were tapped.
 * Cheapest-insertion: repeatedly insert the point that adds the least length.
 * Without a pin yet, falls back to a nearest-neighbor walk from the tee.
 */
export function orderFairwayWaypoints<T extends Pt>(tee: Pt, waypoints: T[], pin: Pt | null): T[] {
	if (waypoints.length < 2) return [...waypoints];
	const d = (a: Pt, b: Pt) => haversineFeet(a.lat, a.lng, b.lat, b.lng);

	if (!pin) {
		const rest = [...waypoints];
		const out: T[] = [];
		let cursor: Pt = tee;
		while (rest.length) {
			let best = 0;
			for (let i = 1; i < rest.length; i++) {
				if (d(cursor, rest[i]) < d(cursor, rest[best])) best = i;
			}
			const next = rest.splice(best, 1)[0];
			out.push(next);
			cursor = next;
		}
		return out;
	}

	const path: (Pt | T)[] = [tee, pin];
	const rest = [...waypoints];
	while (rest.length) {
		let bestCost = Infinity;
		let bestPathIdx = 0;
		let bestRestIdx = 0;
		for (let r = 0; r < rest.length; r++) {
			for (let i = 0; i < path.length - 1; i++) {
				const cost = d(path[i], rest[r]) + d(rest[r], path[i + 1]) - d(path[i], path[i + 1]);
				if (cost < bestCost) {
					bestCost = cost;
					bestPathIdx = i;
					bestRestIdx = r;
				}
			}
		}
		path.splice(bestPathIdx + 1, 0, rest.splice(bestRestIdx, 1)[0]);
	}
	return path.slice(1, -1) as T[];
}

/** Great-circle distance in feet between two lat/lng points. */
export function haversineFeet(
	lat1: number,
	lng1: number,
	lat2: number,
	lng2: number
): number {
	const R = 20902231; // earth radius in feet
	const toRad = (d: number) => (d * Math.PI) / 180;
	const dLat = toRad(lat2 - lat1);
	const dLng = toRad(lng2 - lng1);
	const a =
		Math.sin(dLat / 2) ** 2 +
		Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
	return 2 * R * Math.asin(Math.sqrt(a));
}
