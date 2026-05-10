<script lang="ts">
	import '../app.css';

	let { children } = $props();
</script>

<header class="border-b border-white/5 px-6 py-3 text-sm uppercase tracking-widest opacity-70">
	trashmonitor
</header>

<main class="p-4">
	{@render children?.()}
</main>
