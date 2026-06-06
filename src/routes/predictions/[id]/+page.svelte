<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import {
		fetchPrediction, fetchOddsComparison, fetchNews,
		teamName, teamFlag, stageLabel, TEAMS,
		type Prediction, type OddsComparison, type TeamNewsResponse, type BookmakerOddsEntry
	} from '$lib/api';

	let pred = $state<Prediction | null>(null);
	let comparison = $state<OddsComparison | null>(null);
	let homeNews = $state<TeamNewsResponse | null>(null);
	let awayNews = $state<TeamNewsResponse | null>(null);
	let loading = $state(true);
	let error = $state('');
	let activeTab = $state<'odds' | 'scores' | 'news'>('odds');

	onMount(async () => {
		const matchId = Number(page.params.id);
		if (!matchId || isNaN(matchId)) {
			error = '无效的比赛ID';
			loading = false;
			return;
		}
		try {
			pred = await fetchPrediction(matchId);
		} catch (e) {
			error = (e as Error).message;
		}
		// Load non-critical data in parallel
		const [comp] = await Promise.allSettled([
			fetchOddsComparison(matchId),
		]);
		if (comp.status === 'fulfilled') comparison = comp.value;

		// Load news for both teams
		if (pred) {
			const homeCode = findCode(pred.homeName);
			const awayCode = findCode(pred.awayName);
			const newsPromises: Promise<void>[] = [];
			if (homeCode) {
				newsPromises.push(
					fetchNews(homeCode).then((d) => { homeNews = d; }).catch(() => {})
				);
			}
			if (awayCode) {
				newsPromises.push(
					fetchNews(awayCode).then((d) => { awayNews = d; }).catch(() => {})
				);
			}
			await Promise.allSettled(newsPromises);
		}
		loading = false;
	});

	function findCode(name: string): string | null {
		for (const [code, data] of Object.entries(TEAMS)) {
			if (data.name === name) return code;
		}
		return null;
	}

	function recClass(action: string) {
		if (action.includes('STRONG')) return 'strong';
		if (action.includes('MODERATE')) return 'moderate';
		if (action.includes('OVER')) return 'over';
		return 'avoid';
	}
	function stakeLabel(s: string) {
		const map: Record<string, string> = {
			high: '高注 (5-10% 资金)',
			medium: '中注 (2-5%)',
			low: '小注 (<2%)',
			none: '不注'
		};
		return map[s] || s;
	}
	function impColor(imp: string) {
		return imp === 'high' ? '#f44336' : imp === 'medium' ? '#ff9800' : '#666';
	}
	function catIcon(cat: string) {
		const map: Record<string, string> = { injury: '🏥', transfer: '💼', form: '📈', tactical: '📋', general: '📰' };
		return map[cat] || '📰';
	}
	function scoreColor(prob: number) {
		if (prob > 0.12) return '#4caf50';
		if (prob > 0.07) return '#ff9800';
		return '#666';
	}
</script>

<svelte:head>
	<title>{pred ? pred.match : '加载中'} - 预测详情</title>
</svelte:head>

