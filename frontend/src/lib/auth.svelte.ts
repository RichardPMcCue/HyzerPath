import { browser } from '$app/environment';
import type { Me } from '$lib/types';

const TOKEN_KEY = 'hyzerpath_token';

function createAuth() {
	let token = $state<string | null>(browser ? localStorage.getItem(TOKEN_KEY) : null);
	let user = $state<Me | null>(null);

	return {
		get token() {
			return token;
		},
		get isLoggedIn() {
			return token !== null;
		},
		get user() {
			return user;
		},
		get isAdmin() {
			return user?.is_admin === true;
		},
		setUser(me: Me) {
			user = me;
		},
		login(newToken: string) {
			token = newToken;
			if (browser) localStorage.setItem(TOKEN_KEY, newToken);
		},
		logout() {
			token = null;
			user = null;
			if (browser) localStorage.removeItem(TOKEN_KEY);
		}
	};
}

export const auth = createAuth();
