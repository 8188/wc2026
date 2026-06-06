<script lang="ts">
	import { onMount } from 'svelte';
	import {
		fetchPredictions, fetchBettingStats, fetchPendingBets, fetchBetHistory,
		placeBet, settleBet, resetBetting,
		type Prediction, type BettingStats, type BetResult, type BookmakerOddsEntry
	} from '$lib/api';

	let predictions = $state<Prediction[]>([]);
	let stats = $state<BettingStats>({
		bankroll: 10000, startBankroll: 10000, totalBets: 0,
		wins: 0, losses: 0, winRate: 0, roi: 0, totalProfit: 0, profitPercent: 0, pending: 0
	});
	let pendingBets = $state<BetResult[]>([]);
	let history = $state<BetResult[]>([]);
	let loading = $state(true);
	let message = $state('');

	let selectedMatchId = $state<number | null>(null);
	let betType = $state<'1x2' | 'spread' | 'over_under' | 'btts'>('1x2');
	let selection = $state<string>('home');
	let spreadLine = $state<number>(-0.5);
	let totalLine = $state<number>(2.5);
	let stake = $state(100);

	onMount(async () => {
		try {
			const [pData, statsData, pending, hist] = await Promise.all([
				fetchPredictions(), fetchBettingStats(), fetchPendingBets(), fetchBetHistory()
			]);
			predictions = pData;
			stats = statsData;
			pendingBets = pending;
			history = Array.isArray(hist) ? hist : [];
		} catch (e) {
			console.error('Failed to load betting data:', e);
		}
		loading = false;
	});

	let selectedPred = $derived(
		selectedMatchId ? predictions.find((p) => p.matchId === selectedMatchId) : null
	);

	let currentOdds = $derived.by(() => {
		if (!selectedPred) return 0;
		if (betType === '1x2') {
			return getFairOdds(selection);
		}
		// Try to get odds from bookmaker data
		const bkEntries = Object.values(selectedPred.bookmakerOdds || {});
		if (bkEntries.length === 0) return getFairOdds(selection);

		const bk = bkEntries[0];
		if (betType === 'over_under') {
			if (totalLine === 2.5) return selection === 'over' ? (bk.over25 || 0) : (bk.under25 || 0);
			if (totalLine === 1.5) return selection === 'over' ? (bk.over15 || 0) : (bk.under15 || 0);
		}
		if (betType === 'btts') {
			return selection === 'btts_yes' ? (bk.bttsYes || 0) : (bk.bttsNo || 0);
		}
		if (betType === 'spread' && bk.spread) {
			return selection === 'home' ? (bk.spread.home || 0) : (bk.spread.away || 0);
		}
		return getFairOdds(selection);
	});

	function getFairOdds(sel: string) {
		if (!selectedPred) return 0;
		const fo = selectedPred.fairOdds;
		return sel === 'home' ? fo.home : sel === 'draw' ? fo.draw : fo.away;
	}

	function getBookmakerName(): string {
		if (!selectedPred) return '';
		const bkEntries = Object.values(selectedPred.bookmakerOdds || {});
		return bkEntries.length > 0 ? bkEntries[0].name : '';
	}

	async function handlePlaceBet() {
		if (!selectedPred) {
			message = '❌ 请选择一场比赛';
			return;
		}
		const odds = currentOdds;
		if (!odds || odds <= 0) {
			message = '❌ 无法获取赔率';
			return;
		}
		try {
			const result = await placeBet(
				selectedPred.matchId,
				selection,
				odds,
				stake,
				betType,
				betType === 'spread' ? spreadLine : null,
				betType === 'over_under' ? totalLine : null,
				getBookmakerName()
			);
			stats.bankroll = result.bankroll;
			pendingBets.unshift(result);
			message = `✅ 下注成功! ${result.selectionLabel} @ ${odds} | 注额 ${stake} | 预计回报 ${result.potentialReturn}`;
			stake = 100;
		} catch (e) {
			message = `❌ ${(e as Error).message}`;
		}
		setTimeout(() => (message = ''), 5000);
	}

	async function handleSettle(betId: number, result: 'won' | 'lost') {
		try {
			const r = await settleBet(betId, result);
			pendingBets = pendingBets.filter((b) => b.id !== betId);
			stats.bankroll = r.bankroll;
			message = result === 'won' ? `🎉 赢了! +${r.profit} 元` : '😢 输了';
			const [newStats, newHist] = await Promise.all([fetchBettingStats(), fetchBetHistory()]);
			stats = newStats;
			history = Array.isArray(newHist) ? newHist : [];
		} catch (e) {
			message = `❌ ${(e as Error).message}`;
		}
		setTimeout(() => (message = ''), 5000);
	}

	async function handleReset() {
		try {
			await resetBetting();
			const [newStats, pending, hist] = await Promise.all([
				fetchBettingStats(), fetchPendingBets(), fetchBetHistory()
			]);
			stats = newStats;
			pendingBets = pending;
			history = Array.isArray(hist) ? hist : [];
			message = '💰 资金已重置为 10000 元';
		} catch (e) {
			message = `❌ ${(e as Error).message}`;
		}
		setTimeout(() => (message = ''), 3000);
	}

	function betTypeLabel(t: string) {
		const map: Record<string, string> = { '1x2': '胜平负', spread: '让球盘', over_under: '大小球', btts: '双方进球' };
		return map[t] || t;
	}
	function selectionLabel(s: string) {
		const map: Record<string, string> = {
			home: '🏠 主胜', draw: '🤝 平局', away: '✈️ 客胜',
			over: '📈 大球', under: '📉 小球',
			btts_yes: '⚽ 双方进球', btts_no: '🚫 双方不进球'
		};
		return map[s] || s;
	}
	function profitColor(p: number) {
		return p > 0 ? '#4caf50' : p < 0 ? '#f44336' : '#888';
	}

	// When betType changes, reset selection
	function changeBetType(t: typeof betType) {
		betType = t;
		if (t === '1x2') selection = 'home';
		else if (t === 'over_under') selection = 'over';
		else if (t === 'btts') selection = 'btts_yes';
		else if (t === 'spread') selection = 'home';
	}
