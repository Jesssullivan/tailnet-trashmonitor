<script lang="ts">
	import Hls from 'hls.js';

	type Codec = { codec: string; width?: number; height?: number; profile?: string };
	type Path = {
		name: string;
		ready: boolean;
		readyTime: string | null;
		tracks: string[];
		codec: Codec | null;
		bytesReceived: number;
		readers: number;
	};

	let paths = $state<Path[]>([]);
	let lastError = $state<string | null>(null);
	let lastUpdated = $state<number>(0);

	const tick = async () => {
		try {
			const r = await fetch('/api/v3/paths/list', { headers: { accept: 'application/json' } });
			if (!r.ok) throw new Error(`HTTP ${r.status}`);
			const data = (await r.json()) as { items: Array<Record<string, unknown>> };
			paths = data.items
				.map((p) => {
					const tracks2 =
						(p.tracks2 as Array<{ codec: string; codecProps?: Record<string, unknown> }>) ?? [];
					const t = tracks2[0];
					const codec: Codec | null = t
						? {
								codec: t.codec,
								width: (t.codecProps?.width as number) ?? undefined,
								height: (t.codecProps?.height as number) ?? undefined,
								profile: (t.codecProps?.profile as string) ?? undefined,
							}
						: null;
					return {
						name: p.name as string,
						ready: !!p.ready,
						readyTime: (p.readyTime as string | null) ?? null,
						tracks: (p.tracks as string[]) ?? [],
						codec,
						bytesReceived: (p.bytesReceived as number) ?? 0,
						readers: ((p.readers as unknown[]) ?? []).length,
					};
				})
				.sort((a, b) => a.name.localeCompare(b.name));
			lastError = null;
			lastUpdated = Date.now();
		} catch (err) {
			lastError = err instanceof Error ? err.message : String(err);
		}
	};

	$effect(() => {
		tick();
		const id = setInterval(tick, 10_000);
		return () => clearInterval(id);
	});

	const attachHls = (video: HTMLVideoElement, name: string) => {
		const url = `/${encodeURIComponent(name)}/index.m3u8`;
		if (Hls.isSupported()) {
			const hls = new Hls({ liveDurationInfinity: true, enableWorker: true });
			hls.loadSource(url);
			hls.attachMedia(video);
			return {
				destroy: () => hls.destroy(),
			};
		}
		video.src = url;
		return { destroy: () => {} };
	};

	const requestFullscreen = (el: HTMLElement) => {
		if (document.fullscreenElement === el) {
			void document.exitFullscreen();
		} else {
			void el.requestFullscreen();
		}
	};

	const formatBytes = (n: number): string => {
		if (n < 1024) return `${n} B`;
		if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
		if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
		return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
	};

	const formatUptime = (readyTime: string | null): string => {
		if (!readyTime) return '';
		const elapsed = (Date.now() - new Date(readyTime).getTime()) / 1000;
		if (elapsed < 60) return `${Math.floor(elapsed)}s`;
		if (elapsed < 3600) return `${Math.floor(elapsed / 60)}m`;
		if (elapsed < 86400)
			return `${Math.floor(elapsed / 3600)}h ${Math.floor((elapsed % 3600) / 60)}m`;
		return `${Math.floor(elapsed / 86400)}d ${Math.floor((elapsed % 86400) / 3600)}h`;
	};

	const codecLabel = (c: Codec | null): string => {
		if (!c) return '';
		const res = c.width && c.height ? `${c.width}×${c.height}` : '';
		return [c.codec, res, c.profile].filter(Boolean).join(' · ');
	};
</script>

<section class="grid grid-cols-1 gap-4 md:grid-cols-2">
	{#each paths as p (p.name)}
		<figure class="group relative overflow-hidden rounded-2xl border border-white/5 bg-black">
			<div class="flex items-center justify-between px-3 py-2 text-xs uppercase tracking-wider">
				<span class="font-medium">{p.name}</span>
				<div class="flex items-center gap-3 text-[10px] opacity-60">
					{#if p.ready}
						<span>{codecLabel(p.codec)}</span>
						<span>·</span>
						<span>up {formatUptime(p.readyTime)}</span>
						<span>·</span>
						<span>{formatBytes(p.bytesReceived)}</span>
						{#if p.readers > 0}
							<span>·</span>
							<span class="text-emerald-300">{p.readers} viewer{p.readers === 1 ? '' : 's'}</span>
						{/if}
					{/if}
					<span class:text-emerald-400={p.ready} class:text-rose-400={!p.ready} class="font-medium">
						{p.ready ? 'live' : 'offline'}
					</span>
				</div>
			</div>
			{#if p.ready}
				{#key p.name}
					<button
						type="button"
						class="block aspect-video w-full bg-black"
						onclick={(e) => requestFullscreen(e.currentTarget)}
						title="Click to toggle fullscreen"
					>
						<video
							class="block aspect-video w-full bg-black object-contain"
							autoplay
							muted
							playsinline
							use:attachHls={p.name}
						>
							<track kind="captions" />
						</video>
					</button>
				{/key}
			{:else}
				<div
					class="flex aspect-video flex-col items-center justify-center gap-2 text-xs opacity-40"
				>
					<span class="text-rose-300/60">no producer</span>
					<span class="text-[10px] opacity-50">awaiting publish to /{p.name}</span>
				</div>
			{/if}
		</figure>
	{:else}
		<p class="opacity-50">No streams configured. Bring up a capture host.</p>
	{/each}
</section>

<footer class="mt-4 flex items-center justify-between text-[10px] opacity-40">
	<span>
		{#if lastUpdated > 0}
			refreshed {new Date(lastUpdated).toLocaleTimeString()}
		{/if}
	</span>
	{#if lastError}
		<span class="text-rose-400">manifest fetch failed: {lastError}</span>
	{/if}
</footer>
