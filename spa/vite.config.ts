import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		// In dev, proxy /api (MediaMTX REST) and HLS paths. Set
		// VITE_MEDIAMTX_URL in your shell / .env (e.g.
		// `http://trashmonitor.<your-tailnet>.ts.net`) to point at the
		// deployed cluster, or leave unset to talk to a locally-running
		// MediaMTX (default ports 9997 / 8888).
		proxy: {
			'/api': {
				target: process.env.VITE_MEDIAMTX_URL ?? 'http://localhost:9997',
				changeOrigin: true,
			},
			// Catch HLS playlist + segment paths (any /<stream>/foo.m3u8|.ts).
			'^/[^/]+/.+\\.(m3u8|ts|mp4|m4s)$': {
				target: process.env.VITE_MEDIAMTX_URL ?? 'http://localhost:8888',
				changeOrigin: true,
			},
		},
	},
	build: {
		reportCompressedSize: true,
		chunkSizeWarningLimit: 250,
	},
});
