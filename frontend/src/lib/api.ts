import { goto } from '$app/navigation';
import { auth } from '$lib/auth.svelte';
import type {
	CaddieMode,
	Course,
	Disc,
	DiscItResult,
	DiscStat,
	HolePath
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
	deleteDisc: (discId: number) => request(`/bag/discs/${discId}`, { method: 'DELETE' }),

	// --- throw stats ---
	getDiscStats: () => request<DiscStat[]>('/bag/stats'),
	setDiscStat: (discId: number, stat: { avg_distance: number; max_distance?: number | null }) =>
		request<DiscStat>(`/bag/discs/${discId}/stats`, {
			method: 'PUT',
			body: JSON.stringify(stat)
		}),

	// --- courses ---
	getCourses: () => request<Course[]>('/courses'),
	getCourse: (courseId: number) => request<Course>(`/courses/${courseId}`),

	// --- caddie ---
	getHolePath: (
		courseId: number,
		holeId: number,
		opts: { mode?: CaddieMode; useWind?: boolean; startNodeId?: number } = {}
	) => {
		const params = new URLSearchParams();
		if (opts.mode) params.set('mode', opts.mode);
		if (opts.useWind) params.set('use_wind', 'true');
		if (opts.startNodeId) params.set('start_node_id', String(opts.startNodeId));
		const qs = params.toString();
		return request<HolePath>(
			`/courses/${courseId}/holes/${holeId}/path${qs ? `?${qs}` : ''}`
		);
	}
};

export function loginUrl(): string {
	return `${API_URL}/auth/login`;
}
