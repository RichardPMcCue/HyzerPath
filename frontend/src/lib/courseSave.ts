import { api } from '$lib/api';
import { haversineFeet } from '$lib/geo';
import type { MapperHole } from '$lib/types';

function chainDistance(points: { lat: number; lng: number }[]): number {
	let total = 0;
	for (let i = 0; i < points.length - 1; i++) {
		total += haversineFeet(points[i].lat, points[i].lng, points[i + 1].lat, points[i + 1].lng);
	}
	return Math.round(total);
}

/** Persist a fully placed mapper hole: hole + tee/waypoint/basket nodes,
 *  edges (chain, rebuilt server-side), and any drawn hazard areas. */
export async function createMappedHole(courseId: number, h: MapperHole): Promise<void> {
	if (!h.tee || !h.pin) return;
	const chain = [h.tee, ...h.fairway, h.pin];
	const hole = await api.createHole(courseId, {
		hole_number: h.holeNumber,
		par: h.par,
		distance: chainDistance(chain),
		elevation: 0
	});
	await api.createHoleNode(courseId, hole.hole_id, {
		node_type: 'tee',
		sequence: 0,
		label: 'Tee',
		latitude: h.tee.lat,
		longitude: h.tee.lng,
		is_fairway: true
	});
	for (let i = 0; i < h.fairway.length; i++) {
		await api.createHoleNode(courseId, hole.hole_id, {
			node_type: 'landing_zone',
			sequence: i + 1,
			label: `LZ ${i + 1}`,
			latitude: h.fairway[i].lat,
			longitude: h.fairway[i].lng,
			is_fairway: true
		});
	}
	await api.createHoleNode(courseId, hole.hole_id, {
		node_type: 'basket',
		sequence: h.fairway.length + 1,
		label: 'Basket',
		latitude: h.pin.lat,
		longitude: h.pin.lng,
		is_fairway: true
	});
	await api.rebuildHoleEdges(courseId, hole.hole_id);
	for (const hz of h.hazards) {
		await api.createHoleHazard(courseId, hole.hole_id, {
			hazard_type: hz.hazard_type,
			polygon: hz.polygon.map((p) => [p.lat, p.lng])
		});
	}
}

/** Sync an existing hole's structure: waypoint adds/moves/removals, marker
 *  moves, par, and hazard changes. Rebuilds edges when topology changed. */
export async function saveMappedHoleChanges(courseId: number, h: MapperHole): Promise<void> {
	if (!h.holeId) return;

	for (const nodeId of h.removedNodeIds ?? []) {
		await api.deleteHoleNode(courseId, h.holeId, nodeId);
	}
	h.removedNodeIds = [];

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
				sequence: h.fairway.length + 1,
				label: 'Basket',
				latitude: h.pin.lat,
				longitude: h.pin.lng,
				is_fairway: true
			});
			h.pinNodeId = node.hole_node_id;
		}
	}

	// Waypoints: resequence everything when the set changed, else just moves
	if (h.fairwayChanged) {
		for (let i = 0; i < h.fairway.length; i++) {
			const wp = h.fairway[i];
			if (wp.nodeId) {
				await api.updateHoleNode(courseId, h.holeId, wp.nodeId, {
					sequence: i + 1,
					latitude: wp.lat,
					longitude: wp.lng
				});
			} else {
				const node = await api.createHoleNode(courseId, h.holeId, {
					node_type: 'landing_zone',
					sequence: i + 1,
					label: `LZ ${i + 1}`,
					latitude: wp.lat,
					longitude: wp.lng,
					is_fairway: true
				});
				wp.nodeId = node.hole_node_id;
			}
		}
		if (h.pinNodeId) {
			await api.updateHoleNode(courseId, h.holeId, h.pinNodeId, {
				sequence: h.fairway.length + 1
			});
		}
		await api.rebuildHoleEdges(courseId, h.holeId);
	} else {
		for (const wp of h.fairway) {
			if (wp.moved && wp.nodeId) {
				await api.updateHoleNode(courseId, h.holeId, wp.nodeId, {
					latitude: wp.lat,
					longitude: wp.lng
				});
			}
		}
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
		h.fairway.some((wp) => wp.moved) ||
		(h.removedNodeIds?.length ?? 0) > 0 ||
		(h.removedHazardIds?.length ?? 0) > 0 ||
		h.hazards.some((hz) => !hz.hazardId)
	);
}
