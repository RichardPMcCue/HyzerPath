import { goto } from '$app/navigation';
import { auth } from '$lib/auth.svelte';
import type {
	CaddieMode,
	Course,
	Disc,
	DiscItResult,
	DiscStat,
	Hazard,
	Hole,
	HoleEdge,
	HoleNode,
	HolePath,
	Me,
	Round,
	RoundHoleScore,
	RoundStats,
	ThrowMeasurement,
	ThrowSession
} from '$lib/types';

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
	}
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
	const headers = new Headers(options.headers);
	headers.set('Content-Type', 'application/json');
	if (auth.token) headers.set('Authorization', `Bearer ${auth.token}`);

	const response = await fetch(`${API_URL}${path}`, { ...options, headers });

	// 401 = bad/expired token → re-login. 403 = authenticated but not allowed
	// (e.g. non-admin hitting an admin route) → surface the error, keep session.
	if (response.status === 401) {
		auth.logout();
		goto('/login');
		throw new ApiError(response.status, 'Session expired');
	}
	if (!response.ok) {
		let detail = response.statusText;
		try {
			detail = (await response.json()).detail ?? detail;
		} catch {
			/* not json */
		}
		throw new ApiError(response.status, detail);
	}
	return response.json();
}

export const api = {
	// --- bag ---
	getDiscs: () => request<Disc[]>('/bag/discs'),
	searchDiscs: (name: string) =>
		request<DiscItResult[]>(`/bag/discs/search?name=${encodeURIComponent(name)}`),
	createDisc: (disc: Partial<Disc>) =>
		request<Disc>('/bag/discs', { method: 'POST', body: JSON.stringify(disc) }),
	updateDisc: (discId: number, disc: Partial<Disc>) =>
		request<Disc>(`/bag/discs/${discId}`, { method: 'PATCH', body: JSON.stringify(disc) }),
	deleteDisc: (discId: number) => request(`/bag/discs/${discId}`, { method: 'DELETE' }),

	// --- throw stats ---
	getDiscStats: () => request<DiscStat[]>('/bag/stats'),
	setDiscStat: (
		discId: number,
		stat: { avg_distance: number; max_distance?: number | null; throw_style?: string }
	) =>
		request<DiscStat>(`/bag/discs/${discId}/stats`, {
			method: 'PUT',
			body: JSON.stringify(stat)
		}),

	// --- throw measuring ---
	createThrowSession: (start: { start_latitude: number; start_longitude: number; label?: string }) =>
		request<ThrowSession>('/throws/sessions', { method: 'POST', body: JSON.stringify(start) }),
	updateThrowSession: (
		sessionId: number,
		update: { start_latitude?: number; start_longitude?: number; label?: string }
	) =>
		request<ThrowSession>(`/throws/sessions/${sessionId}`, {
			method: 'PATCH',
			body: JSON.stringify(update)
		}),
	recordThrow: (
		sessionId: number,
		throwIn: {
			end_latitude: number;
			end_longitude: number;
			disc_id?: number | null;
			throw_style?: string | null;
		}
	) =>
		request<ThrowMeasurement>(`/throws/sessions/${sessionId}/throws`, {
			method: 'POST',
			body: JSON.stringify(throwIn)
		}),
	deleteThrow: (sessionId: number, throwId: number) =>
		request(`/throws/sessions/${sessionId}/throws/${throwId}`, { method: 'DELETE' }),

	// --- auth ---
	getMe: () => request<Me>('/auth/me'),
	updateMe: (update: { username: string }) =>
		request<Me>('/auth/me', { method: 'PATCH', body: JSON.stringify(update) }),
	listUsers: () => request<Me[]>('/auth/users'),
	setUserAdmin: (userId: number, isAdmin: boolean) =>
		request<Me>(`/auth/users/${userId}`, {
			method: 'PATCH',
			body: JSON.stringify({ is_admin: isAdmin })
		}),

	// --- courses ---
	getCourses: () => request<Course[]>('/courses'),
	getCourse: (courseId: number) => request<Course>(`/courses/${courseId}`),
	createCourse: (course: {
		name: string;
		city: string;
		state: string;
		address: string;
		total_par: number;
	}) => request<Course>('/courses', { method: 'POST', body: JSON.stringify(course) }),
	deleteCourse: (courseId: number) => request(`/courses/${courseId}`, { method: 'DELETE' }),
	createHole: (
		courseId: number,
		hole: { hole_number: number; par: number; distance: number; elevation: number }
	) => request<Hole>(`/courses/${courseId}/holes`, { method: 'POST', body: JSON.stringify(hole) }),
	updateHole: (courseId: number, holeId: number, hole: Partial<Hole>) =>
		request<Hole>(`/courses/${courseId}/holes/${holeId}`, {
			method: 'PATCH',
			body: JSON.stringify(hole)
		}),
	deleteHole: (courseId: number, holeId: number) =>
		request(`/courses/${courseId}/holes/${holeId}`, { method: 'DELETE' }),
	getHoleNodes: (courseId: number, holeId: number) =>
		request<HoleNode[]>(`/courses/${courseId}/holes/${holeId}/nodes`),
	createHoleNode: (courseId: number, holeId: number, node: Partial<HoleNode>) =>
		request<HoleNode>(`/courses/${courseId}/holes/${holeId}/nodes`, {
			method: 'POST',
			body: JSON.stringify(node)
		}),
	updateHoleNode: (courseId: number, holeId: number, nodeId: number, node: Partial<HoleNode>) =>
		request<HoleNode>(`/courses/${courseId}/holes/${holeId}/nodes/${nodeId}`, {
			method: 'PATCH',
			body: JSON.stringify(node)
		}),
	createHoleEdge: (
		courseId: number,
		holeId: number,
		edge: { from_node_id: number; to_node_id: number; distance: number }
	) =>
		request<HoleEdge>(`/courses/${courseId}/holes/${holeId}/edges`, {
			method: 'POST',
			body: JSON.stringify(edge)
		}),
	deleteHoleNode: (courseId: number, holeId: number, nodeId: number) =>
		request(`/courses/${courseId}/holes/${holeId}/nodes/${nodeId}`, { method: 'DELETE' }),
	rebuildHoleEdges: (courseId: number, holeId: number) =>
		request<HoleEdge[]>(`/courses/${courseId}/holes/${holeId}/edges/rebuild`, {
			method: 'POST'
		}),
	getHoleHazards: (courseId: number, holeId: number) =>
		request<Hazard[]>(`/courses/${courseId}/holes/${holeId}/hazards`),
	createHoleHazard: (
		courseId: number,
		holeId: number,
		hazard: { hazard_type: string; polygon: [number, number][] }
	) =>
		request<Hazard>(`/courses/${courseId}/holes/${holeId}/hazards`, {
			method: 'POST',
			body: JSON.stringify(hazard)
		}),
	deleteHoleHazard: (courseId: number, holeId: number, hazardId: number) =>
		request(`/courses/${courseId}/holes/${holeId}/hazards/${hazardId}`, { method: 'DELETE' }),

	// --- caddie ---
	getHolePath: (
		courseId: number,
		holeId: number,
		opts: {
			mode?: CaddieMode;
			useWind?: boolean;
			startNodeId?: number;
			lie?: { latitude: number; longitude: number };
		} = {}
	) => {
		const params = new URLSearchParams();
		if (opts.mode) params.set('mode', opts.mode);
		if (opts.useWind) params.set('use_wind', 'true');
		if (opts.startNodeId) params.set('start_node_id', String(opts.startNodeId));
		if (opts.lie) {
			params.set('lie_latitude', String(opts.lie.latitude));
			params.set('lie_longitude', String(opts.lie.longitude));
		}
		const qs = params.toString();
		return request<HolePath>(
			`/courses/${courseId}/holes/${holeId}/path${qs ? `?${qs}` : ''}`
		);
	},

	// --- rounds ---
	startRound: (
		courseId: number,
		opts: { tracking_mode?: string; layout?: string } = {}
	) =>
		request<Round>('/rounds', {
			method: 'POST',
			body: JSON.stringify({ course_id: courseId, ...opts })
		}),
	getRound: (roundId: number) => request<Round>(`/rounds/${roundId}`),
	listRounds: () => request<Round[]>('/rounds'),
	setHoleScore: (roundId: number, holeId: number, score: number) =>
		request<RoundHoleScore>(`/rounds/${roundId}/holes/${holeId}`, {
			method: 'PUT',
			body: JSON.stringify({ score })
		}),
	finishRound: (roundId: number) =>
		request<Round>(`/rounds/${roundId}/finish`, { method: 'POST' }),
	deleteRound: (roundId: number) => request(`/rounds/${roundId}`, { method: 'DELETE' }),
	recordRoundThrow: (
		roundId: number,
		holeId: number,
		throwIn: {
			throw_number: number;
			disc_id?: number | null;
			start_latitude?: number | null;
			start_longitude?: number | null;
			end_latitude?: number | null;
			end_longitude?: number | null;
			landing_zone?: string | null;
			drop_zone?: string | null;
			putt_distance_ft?: number | null;
			is_holed?: boolean;
		}
	) =>
		request<{ round_throw_id: number }>(`/rounds/${roundId}/holes/${holeId}/throws`, {
			method: 'POST',
			body: JSON.stringify(throwIn)
		}),
	deleteRoundThrow: (roundId: number, roundThrowId: number) =>
		request(`/rounds/${roundId}/throws/${roundThrowId}`, { method: 'DELETE' }),
	getRoundStats: (roundId: number) =>
		request<RoundStats>(`/rounds/${roundId}/stats`)
};

export function loginUrl(): string {
	return `${API_URL}/auth/login`;
}
