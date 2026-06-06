<script lang="ts">
	import { page } from '$app/state';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	const navItems = [
		{ href: '/matches', label: '📋 赛程', match: '/matches' },
		{ href: '/predictions', label: '🔮 预测', match: '/predictions' },
		{ href: '/betting', label: '💰 模拟下注', match: '/betting' },
		{ href: '/stats', label: '📊 统计', match: '/stats' }
	];

	function isActive(item: { href: string; match: string }) {
		const path = page.url.pathname;
		if (item.match === '/matches') return path === '/' || path.startsWith('/matches');
		return path.startsWith(item.match);
	}
</script>

<svelte:head>
	<title>⚽ WC2026 博彩预测引擎</title>
</svelte:head>

<div class="app">
	<header class="header">
		<div class="header-inner">
			<h1 class="title">⚽ WC2026 博彩预测引擎</h1>
			<p class="subtitle">独立分析 · 价值投注 · 模拟游戏</p>
		</div>
		<nav class="nav">
			{#each navItems as item}
				<a href={item.href} class="tab-btn" class:active={isActive(item)}>{item.label}</a>
			{/each}
		</nav>
	</header>

	<main class="main">
		{@render children()}
	</main>

	<footer class="footer">
		<p>⚠️ 本系统仅为模拟演示，所有赔率和预测均为算法生成，不代表真实投注建议。</p>
		<p>模拟资金 10000 元 | 后端 API 实时数据</p>
	</footer>
</div>

<style>
	:global(*) {
		margin: 0;
		padding: 0;
		box-sizing: border-box;
	}
	:global(body) {
		font-family: -apple-system, 'Segoe UI', Roboto, 'Microsoft YaHei', sans-serif;
		background: #0a0e17;
		color: #e0e0e0;
		min-height: 100vh;
	}
	:global(a) {
		text-decoration: none;
		color: inherit;
	}
	.app {
		max-width: 1200px;
		margin: 0 auto;
		padding: 0 16px;
	}
	.header {
		background: linear-gradient(135deg, #1a1f2e 0%, #0d1117 100%);
		padding: 20px 24px;
		margin: -16px -16px 16px;
		border-bottom: 2px solid #1e88e5;
	}
	.header-inner {
		text-align: center;
	}
	.title {
		text-align: center;
		font-size: 26px;
		color: #fff;
	}
	.subtitle {
		text-align: center;
		color: #8899aa;
		font-size: 13px;
		margin: 4px 0 12px;
	}
	.nav {
		display: flex;
		justify-content: center;
		gap: 8px;
		flex-wrap: wrap;
	}
	.tab-btn {
		background: #1e2433;
		border: 1px solid #2a3040;
		color: #aaa;
		padding: 8px 20px;
		border-radius: 6px;
		cursor: pointer;
		font-size: 14px;
		transition: all 0.2s;
	}
	.tab-btn:hover {
		background: #2a3040;
		color: #fff;
	}
	.tab-btn.active {
		background: #1e88e5;
		border-color: #1e88e5;
		color: #fff;
	}
	.main {
		padding: 16px 0;
		min-height: 500px;
	}
	.footer {
		text-align: center;
		padding: 24px;
		color: #556;
		font-size: 12px;
		border-top: 1px solid #1a1f2e;
		margin-top: 32px;
	}
</style>
