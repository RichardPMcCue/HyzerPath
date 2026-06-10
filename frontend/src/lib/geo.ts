type Pt = { lat: number; lng: number };

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
