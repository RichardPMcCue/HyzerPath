import { goto } from '$app/navigation';
import { auth } from '$lib/auth.svelte';
import type {
	CaddieMode,
	Course,
	Disc,
	DiscItResult,
	DiscStat,
	HolePath,
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

	if (response.status === 401 || response.status === 403) {
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
	setDiscStat: (discId: number, stat: { avg_distance: number; max_distance?: number | null }) =>
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
		throwIn: { end_latitude: number; end_longitude: number; disc_id?: number | null }
	) =>
		request<ThrowMeasurement>(`/throws/sessions/${sessionId}/throws`, {
			method: 'POST',
			body: JSON.stringify(throwIn)
		}),
	deleteThrow: (sessionId: number, throwId: number) =>
		request(`/throws/sessions/${sessionId}/throws/${throwId}`, { method: 'DELETE' }),

	// --- courses ---
	getCourses: () => request<Course[]>('/courses'),
	getCourse: (courseId: number) => request<Course>(`/courses/${courseId}`),

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
	startRound: (courseId: number) =>
		request<Round>('/rounds', { method: 'POST', body: JSON.stringify({ course_id: courseId }) }),
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
			is_holed?: boolean;
		}
	) =>
		request(`/rounds/${roundId}/holes/${holeId}/throws`, {
			method: 'POST',
			body: JSON.stringify(throwIn)
		}),
	getRoundStats: (roundId: number) =>
		request<RoundStats>(`/rounds/${roundId}/stats`)
};

export function loginUrl(): string {
	return `${API_URL}/auth/login`;
}
