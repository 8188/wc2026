<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchBettingStats, fetchPredictions, type BettingStats, type Prediction } from '$lib/api';

	let stats = $state<BettingStats>({
		bankroll: 10000, startBankroll: 10000, totalBets: 0,
		wins: 0, losses: 0, winRate: 0, roi: 0, totalProfit: 0, profitPercent: 0, pending: 0
	});
	let predictions = $state<Prediction[]>([]);
	let loading = $state(true);

	onMount(async () => {
		try {
			const [sData, pData] = await Promise.all([fetchBettingStats(), fetchPredictions()]);
			stats = sData;
			predictions = pData;
		} catch (e) {
			console.error('Failed to load stats:', e);
		}
		loading = false;
	});

	let confidenceDist = $derived({
		high: predictions.filter((p) => p.confidence === 'high').length,
		medium: predictions.filter((p) => p.confidence === 'medium').length,
		low: predictions.filter((p) => p.confidence === 'low').length
	});

	let recDist = $derived({
		strong: predictions.filter((p) => p.recommendation?.action?.includes('STRONG')).length,
		moderate: predictions.filter((p) => p.recommendation?.action?.includes('MODERATE')).length,
		avoid: predictions.filter(
			(p) => p.recommendation?.action?.includes('NO BET') || p.recommendation?.action?.includes('AVOID')
		).length,
		over: predictions.filter((p) => p.recommendation?.action?.includes('OVER')).length
	});

	let totalConf = $derived(confidenceDist.high + confidenceDist.medium + confidenceDist.low || 1);

	function profitBarPct(p: number) {
		return Math.min(100, Math.max(0, 50 + p * 0.5));
	}
</script>

<svelte:head>
	<title>统计 - WC2026</title>
</svelte:head>

