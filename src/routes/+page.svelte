<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	onMount(() => {
		goto('/matches', { replaceState: true });
	});
</script>

<p style="text-align:center;padding:80px 0;color:#8899aa">正在跳转...</p>
