<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchPredictions, type Prediction } from '$lib/api';

	let predictions = $state<Prediction[]>([]);
	let loading = $state(true);
	let filterConfidence = $state('all');

	onMount(async () => {
		try {
			const data = await fetchPredictions();
			predictions = data;
		} catch (e) {
			console.error('Failed to load predictions:', e);
		}
		loading = false;
	});

	let filtered = $derived.by(() => {
		if (filterConfidence === 'all') return predictions;
		return predictions.filter((p) => p.confidence === filterConfidence);
	});

	function confidenceIcon(c: string) {
		return c === 'high' ? '🟢' : c === 'medium' ? '🟡' : '🔴';
	}
	function confidenceLabel(c: string) {
		return c === 'high' ? '高' : c === 'medium' ? '中' : '低';
	}
	function recClass(action: string) {
		if (action.includes('STRONG')) return 'strong';
		if (action.includes('MODERATE')) return 'moderate';
		if (action.includes('OVER')) return 'over';
		return 'avoid';
	}
</script>

<svelte:head>
	<title>预测分析 - WC2026</title>
</svelte:head>

<div class="predictions-page">
	<div class="page-header">
		<h2>🔮 全部预测分析</h2>
		<div class="confidence-filters">
			<button class:active={filterConfidence === 'all'} onclick={() => (filterConfidence = 'all')}>全部</button>
			<button class:active={filterConfidence === 'high'} onclick={() => (filterConfidence = 'high')}>🟢 高信心</button>
			<button class:active={filterConfidence === 'medium'} onclick={() => (filterConfidence = 'medium')}>🟡 中信心</button>
			<button class:active={filterConfidence === 'low'} onclick={() => (filterConfidence = 'low')}>🔴 低信心</button>
		</div>
	</div>

	{#if loading}
		<div class="loading">
			<div class="spinner">⏳</div>
			<p>加载预测数据中...</p>
		</div>
	{:else if filtered.length === 0}
		<div class="empty">暂无预测数据</div>
	{:else}
		<div class="pred-grid">
			{#each filtered as pred (pred.matchId)}
				<a href="/predictions/{pred.matchId}" class="pred-card">
					<div class="pred-match">{pred.match}</div>
					<div class="pred-meta">
						<span class="stage-tag">{pred.stage}</span>
						<span class="confidence">{confidenceIcon(pred.confidence)} {confidenceLabel(pred.confidence)}信心</span>
					</div>
					<div class="pred-probs">
						<span class="prob home">{Math.round(pred.prediction.home * 100)}%</span>
						<span class="prob draw">{Math.round(pred.prediction.draw * 100)}%</span>
						<span class="prob away">{Math.round(pred.prediction.away * 100)}%</span>
					</div>
					<div class="pred-details">
						<span>预测比分: <strong>{pred.predictedScore}</strong></span>
						<span class="rec {recClass(pred.recommendation.action)}">{pred.recommendation.action}</span>
					</div>
					<div class="pred-odds">
						公平赔率: 主{pred.fairOdds.home} / 平{pred.fairOdds.draw} / 客{pred.fairOdds.away}
					</div>
					{#if pred.valueBets.length > 0}
						<div class="value-badge">🎯 {pred.valueBets.length} 个价值投注</div>
					{/if}
				</a>
			{/each}
		</div>
	{/if}
</div>

<style>
	.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px; }
	.page-header h2 { color: #1e88e5; font-size: 20px; }
	.confidence-filters { display: flex; gap: 4px; }
	.confidence-filters button { background: #1e2433; border: 1px solid #2a3040; color: #aaa; padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; }
	.confidence-filters button.active { background: #1e88e5; border-color: #1e88e5; color: #fff; }
	.pred-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; }
	.pred-card {
		background: #141822; border: 1px solid #1e2433; border-radius: 8px; padding: 16px;
		transition: all 0.2s; display: block; color: inherit; text-decoration: none;
	}
	.pred-card:hover { border-color: #1e88e5; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(30,136,229,0.15); }
	.pred-match { font-weight: bold; font-size: 15px; margin-bottom: 6px; color: #1e88e5; }
	.pred-meta { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
	.stage-tag { background: #1a2332; color: #8899aa; padding: 2px 8px; border-radius: 3px; font-size: 11px; }
	.confidence { font-size: 12px; }
	.pred-probs { display: flex; gap: 8px; margin: 8px 0; }
	.prob { padding: 3px 10px; border-radius: 4px; font-size: 13px; font-weight: bold; }
	.prob.home { background: #1b5e20; color: #a5d6a7; }
	.prob.draw { background: #4a3000; color: #ffe082; }
	.prob.away { background: #b71c1c; color: #ef9a9a; }
	.pred-details { display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: #8899aa; margin: 6px 0; }
	.pred-details strong { color: #1e88e5; }
	.rec { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
	.rec.strong { background: #2e7d32; color: #fff; }
	.rec.moderate { background: #f57f17; color: #000; }
	.rec.over { background: #1565c0; color: #fff; }
	.rec.avoid { background: #c62828; color: #fff; }
	.pred-odds { font-size: 12px; color: #667; }
	.value-badge { margin-top: 6px; font-size: 12px; color: #4caf50; font-weight: bold; }
	.loading { text-align: center; padding: 80px 0; }
	.spinner { font-size: 48px; animation: spin 1s linear infinite; display: inline-block; }
	@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
	.loading p { color: #8899aa; margin-top: 12px; }
	.empty { color: #556; text-align: center; padding: 60px 0; }
</style>