<div class="stats-page">
	<h2>📊 全局统计</h2>

	{#if loading}
		<div class="loading">
			<div class="spinner">⏳</div>
			<p>加载统计数据中...</p>
		</div>
	{:else}
		<!-- Stat Cards -->
		<div class="stat-cards">
			<div class="stat-card">
				<div class="stat-l">模拟资金</div>
				<div class="stat-v" style="color:{stats.totalProfit >= 0 ? '#4caf50' : '#f44336'}">
					{Math.round(stats.bankroll * 100) / 100} 元
				</div>
			</div>
			<div class="stat-card">
				<div class="stat-l">盈亏</div>
				<div class="stat-v" style="color:{stats.totalProfit >= 0 ? '#4caf50' : '#f44336'}">
					{stats.totalProfit > 0 ? '+' : ''}{stats.totalProfit} 元
				</div>
			</div>
			<div class="stat-card">
				<div class="stat-l">ROI</div>
				<div class="stat-v" style="color:{stats.roi >= 0 ? '#4caf50' : '#f44336'}">{stats.roi}%</div>
			</div>
			<div class="stat-card">
				<div class="stat-l">胜率</div>
				<div class="stat-v">{stats.winRate}%</div>
			</div>
		</div>

		<!-- Profit Bar -->
		<div class="section">
			<h3>💰 资金表现</h3>
			<div class="profit-bar-bg">
				<div class="profit-bar-fill" style="width:{profitBarPct(stats.profitPercent)}%;background:{stats.totalProfit >= 0 ? '#2e7d32' : '#c62828'}"></div>
			</div>
			<div class="profit-stats">
				<div>总投注: {stats.totalBets} 笔 | 胜: {stats.wins} | 负: {stats.losses}</div>
				<div>盈亏: {stats.totalProfit} 元 ({stats.profitPercent}%)</div>
			</div>
		</div>

		<!-- Confidence Distribution -->
		<div class="section">
			<h3>🔮 信心分布</h3>
			<div class="dist-bar">
				<div class="dist-s high" style="width:{(confidenceDist.high / totalConf) * 100}%">
					{confidenceDist.high > 0 ? Math.round((confidenceDist.high / totalConf) * 100) + '%' : ''}
				</div>
				<div class="dist-s med" style="width:{(confidenceDist.medium / totalConf) * 100}%">
					{confidenceDist.medium > 0 ? Math.round((confidenceDist.medium / totalConf) * 100) + '%' : ''}
				</div>
				<div class="dist-s low" style="width:{(confidenceDist.low / totalConf) * 100}%">
					{confidenceDist.low > 0 ? Math.round((confidenceDist.low / totalConf) * 100) + '%' : ''}
				</div>
			</div>
			<div class="dist-labels">
				<span>🟢 高 {confidenceDist.high}</span>
				<span>🟡 中 {confidenceDist.medium}</span>
				<span>🔴 低 {confidenceDist.low}</span>
			</div>
		</div>

		<!-- Recommendations -->
		<div class="section">
			<h3>💡 推荐汇总</h3>
			<div class="rec-s">
				<div class="rec-item strong">💪 强烈建议: {recDist.strong}</div>
				<div class="rec-item moderate">⚡ 建议关注: {recDist.moderate}</div>
				<div class="rec-item over">⚽ 小球推荐: {recDist.over}</div>
				<div class="rec-item avoid">🚫 避免下注: {recDist.avoid}</div>
			</div>
		</div>

		<!-- Model Info -->
		<div class="section">
			<h3>🧠 预测模型说明</h3>
			<div class="model-info">
				<div class="factor">
					<div class="factor-bar" style="width:35%"><strong>实力评级 35%</strong></div>
					<p>基于FIFA排名、阵容深度、历史战绩的综合实力评分</p>
				</div>
				<div class="factor">
					<div class="factor-bar" style="width:20%"><strong>近期状态 20%</strong></div>
					<p>近10场比赛战绩加权 (近期权重更高)</p>
				</div>
				<div class="factor">
					<div class="factor-bar news" style="width:20%"><strong>新闻/伤病 20%</strong></div>
					<p>NLP情感分析 + 伤病信息 + 转会动态</p>
				</div>
				<div class="factor">
					<div class="factor-bar market" style="width:15%"><strong>市场赔率 15%</strong></div>
					<p>融合The Odds API多家博彩公司赔率，去水后计算公平概率</p>
				</div>
				<div class="factor">
					<div class="factor-bar h2h" style="width:10%"><strong>对阵历史 10%</strong></div>
					<p>世界杯在 neutral venue 进行，但考虑球迷主场优势</p>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.stats-page { max-width: 800px; margin: 0 auto; }
	.stats-page h2 { color: #1e88e5; text-align: center; margin-bottom: 16px; }
	.section { background: #141822; border: 1px solid #1e2433; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
	.section h3 { margin: 0 0 12px; color: #1e88e5; font-size: 15px; }
	.stat-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
	.stat-card { text-align: center; background: #1a1f2e; border-radius: 8px; padding: 16px; }
	.stat-l { font-size: 12px; color: #8899aa; }
	.stat-v { font-size: 24px; font-weight: bold; margin-top: 4px; }
	.profit-bar-bg { height: 24px; background: #1a1f2e; border-radius: 4px; overflow: hidden; }
	.profit-bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s; }
	.profit-stats { font-size: 13px; color: #8899aa; margin-top: 8px; line-height: 1.8; }
	.dist-bar { display: flex; height: 28px; border-radius: 4px; overflow: hidden; margin-bottom: 8px; }
	.dist-s { display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; color: #fff; }
	.dist-s.high { background: #2e7d32; }
	.dist-s.med { background: #f57f17; }
	.dist-s.low { background: #c62828; }
	.dist-labels { display: flex; gap: 16px; font-size: 12px; color: #8899aa; }
	.rec-s { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
	.rec-item { padding: 10px; border-radius: 6px; text-align: center; font-size: 13px; }
	.rec-item.strong { background: #2e7d32; color: #fff; }
	.rec-item.moderate { background: #f57f17; color: #000; }
	.rec-item.over { background: #1565c0; color: #fff; }
	.rec-item.avoid { background: #c62828; color: #fff; }
	.model-info { display: flex; flex-direction: column; gap: 10px; }
	.factor { background: #1a1f2e; border-radius: 6px; padding: 10px 12px; }
	.factor-bar { background: #1e88e5; height: 24px; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; color: #fff; margin-bottom: 4px; }
	.factor-bar.news { background: #9c27b0; }
	.factor-bar.market { background: #ff9800; }
	.factor-bar.h2h { background: #00bcd4; }
	.factor p { font-size: 12px; color: #8899aa; margin: 0; }
	.loading { text-align: center; padding: 80px 0; }
	.spinner { font-size: 48px; animation: spin 1s linear infinite; display: inline-block; }
	@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
	.loading p { color: #8899aa; margin-top: 12px; }
	@media (max-width: 600px) {
		.stat-cards { grid-template-columns: 1fr 1fr; }
		.rec-s { grid-template-columns: 1fr; }
	}
</style>
