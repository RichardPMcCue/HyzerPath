import { browser } from '$app/environment';

const TOKEN_KEY = 'hyzerpath_token';

function createAuth() {
	let token = $state<string | null>(browser ? localStorage.getItem(TOKEN_KEY) : null);

	return {
		get token() {
			return token;
		},
		get isLoggedIn() {
			return token !== null;
		},
		login(newToken: string) {
			token = newToken;
			if (browser) localStorage.setItem(TOKEN_KEY, newToken);
		},
		logout() {
			token = null;
			if (browser) localStorage.removeItem(TOKEN_KEY);
		}
	};
}

export const auth = createAuth();
