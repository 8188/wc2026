// fetch-real-odds.mjs - 使用 Tavily 搜索获取真实赔率和伤病数据
// 由于 BALLDONTLIE 免费 tier 有限，先用 Tavily 搜索获取真实数据

import { TavilyClient } from 'tavily-apis';
import { readFileSync, writeFileSync } from 'fs';

const client = new TavilyClient();
const TAVILY_KEY = process.env.TAVILY_API_KEY;

async function searchRealOdds() {
  // 搜索2026世界杯赔率数据
  const search1 = await client.search({
    query: '2026 FIFA World Cup betting odds 1X2 first round group stage',
    search_depth: 'advanced',
    max_results: 10,
    include_raw_content: true,
  });

  const search2 = await client.search({
    query: '2026 FIFA World Cup injuries suspensions team news squad updates',
    search_depth: 'advanced',
    max_results: 10,
    include_raw_content: true,
  });

  const search3 = await client.search({
    query: '2026 FIFA World Cup betting odds futures outright winner France England Argentina',
    search_depth: 'advanced',
    max_results: 5,
    include_raw_content: true,
  });

  return { odds: search1, news: search2, futures: search3 };
}

async function extractOddsFromPages(results) {
  const urls = [];
  for (const r of results.results) {
    if (r.url) urls.push(r.url);
  }
  if (urls.length === 0) return { rawContent: '', extractedContent: '' };
  
  const extracted = await client.extract({ urls: urls.slice(0, 5) });
  return extracted;
}

async function main() {
  console.log('🔍 正在搜索2026世界杯真实赔率数据...\n');
  
  try {
    const results = await searchRealOdds();
    
    console.log('✅ 搜索结果获取成功\n');
    console.log(`- 赔率搜索结果: ${results.odds.results?.length || 0} 条`);
    console.log(`- 伤病新闻: ${results.news.results?.length || 0} 条`);
    console.log(`- 博彩公司数据: ${results.futures.results?.length || 0} 条\n`);
    
    // 保存原始搜索数据
    const data = {
      timestamp: new Date().toISOString(),
      odds_search: results.odds.results || [],
      news_search: results.news.results || [],
      futures_search: results.futures.results || [],
    };
    
    writeFileSync('./src/data/real-odds-data.json', JSON.stringify(data, null, 2));
    console.log('📊 数据已保存到 src/data/real-odds-data.json');
    
  } catch (error) {
    console.error('❌ 搜索失败:', error.message);
  }
}

main();
