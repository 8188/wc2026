<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchMatches, stageLabel, stageColor, teamName, teamFlag, type Match } from '$lib/api';

	let matches = $state<Match[]>([]);
	let loading = $state(true);
	let filterStage = $state('all');
	let searchQuery = $state('');

	onMount(async () => {
		try {
			const data = await fetchMatches();
			matches = data;
		} catch (e) {
			console.error('Failed to load matches:', e);
		}
		loading = false;
	});

	let filteredMatches = $derived.by(() => {
		let list = matches;
		if (filterStage === 'group') list = list.filter((m) => m.stage === 'group');
		else if (filterStage === 'knockout') list = list.filter((m) => m.stage !== 'group');

		if (searchQuery) {
			const q = searchQuery.toLowerCase();
			list = list.filter((m) => {
				const h = teamName(m.home).toLowerCase();
				const a = teamName(m.away).toLowerCase();
				return h.includes(q) || a.includes(q) || (m.group && m.group.toLowerCase().includes(q));
			});
		}
		return list;
	});
</script>

<svelte:head>
	<title>赛程 - WC2026</title>
</svelte:head>

<div class="match-list">
	<div class="controls">
		<input type="text" bind:value={searchQuery} placeholder="🔍 搜索球队或小组..." class="search" />
		<div class="filters">
			<button class:active={filterStage === 'all'} onclick={() => (filterStage = 'all')}>全部 ({matches.length})</button>
			<button class:active={filterStage === 'group'} onclick={() => (filterStage = 'group')}>小组赛</button>
			<button class:active={filterStage === 'knockout'} onclick={() => (filterStage = 'knockout')}>淘汰赛</button>
		</div>
	</div>

	{#if loading}
		<div class="loading">
			<div class="spinner">⏳</div>
			<p>加载比赛数据中...</p>
		</div>
	{:else if filteredMatches.length === 0}
		<div class="empty">没有找到匹配的比赛</div>
	{:else}
		<div class="matches-grid">
			{#each filteredMatches as match (match.id)}
				<a href="/predictions/{match.id}" class="match-card">
					<div class="match-header">
						<span class="stage-badge" style="background:{stageColor(match.stage)}">{stageLabel(match.stage)}</span>
						<span class="match-date">{match.date || '待定'}</span>
					</div>
					<div class="match-teams">
						<div class="team home">
							<span class="flag">{teamFlag(match.home)}</span>
							<span class="name">{teamName(match.home)}</span>
						</div>
						<div class="vs">VS</div>
						<div class="team away">
							<span class="flag">{teamFlag(match.away)}</span>
							<span class="name">{teamName(match.away)}</span>
						</div>
					</div>
					<div class="match-footer">
						<span class="venue">📍 {match.venue}</span>
						{#if match.group}<span class="group-tag">Group {match.group}</span>{/if}
					</div>
					{#if match.homeScore !== null}
						<div class="score">
							{match.homeScore} - {match.awayScore}
						</div>
					{/if}
				</a>
			{/each}
		</div>
	{/if}
</div>

<style>
	.controls { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
	.search { flex: 1; min-width: 200px; padding: 8px 12px; background: #141822; border: 1px solid #2a3040; border-radius: 6px; color: #e0e0e0; font-size: 14px; outline: none; }
	.search:focus { border-color: #1e88e5; }
	.filters { display: flex; gap: 4px; }
	.filters button { background: #1e2433; border: 1px solid #2a3040; color: #aaa; padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; }
	.filters button.active { background: #1e88e5; border-color: #1e88e5; color: #fff; }
	.matches-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
	.match-card {
		background: #141822; border: 1px solid #1e2433; border-radius: 8px;
		padding: 14px; cursor: pointer; transition: all 0.2s; display: block; color: inherit; text-decoration: none;
	}
	.match-card:hover { border-color: #1e88e5; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(30,136,229,0.15); }
	.match-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
	.stage-badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; color: #fff; }
	.match-date { font-size: 12px; color: #667; }
	.match-teams { display: flex; align-items: center; justify-content: space-between; margin: 10px 0; }
	.team { display: flex; align-items: center; gap: 6px; }
	.team .flag { font-size: 20px; }
	.team .name { font-size: 14px; font-weight: 500; }
	.team.home { justify-content: flex-end; }
	.team.away { justify-content: flex-start; }
	.vs { font-weight: bold; color: #556; font-size: 12px; }
	.match-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 6px; }
	.venue { font-size: 11px; color: #556; }
	.group-tag { background: #1a2332; color: #8899aa; padding: 2px 8px; border-radius: 3px; font-size: 11px; }
	.score { text-align: center; font-size: 20px; font-weight: bold; color: #1e88e5; margin-top: 8px; }
	.loading { text-align: center; padding: 80px 0; }
	.spinner { font-size: 48px; animation: spin 1s linear infinite; display: inline-block; }
	@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
	.loading p { color: #8899aa; margin-top: 12px; }
	.empty { color: #556; text-align: center; padding: 60px 0; }
</style>
