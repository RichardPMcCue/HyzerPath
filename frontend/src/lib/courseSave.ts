import { api } from '$lib/api';
import { haversineFeet } from '$lib/geo';
import type { MapperHole } from '$lib/types';

/** Persist a fully placed mapper hole: hole + tee/basket nodes + the edge between them. */
export async function createMappedHole(courseId: number, h: MapperHole): Promise<void> {
	if (!h.tee || !h.pin) return;
	const distance = Math.round(haversineFeet(h.tee.lat, h.tee.lng, h.pin.lat, h.pin.lng));
	const hole = await api.createHole(courseId, {
		hole_number: h.holeNumber,
		par: h.par,
		distance,
		elevation: 0
	});
	const tee = await api.createHoleNode(courseId, hole.hole_id, {
		node_type: 'tee',
		sequence: 0,
		label: 'Tee',
		latitude: h.tee.lat,
		longitude: h.tee.lng,
		is_fairway: true
	});
	const basket = await api.createHoleNode(courseId, hole.hole_id, {
		node_type: 'basket',
		sequence: 1,
		label: 'Basket',
		latitude: h.pin.lat,
		longitude: h.pin.lng,
		is_fairway: true
	});
	await api.createHoleEdge(courseId, hole.hole_id, {
		from_node_id: tee.hole_node_id,
		to_node_id: basket.hole_node_id,
		distance
	});
}
