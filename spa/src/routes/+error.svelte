<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
</script>

<section class="mx-auto max-w-prose p-6">
	<h1 class="mb-2 text-2xl">{page.status}</h1>
	<p class="opacity-70">{page.error?.message ?? 'unknown error'}</p>
	<a class="mt-4 inline-block underline opacity-60 hover:opacity-100" href={resolve('/')}>
		back to streams
	</a>
</section>
