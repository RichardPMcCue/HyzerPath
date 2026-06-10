import adapter from '@sveltejs/adapter-static';
import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},

			// Single-page app: everything is client-rendered behind auth,
			// served as static files (fallback handles deep links).
			adapter: adapter({ fallback: 'index.html' })
		})
	],
	server: {
		proxy: {
			// Mirrors the nginx /tiles/ proxy in production: satellite tiles are
			// served same-origin so tracker blockers can't kill them
			'/tiles': {
				target: 'https://server.arcgisonline.com',
				changeOrigin: true,
				rewrite: (path) =>
					path.replace(/^\/tiles/, '/ArcGIS/rest/services/World_Imagery/MapServer/tile')
			}
		}
	}
});
