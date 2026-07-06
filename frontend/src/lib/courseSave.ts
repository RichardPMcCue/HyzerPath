import { api } from '$lib/api';
import { haversineFeet } from '$lib/geo';
import type { MapperHole } from '$lib/types';

function ring(h: MapperHole): [number, number][] | undefined {
	return h.fairway.length >= 3 ? h.fairway.map((p) => [p.lat, p.lng]) : undefined;
}

/** Persist a fully placed mapper hole: hole (with its fairway polygon),
 *  tee/basket nodes, and any drawn hazard areas. The server derives the
 *  playing line and the real distance from the polygon. */
export async function createMappedHole(courseId: number, h: MapperHole): Promise<void> {
	if (!h.tee || !h.pin) return;
	const hole = await api.createHole(courseId, {
		hole_number: h.holeNumber,
		par: h.par,
		// straight-line estimate; the server recomputes from the routed line
		distance: Math.round(haversineFeet(h.tee.lat, h.tee.lng, h.pin.lat, h.pin.lng)),
		elevation: 0,
		fairway_polygon: ring(h)
	});
	await api.createHoleNode(courseId, hole.hole_id, {
		node_type: 'tee',
		sequence: 0,
		label: 'Tee',
		latitude: h.tee.lat,
		longitude: h.tee.lng,
		is_fairway: true
	});
	await api.createHoleNode(courseId, hole.hole_id, {
		node_type: 'basket',
		sequence: 1,
		label: 'Basket',
		latitude: h.pin.lat,
		longitude: h.pin.lng,
		is_fairway: true
	});
	// Nodes landed after the polygon: re-send it so the server can route
	// tee→basket and store the real played distance
	if (ring(h)) {
		await api.updateHole(courseId, hole.hole_id, { fairway_polygon: ring(h) });
	}
	for (const hz of h.hazards) {
		await api.createHoleHazard(courseId, hole.hole_id, {
			hazard_type: hz.hazard_type,
			polygon: hz.polygon.map((p) => [p.lat, p.lng])
		});
	}
}

/** Sync an existing hole's structure: marker moves, fairway polygon edits,
 *  par, and hazard changes. */
export async function saveMappedHoleChanges(courseId: number, h: MapperHole): Promise<void> {
	if (!h.holeId) return;

	if (h.teeMoved && h.tee) {
		if (h.teeNodeId) {
			await api.updateHoleNode(courseId, h.holeId, h.teeNodeId, {
				latitude: h.tee.lat,
				longitude: h.tee.lng
			});
		} else {
			const node = await api.createHoleNode(courseId, h.holeId, {
				node_type: 'tee',
				sequence: 0,
				label: 'Tee',
				latitude: h.tee.lat,
				longitude: h.tee.lng,
				is_fairway: true
			});
			h.teeNodeId = node.hole_node_id;
		}
	}
	if (h.pinMoved && h.pin) {
		if (h.pinNodeId) {
			await api.updateHoleNode(courseId, h.holeId, h.pinNodeId, {
				latitude: h.pin.lat,
				longitude: h.pin.lng
			});
		} else {
			const node = await api.createHoleNode(courseId, h.holeId, {
				node_type: 'basket',
				sequence: 1,
				label: 'Basket',
				latitude: h.pin.lat,
				longitude: h.pin.lng,
				is_fairway: true
			});
			h.pinNodeId = node.hole_node_id;
		}
	}

	if (h.fairwayChanged && ring(h)) {
		await api.updateHole(courseId, h.holeId, { fairway_polygon: ring(h) });
	}

	if (h.parChanged) {
		await api.updateHole(courseId, h.holeId, { par: h.par });
	}

	for (const hazardId of h.removedHazardIds ?? []) {
		await api.deleteHoleHazard(courseId, h.holeId, hazardId);
	}
	h.removedHazardIds = [];
	for (const hz of h.hazards) {
		if (!hz.hazardId) {
			const created = await api.createHoleHazard(courseId, h.holeId, {
				hazard_type: hz.hazard_type,
				polygon: hz.polygon.map((p) => [p.lat, p.lng])
			});
			hz.hazardId = created.hazard_id;
		}
	}
}

/** True if the hole has any unsaved change. */
export function holeIsDirty(h: MapperHole): boolean {
	return (
		!h.holeId ||
		!!h.teeMoved ||
		!!h.pinMoved ||
		!!h.parChanged ||
		!!h.fairwayChanged ||
		(h.removedHazardIds?.length ?? 0) > 0 ||
		h.hazards.some((hz) => !hz.hazardId)
	);
}