</script>

<svelte:head>
	<title>模拟下注 - WC2026</title>
</svelte:head>

<div class="betting-page">
	<!-- Bankroll -->
	<div class="bankroll-display">
		<div class="bankroll-amount">💰 {Math.round(stats.bankroll * 100) / 100} 元</div>
		<div class="bankroll-change" style="color:{stats.totalProfit >= 0 ? '#4caf50' : '#f44336'}">
			{stats.totalProfit >= 0 ? '📈' : '📉'} {stats.totalProfit} 元 ({stats.profitPercent}%)
		</div>
		<div class="bankroll-meta">
			胜 {stats.wins} / 负 {stats.losses} / 胜率 {stats.winRate}% / ROI {stats.roi}%
		</div>
		<button class="reset-btn" onclick={handleReset}>🔄 重置资金</button>
	</div>

	{#if message}
		<div class="message">{message}</div>
	{/if}

	<!-- Place Bet Form -->
	<div class="section">
		<h3>💰 模拟下注</h3>
		<div class="fg">
			<label>选择比赛</label>
			<select bind:value={selectedMatchId}>
				<option value={null}>-- 请选择一场比赛 --</option>
				{#each predictions.filter((p) => p.prediction).sort((a, b) => a.matchId - b.matchId) as pred}
					<option value={pred.matchId}>
						{pred.match} | {pred.predictedScore} | {pred.confidence === 'high' ? '高' : pred.confidence === 'medium' ? '中' : '低'}信心
					</option>
				{/each}
			</select>
		</div>

		<!-- Bet Type Tabs -->
		<div class="fg">
			<label>选择玩法</label>
			<div class="type-tabs">
				<button class:active={betType === '1x2'} onclick={() => changeBetType('1x2')}>胜平负</button>
				<button class:active={betType === 'spread'} onclick={() => changeBetType('spread')}>让球盘</button>
				<button class:active={betType === 'over_under'} onclick={() => changeBetType('over_under')}>大小球</button>
				<button class:active={betType === 'btts'} onclick={() => changeBetType('btts')}>双方进球</button>
			</div>
		</div>

		<!-- Selection Buttons based on bet type -->
		<div class="fg">
			{#if betType === '1x2'}
				<div class="sel-btns">
					<button class:active={selection === 'home'} onclick={() => (selection = 'home')}>🏠 主胜</button>
					<button class:active={selection === 'draw'} onclick={() => (selection = 'draw')}>🤝 平局</button>
					<button class:active={selection === 'away'} onclick={() => (selection = 'away')}>✈️ 客胜</button>
				</div>
			{:else if betType === 'spread'}
				<div class="spread-row">
					<select bind:value={spreadLine} class="line-select">
						<option value={-2}>主让2球</option>
						<option value={-1.5}>主让1.5球</option>
						<option value={-1}>主让1球</option>
						<option value={-0.5}>主让0.5球</option>
						<option value={0}>平手盘</option>
						<option value={0.5}>客让0.5球</option>
						<option value={1}>客让1球</option>
					</select>
					<div class="sel-btns">
						<button class:active={selection === 'home'} onclick={() => (selection = 'home')}>主队</button>
						<button class:active={selection === 'away'} onclick={() => (selection = 'away')}>客队</button>
					</div>
				</div>
			{:else if betType === 'over_under'}
				<div class="spread-row">
					<select bind:value={totalLine} class="line-select">
						<option value={1.5}>1.5 球</option>
						<option value={2.5}>2.5 球</option>
					</select>
					<div class="sel-btns">
						<button class:active={selection === 'over'} onclick={() => (selection = 'over')}>📈 大球</button>
						<button class:active={selection === 'under'} onclick={() => (selection = 'under')}>📉 小球</button>
					</div>
				</div>
			{:else if betType === 'btts'}
				<div class="sel-btns">
					<button class:active={selection === 'btts_yes'} onclick={() => (selection = 'btts_yes')}>⚽ 双方都进球</button>
					<button class:active={selection === 'btts_no'} onclick={() => (selection = 'btts_no')}>🚫 至少一方不进球</button>
				</div>
			{/if}
		</div>

		<div class="fg">
			<label>下注金额</label>
			<input type="range" bind:value={stake} min="10" max="500" step="10" />
			<span class="stake-val">{stake} 元</span>
		</div>

		{#if selectedPred}
			<div class="bet-preview">
				<div class="pv-match">{selectedPred.match}</div>
				<div class="pv-info">
					玩法: {betTypeLabel(betType)} | 选择: {selectionLabel(selection)}
					{#if betType === 'spread'} | 让球线: {spreadLine > 0 ? '+' : ''}{spreadLine}{/if}
					{#if betType === 'over_under'} | 盘口: {totalLine}球{/if}
				</div>
				<div class="pv-odds">
					赔率: {currentOdds > 0 ? currentOdds.toFixed(2) : 'N/A'}
					{#if getBookmakerName()}<span class="pv-bk">({getBookmakerName()})</span>{/if}
				</div>
				<div class="pv-return">预计回报: {currentOdds > 0 ? Math.round(stake * currentOdds * 100) / 100 : 0} 元</div>
			</div>
		{/if}
		<button class="place-btn" onclick={handlePlaceBet}>🎯 确认下注</button>
	</div>

	<!-- Pending Bets -->
	<div class="section">
		<h3>⏳ 待结算 ({pendingBets.length})</h3>
		{#if pendingBets.length === 0}
			<p class="empty">暂无待结算投注</p>
		{:else}
			{#each pendingBets as bet (bet.id)}
				<div class="bet-item">
					<div class="bet-info">
						<div class="bm">{bet.matchLabel}</div>
						<div class="bd">
							<span class="bt">{betTypeLabel(bet.betType)}</span>
							<span>{bet.selectionLabel || selectionLabel(bet.selection)}</span>
							{#if bet.spreadLine != null}<span>{bet.spreadLine > 0 ? '+' : ''}{bet.spreadLine}</span>{/if}
							{#if bet.totalLine != null}<span>{bet.totalLine}球</span>{/if}
							<span>赔率: {bet.odds}</span>
							<span class="bs">注额: {bet.stake}</span>
							<span>回报: {bet.potentialReturn}</span>
						</div>
					</div>
					<div class="ba">
						<button class="win-b" onclick={() => handleSettle(bet.id, 'won')}>✅ 赢了</button>
						<button class="lose-b" onclick={() => handleSettle(bet.id, 'lost')}>❌ 输了</button>
					</div>
				</div>
			{/each}
		{/if}
	</div>

	<!-- History -->
	<div class="section">
		<h3>📜 投注记录 ({history.length})</h3>
		{#if history.length === 0}
			<p class="empty">暂无投注记录</p>
		{:else}
			{#each history as h}
				<div class="history-item">
					<span class="hr {(h as any).result}">{(h as any).result === 'won' ? '✅' : '❌'}</span>
					<div class="hi">
						<div class="hm">{(h as any).matchLabel}</div>
						<div class="hd">
							<span class="bt">{betTypeLabel((h as any).betType || '1x2')}</span>
							{(h as any).selectionLabel} @ {h.odds} | 注额 {h.stake}
						</div>
					</div>
					<div class="hp" style="color:{profitColor(h.profit)}">
						{h.profit > 0 ? '+' : ''}{h.profit}
					</div>
				</div>
			{/each}
		{/if}
	</div>
</div>

<style>
	.betting-page { max-width: 720px; margin: 0 auto; }
	.bankroll-display { text-align: center; background: linear-gradient(135deg, #1a2332, #0d1117); border: 2px solid #1e88e5; border-radius: 12px; padding: 20px; margin-bottom: 16px; }
	.bankroll-amount { font-size: 36px; font-weight: bold; color: #4caf50; }
	.bankroll-change { font-size: 14px; margin-top: 4px; }
	.bankroll-meta { font-size: 12px; color: #8899aa; margin-top: 6px; }
	.reset-btn { background: #2a3040; border: 1px solid #3a4050; color: #aaa; padding: 6px 16px; border-radius: 4px; cursor: pointer; margin-top: 8px; }
	.message { background: #1a2332; border: 1px solid #1e88e5; border-radius: 6px; padding: 12px; margin: 12px 0; text-align: center; }
	.section { background: #141822; border: 1px solid #1e2433; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
	.section h3 { margin: 0 0 12px; color: #1e88e5; }
	.fg { margin-bottom: 12px; }
	.fg label { display: block; font-size: 13px; color: #8899aa; margin-bottom: 4px; }
	.fg select, .line-select { width: 100%; padding: 8px; background: #1a1f2e; border: 1px solid #2a3040; border-radius: 4px; color: #e0e0e0; }
	.line-select { width: auto; min-width: 140px; }
	.type-tabs { display: flex; gap: 6px; }
	.type-tabs button { flex: 1; padding: 8px 6px; background: #1a1f2e; border: 1px solid #2a3040; border-radius: 6px; color: #8899aa; cursor: pointer; font-size: 13px; transition: all 0.2s; }
	.type-tabs button.active { background: #1565c0; border-color: #1565c0; color: #fff; font-weight: bold; }
	.type-tabs button:hover:not(.active) { background: #2a3040; color: #fff; }
	.sel-btns { display: flex; gap: 8px; }
	.sel-btns button { flex: 1; padding: 10px; background: #1a1f2e; border: 1px solid #2a3040; border-radius: 6px; color: #aaa; cursor: pointer; font-size: 13px; }
	.sel-btns button.active { background: #1e88e5; border-color: #1e88e5; color: #fff; }
	.spread-row { display: flex; gap: 10px; align-items: center; }
	input[type="range"] { width: 100%; accent-color: #1e88e5; }
	.stake-val { display: block; text-align: center; color: #1e88e5; font-weight: bold; font-size: 18px; margin-top: 4px; }
	.bet-preview { background: #1a1f2e; border-radius: 6px; padding: 12px; margin: 12px 0; }
	.pv-match { font-weight: bold; font-size: 14px; }
	.pv-info { font-size: 13px; color: #8899aa; margin-top: 4px; }
	.pv-odds { font-size: 14px; color: #ffd54f; font-weight: bold; margin-top: 4px; }
	.pv-bk { font-size: 11px; color: #1e88e5; font-weight: normal; }
	.pv-return { color: #4caf50; font-weight: bold; margin-top: 4px; }
	.place-btn { width: 100%; padding: 14px; background: linear-gradient(135deg, #2e7d32, #1b5e20); border: none; border-radius: 8px; color: #fff; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 12px; }
	.place-btn:hover { background: linear-gradient(135deg, #388e3c, #2e7d32); }
	.empty { color: #556; text-align: center; padding: 20px 0; font-size: 13px; }
	.bet-item { display: flex; justify-content: space-between; align-items: center; background: #1a1f2e; border-radius: 6px; padding: 12px; margin-bottom: 8px; }
	.bet-info { flex: 1; }
	.bm { font-weight: bold; font-size: 14px; }
	.bd { display: flex; gap: 10px; margin-top: 4px; font-size: 12px; color: #8899aa; flex-wrap: wrap; }
	.bs { color: #1e88e5; font-weight: bold; }
	.bt { background: #1565c0; color: #fff; padding: 1px 6px; border-radius: 3px; font-size: 10px; font-weight: bold; }
	.ba { display: flex; gap: 6px; }
	.win-b { background: #2e7d32; border: none; color: #fff; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; }
	.lose-b { background: #c62828; border: none; color: #fff; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; }
	.history-item { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid #1a1f2e; }
	.hr { font-size: 12px; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
	.hr.won { background: #2e7d32; color: #fff; }
	.hr.lost { background: #c62828; color: #fff; }
	.hi { flex: 1; }
	.hm { font-size: 13px; font-weight: bold; }
	.hd { font-size: 12px; color: #8899aa; display: flex; gap: 8px; align-items: center; }
	.hp { font-weight: bold; font-size: 16px; }
</style>