<div class="detail">
	<a href="/predictions" class="back-btn">← 返回预测列表</a>

	{#if loading}
		<div class="loading">
			<div class="spinner">⏳</div>
			<p>加载预测数据中...</p>
		</div>
	{:else if error}
		<div class="error">❌ {error}</div>
	{:else if !pred}
		<div class="empty">预测数据不存在</div>
	{:else}
		<!-- Match Header -->
		<div class="match-header-detail">
			<div class="team-detail home">
				<span class="flag-lg">⚽</span>
				<h2>{pred.homeName}</h2>
			</div>
			<div class="center-info">
				<div class="stage-tag">{stageLabel(pred.stage)}</div>
				<div class="venue">{pred.venue}</div>
				{#if pred.date}<div class="date">{pred.date}</div>{/if}
			</div>
			<div class="team-detail away">
				<span class="flag-lg">⚽</span>
				<h2>{pred.awayName}</h2>
			</div>
		</div>

		<!-- Prediction Summary -->
		<div class="section">
			<h3>🔮 预测分析</h3>
			<div class="prob-bar">
				<div class="bar-seg home" style="width:{pred.prediction.home * 100}%">
					{Math.round(pred.prediction.home * 100)}%
				</div>
				<div class="bar-seg draw" style="width:{pred.prediction.draw * 100}%">
					{Math.round(pred.prediction.draw * 100)}%
				</div>
				<div class="bar-seg away" style="width:{pred.prediction.away * 100}%">
					{Math.round(pred.prediction.away * 100)}%
				</div>
			</div>
			<div class="prob-labels">
				<span>🏠 {pred.homeName}胜</span>
				<span>🤝 平局</span>
				<span>✈️ {pred.awayName}胜</span>
			</div>
			<div class="pred-summary">
				<div class="pred-box">
					<div class="label">预测比分</div>
					<div class="value">{pred.predictedScore}</div>
				</div>
				<div class="pred-box">
					<div class="label">信心等级</div>
					<div class="value">{pred.confidence === 'high' ? '🟢 高' : pred.confidence === 'medium' ? '🟡 中' : '🔴 低'}</div>
				</div>
				<div class="pred-box">
					<div class="label">公平赔率</div>
					<div class="value small">主{pred.fairOdds.home} / 平{pred.fairOdds.draw} / 客{pred.fairOdds.away}</div>
				</div>
				{#if pred.handicapRec}
					<div class="pred-box">
						<div class="label">推荐让球</div>
						<div class="value small">{pred.handicapRec.label}</div>
					</div>
				{/if}
			</div>

			<!-- Market Expected Goals -->
			{#if pred.marketExpectedGoals}
				<div class="xg-box">
					<div class="xg-title">期望进球 (xG)</div>
					<div class="xg-row">
						<span class="xg-label">模型预测</span>
						<span class="xg-home">{pred.marketExpectedGoals.home}</span>
						<span class="xg-sep">-</span>
						<span class="xg-away">{pred.marketExpectedGoals.away}</span>
						<span class="xg-total">总 {pred.marketExpectedGoals.total}</span>
					</div>
					{#if pred.marketExpectedGoals.marketHome}
						<div class="xg-row market">
							<span class="xg-label">市场隐含</span>
							<span class="xg-home">{pred.marketExpectedGoals.marketHome}</span>
							<span class="xg-sep">-</span>
							<span class="xg-away">{pred.marketExpectedGoals.marketAway}</span>
							<span class="xg-total">总 {pred.marketExpectedGoals.marketTotal}</span>
						</div>
					{/if}
				</div>
			{/if}
		</div>

		<!-- Tab Navigation -->
		<div class="tabs">
			<button class:active={activeTab === 'odds'} onclick={() => activeTab = 'odds'}>📊 博彩赔率对比</button>
			<button class:active={activeTab === 'scores'} onclick={() => activeTab = 'scores'}>⚽ 比分预测</button>
			<button class:active={activeTab === 'news'} onclick={() => activeTab = 'news'}>📰 关键资讯</button>
		</div>

		<!-- Tab: Bookmaker Odds Comparison -->
		{#if activeTab === 'odds'}
			<div class="section">
				<h3>📊 多博彩公司赔率对比</h3>
				{#if comparison && comparison.bookmakers.length > 0}
					<p class="source-info">
						数据来源: {comparison.bookmakers.map((b) => b.name).join(', ')}
						{#if comparison.lastUpdated}
							| 更新于 {new Date(comparison.lastUpdated).toLocaleString('zh-CN')}
						{/if}
					</p>
					<div class="odds-table-wrap">
						<table class="odds-table">
							<thead>
								<tr>
									<th>博彩公司</th>
									<th>主胜</th>
									<th>平局</th>
									<th>客胜</th>
									<th>大2.5</th>
									<th>小2.5</th>
									<th>双方进球</th>
									<th>让球</th>
								</tr>
							</thead>
							<tbody>
								{#each comparison.bookmakers as bk}
									<tr>
										<td class="bk-name">{bk.name}</td>
										<td class="odds-cell">{bk.outcome.home?.toFixed(2) || '-'}</td>
										<td class="odds-cell">{bk.outcome.draw?.toFixed(2) || '-'}</td>
										<td class="odds-cell">{bk.outcome.away?.toFixed(2) || '-'}</td>
										<td class="odds-cell">{bk.over25?.toFixed(2) || '-'}</td>
										<td class="odds-cell">{bk.under25?.toFixed(2) || '-'}</td>
										<td class="odds-cell">{bk.bttsYes?.toFixed(2) || '-'}</td>
										<td class="odds-cell">
											{#if bk.spread}
												{bk.spread.line > 0 ? '+' : ''}{bk.spread.line} ({bk.spread.home?.toFixed(2) || '-'})
											{:else}
												-
											{/if}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>

					<!-- Best odds highlight -->
					{#if comparison.bestOdds}
						<div class="best-odds">
							<h4>🏆 最佳赔率</h4>
							<div class="best-grid">
								{#each Object.entries(comparison.bestOdds).filter(([, v]) => v) as [key, val]}
									<div class="best-item">
										<span class="best-label">{key === 'home' ? '主胜' : key === 'draw' ? '平局' : key === 'away' ? '客胜' : key === 'over25' ? '大2.5' : key === 'under25' ? '小2.5' : 'BTTS'}</span>
										<span class="best-odds-val">{val.odds.toFixed(2)}</span>
										<span class="best-bk">@ {val.bookie}</span>
									</div>
								{/each}
							</div>
						</div>
					{/if}
				{:else}
					<div class="empty-data">
						<p>暂无博彩赔率数据</p>
						<p class="hint">该赛事暂无博彩赔率数据，请稍后刷新重试</p>
					</div>
				{/if}
			</div>
		{/if}

		<!-- Tab: Top Scores -->
		{#if activeTab === 'scores'}
			<div class="section">
				<h3>⚽ Top 5 最可能比分</h3>
				{#if pred.topScores && pred.topScores.length > 0}
					<div class="scores-grid">
						{#each pred.topScores as s, i}
							<div class="score-card" style="border-left: 4px solid {scoreColor(s.probability)}">
								<div class="score-rank">#{i + 1}</div>
								<div class="score-val">{s.score}</div>
								<div class="score-prob" style="color: {scoreColor(s.probability)}">
									{(s.probability * 100).toFixed(1)}%
								</div>
								<div class="score-bar" style="width:{s.probability * 500}%; background:{scoreColor(s.probability)}"></div>
							</div>
						{/each}
					</div>
				{:else}
					<p class="empty-data">无比分预测数据</p>
				{/if}
			</div>
		{/if}

		<!-- Tab: News -->
		{#if activeTab === 'news'}
			<div class="section">
				<h3>📰 关键资讯</h3>

				{#if homeNews && homeNews.injuries.length > 0}
					<h4>🏥 {pred.homeName} 伤停</h4>
					<div class="injury-list">
						{#each homeNews.injuries as inj}
							<div class="injury-item {inj.status.toLowerCase()}">
								<span class="inj-status">{inj.status}</span>
								<span class="inj-name">{inj.player}</span>
								<span class="inj-pos">({inj.position})</span>
								{#if inj.reason}<span class="inj-reason">{inj.reason}</span>{/if}
							</div>
						{/each}
					</div>
				{/if}

				{#if awayNews && awayNews.injuries.length > 0}
					<h4>🏥 {pred.awayName} 伤停</h4>
					<div class="injury-list">
						{#each awayNews.injuries as inj}
							<div class="injury-item {inj.status.toLowerCase()}">
								<span class="inj-status">{inj.status}</span>
								<span class="inj-name">{inj.player}</span>
								<span class="inj-pos">({inj.position})</span>
								{#if inj.reason}<span class="inj-reason">{inj.reason}</span>{/if}
							</div>
						{/each}
					</div>
				{/if}

				<!-- News -->
				{#each [homeNews, awayNews] as newsData, idx}
					{#if newsData && newsData.news.length > 0}
						<h4>{idx === 0 ? pred.homeName : pred.awayName} 新闻</h4>
						<div class="news-list">
							{#each newsData.news as n}
								<div class="news-item">
									<span class="news-cat">{catIcon(n.category)}</span>
									<span class="news-imp" style="color:{impColor(n.importance)}">●</span>
									<a href={n.url || '#'} class="news-title" target="_blank" rel="noopener noreferrer">{n.headline}</a>
									<span class="news-meta">{n.source} · {n.date || ''}</span>
								</div>
							{/each}
						</div>
					{/if}
				{/each}

				{#if (!homeNews || (homeNews.news.length === 0 && homeNews.injuries.length === 0)) && (!awayNews || (awayNews.news.length === 0 && awayNews.injuries.length === 0))}
					<div class="empty-data">
						<p>暂无相关资讯</p>
						<p class="hint">该球队暂无新闻资讯，世界杯开赛后将有更多伤停和赛事动态</p>
					</div>
				{/if}
			</div>
		{/if}

		<!-- Recommendation -->
		<div class="section">
			<h3>💡 投注建议</h3>
			<div class="rec-box">
				<div class="rec-action {recClass(pred.recommendation.action)}">
					{pred.recommendation.action}
				</div>
				<p class="rec-reason">{pred.recommendation.reason}</p>
				<div class="stake-level">建议注额: {stakeLabel(pred.recommendation.stake)}</div>
			</div>
		</div>

		<!-- Value Bets -->
		{#if pred.valueBets.length > 0}
			<div class="section">
				<h3>🎯 价值投注机会 ({pred.valueBets.length})</h3>
				<div class="value-list">
					{#each [...pred.valueBets].sort((a: {value: number}, b: {value: number}) => b.value - a.value) as bet}
						<div class="value-item">
							<span class="vi-market">{bet.market === '1x2' ? (bet.type === 'home' ? '🏠' : bet.type === 'away' ? '✈️' : '🤝') : bet.market === 'totals' ? '📊' : '⚽'}</span>
							<span class="vi-sel">{bet.type === 'home' ? pred.homeName + '胜' : bet.type === 'away' ? pred.awayName + '胜' : bet.type === 'draw' ? '平局' : bet.type === 'over25' ? '大2.5' : bet.type === 'under25' ? '小2.5' : bet.type === 'btts_yes' ? '双方进球' : bet.type}</span>
							<span class="vi-bk">{bet.bookie}</span>
							<span class="vi-odds">{bet.marketOdds}</span>
							<span class="vi-val" style="color:{bet.value > 0.08 ? '#4caf50' : '#ff9800'}">
								+{Math.round(bet.value * 100)}%
							</span>
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Factors -->
		<div class="section">
			<h3>📊 预测因子</h3>
			<div class="factors">
				<div class="factor">
					<div class="factor-label">实力差距: {Math.round(pred.factors.strength * 100)}%</div>
					<div class="factor-bar" style="width:{Math.abs(pred.factors.strength) * 100}%"></div>
				</div>
				<div class="factor">
					<div class="factor-label">近期状态: {Math.round(pred.factors.form * 100)}%</div>
					<div class="factor-bar form" style="width:{Math.abs(pred.factors.form) * 100}%"></div>
				</div>
				<div class="factor">
					<div class="factor-label">新闻面: {Math.round(pred.factors.news * 100)}%</div>
					<div class="factor-bar news" style="width:{Math.abs(pred.factors.news) * 100}%"></div>
				</div>
			</div>
		</div>

		<!-- Quick Bet Link -->
		<div class="bet-link">
			<a href="/betting?match={pred.matchId}" class="go-bet-btn">💰 前往模拟下注</a>
		</div>
	{/if}
</div>

<style>
	.detail { max-width: 960px; margin: 0 auto; }
	.back-btn { display: inline-block; background: #1e2433; border: 1px solid #2a3040; color: #aaa; padding: 6px 14px; border-radius: 6px; cursor: pointer; margin-bottom: 16px; font-size: 13px; text-decoration: none; }
	.back-btn:hover { background: #2a3040; color: #fff; }
	.match-header-detail { display: flex; align-items: center; justify-content: space-between; background: #141822; border-radius: 12px; padding: 24px; margin-bottom: 20px; border: 1px solid #1e2433; }
	.team-detail { text-align: center; flex: 1; }
	.team-detail h2 { margin: 8px 0 4px; font-size: 18px; }
	.flag-lg { font-size: 48px; }
	.center-info { text-align: center; padding: 0 24px; }
	.stage-tag { background: #1e88e5; color: #fff; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: bold; }
	.venue { margin-top: 8px; font-size: 12px; color: #556; }
	.date { font-size: 11px; color: #778; margin-top: 4px; }
	.section { background: #141822; border: 1px solid #1e2433; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
	.section h3 { margin: 0 0 12px; color: #1e88e5; font-size: 16px; }
	.prob-bar { display: flex; height: 32px; border-radius: 4px; overflow: hidden; margin: 8px 0; }
	.bar-seg { display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 13px; color: #fff; }
	.bar-seg.home { background: #2e7d32; }
	.bar-seg.draw { background: #f57f17; }
	.bar-seg.away { background: #c62828; }
	.prob-labels { display: flex; justify-content: space-between; font-size: 12px; color: #8899aa; }
	.pred-summary { display: flex; gap: 12px; margin-top: 12px; flex-wrap: wrap; }
	.pred-box { background: #1a1f2e; border-radius: 6px; padding: 12px 16px; text-align: center; flex: 1; min-width: 110px; }
	.pred-box .label { font-size: 11px; color: #8899aa; }
	.pred-box .value { font-size: 20px; font-weight: bold; color: #1e88e5; margin-top: 4px; }
	.pred-box .value.small { font-size: 13px; }

	/* xG box */
	.xg-box { background: #1a1f2e; border-radius: 6px; padding: 12px; margin-top: 12px; }
	.xg-title { font-size: 12px; color: #8899aa; margin-bottom: 8px; font-weight: bold; }
	.xg-row { display: flex; align-items: center; gap: 8px; font-size: 14px; padding: 4px 0; }
	.xg-row.market { color: #ff9800; }
	.xg-label { width: 70px; font-size: 11px; color: #778; }
	.xg-home, .xg-away { font-weight: bold; font-size: 18px; min-width: 30px; text-align: center; }
	.xg-sep { color: #556; }
	.xg-total { margin-left: auto; font-size: 12px; color: #8899aa; }

	/* Tabs */
	.tabs { display: flex; gap: 4px; margin-bottom: 16px; }
	.tabs button { flex: 1; padding: 10px 8px; background: #1a1f2e; border: 1px solid #2a3040; border-radius: 6px; color: #8899aa; cursor: pointer; font-size: 13px; transition: all 0.2s; }
	.tabs button.active { background: #1e88e5; border-color: #1e88e5; color: #fff; font-weight: bold; }
	.tabs button:hover:not(.active) { background: #2a3040; color: #fff; }

	/* Odds table */
	.source-info { font-size: 11px; color: #778; margin-bottom: 8px; }
	.odds-table-wrap { overflow-x: auto; }
	.odds-table { width: 100%; border-collapse: collapse; font-size: 13px; }
	.odds-table th { background: #1a1f2e; padding: 8px 6px; text-align: center; color: #8899aa; font-weight: 600; font-size: 11px; border-bottom: 1px solid #2a3040; }
	.odds-table td { padding: 8px 6px; text-align: center; border-bottom: 1px solid #1a1f2e; }
	.bk-name { text-align: left; font-weight: bold; color: #ccd; white-space: nowrap; }
	.odds-cell { color: #e0e0e0; font-family: monospace; }
	.best-odds { margin-top: 16px; background: #1a1f2e; border-radius: 6px; padding: 12px; }
	.best-odds h4 { margin: 0 0 8px; font-size: 14px; color: #ffd54f; }
	.best-grid { display: flex; gap: 12px; flex-wrap: wrap; }
	.best-item { background: #141822; padding: 8px 12px; border-radius: 6px; text-align: center; min-width: 80px; }
	.best-label { font-size: 11px; color: #8899aa; display: block; }
	.best-odds-val { font-size: 18px; font-weight: bold; color: #4caf50; }
	.best-bk { font-size: 10px; color: #1e88e5; display: block; }

	/* Scores */
	.scores-grid { display: flex; flex-direction: column; gap: 8px; }
	.score-card { display: flex; align-items: center; gap: 12px; background: #1a1f2e; padding: 12px 16px; border-radius: 6px; }
	.score-rank { font-size: 12px; color: #556; width: 24px; }
	.score-val { font-size: 24px; font-weight: bold; color: #e0e0e0; min-width: 50px; text-align: center; }
	.score-prob { font-size: 16px; font-weight: bold; min-width: 50px; }
	.score-bar { height: 8px; border-radius: 4px; min-width: 4px; }

	/* News */
	h4 { color: #ccd; font-size: 14px; margin: 16px 0 8px; }
	h4:first-of-type { margin-top: 0; }
	.injury-list { display: flex; flex-direction: column; gap: 4px; }
	.injury-item { display: flex; gap: 8px; align-items: center; padding: 6px 10px; background: #1a1f2e; border-radius: 4px; font-size: 13px; }
	.inj-status { padding: 2px 6px; border-radius: 3px; font-size: 10px; font-weight: bold; color: #fff; }
	.injury-item.out .inj-status { background: #c62828; }
	.injury-item.doubtful .inj-status { background: #f57f17; color: #000; }
	.injury-item.returning .inj-status { background: #1565c0; }
	.inj-name { font-weight: bold; }
	.inj-pos { color: #778; font-size: 11px; }
	.inj-reason { color: #8899aa; font-size: 11px; margin-left: auto; }
	.news-list { display: flex; flex-direction: column; gap: 6px; }
	.news-item { display: flex; gap: 8px; align-items: flex-start; padding: 8px 10px; background: #1a1f2e; border-radius: 4px; font-size: 13px; }
	.news-cat { font-size: 14px; }
	.news-imp { font-size: 10px; margin-top: 4px; }
	.news-title { color: #ccd; text-decoration: none; flex: 1; }
	.news-title:hover { color: #1e88e5; }
	.news-meta { font-size: 10px; color: #556; white-space: nowrap; }
	.empty-data { text-align: center; padding: 24px 0; color: #556; }
	.empty-data .hint { font-size: 12px; color: #778; margin-top: 4px; }

	/* Rec */
	.rec-box { background: #1a1f2e; border-radius: 8px; padding: 16px; }
	.rec-action { display: inline-block; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 14px; margin-bottom: 8px; }
	.rec-action.strong { background: #2e7d32; color: #fff; }
	.rec-action.moderate { background: #f57f17; color: #000; }
	.rec-action.over { background: #1565c0; color: #fff; }
	.rec-action.avoid { background: #c62828; color: #fff; }
	.rec-reason { color: #ccd; font-size: 14px; margin: 8px 0; }
	.stake-level { color: #ff9800; font-size: 13px; margin-top: 8px; }

	/* Factors */
	.factors { display: flex; flex-direction: column; gap: 10px; }
	.factor { background: #1a1f2e; border-radius: 6px; padding: 10px 12px; }
	.factor-label { font-size: 12px; color: #8899aa; margin-bottom: 4px; }
	.factor-bar { background: #1e88e5; height: 8px; border-radius: 4px; min-width: 4px; }
	.factor-bar.form { background: #f57f17; }
	.factor-bar.news { background: #9c27b0; }

	/* Value bets */
	.value-list { display: flex; flex-direction: column; gap: 6px; }
	.value-item { display: flex; gap: 8px; align-items: center; background: #1a1f2e; padding: 8px 12px; border-radius: 6px; font-size: 13px; }
	.vi-market { font-size: 16px; }
	.vi-sel { font-weight: bold; min-width: 80px; }
	.vi-bk { color: #1e88e5; min-width: 60px; }
	.vi-odds { color: #ffd54f; min-width: 40px; }
	.vi-val { font-weight: bold; margin-left: auto; }

	.bet-link { text-align: center; margin: 20px 0; }
	.go-bet-btn { display: inline-block; background: linear-gradient(135deg, #2e7d32, #1b5e20); padding: 12px 32px; border-radius: 8px; color: #fff; font-size: 16px; font-weight: bold; text-decoration: none; }
	.go-bet-btn:hover { background: linear-gradient(135deg, #388e3c, #2e7d32); }
	.loading { text-align: center; padding: 80px 0; }
	.spinner { font-size: 48px; animation: spin 1s linear infinite; display: inline-block; }
	@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
	.loading p { color: #8899aa; margin-top: 12px; }
	.error, .empty { color: #f44; text-align: center; padding: 60px 0; }
	@media (max-width: 600px) {
		.match-header-detail { flex-direction: column; gap: 12px; }
		.center-info { order: -1; }
		.odds-table { font-size: 11px; }
		.odds-table th, .odds-table td { padding: 4px 3px; }
	}
</style>
