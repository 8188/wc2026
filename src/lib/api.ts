/**
 * API Client for WC2026 Betting Predictor
 * 对接 FastAPI 后端
 */

const BASE = (import.meta.env.PUBLIC_API_BASE_URL || '') + '/api';

async function get(path: string, params?: Record<string, string>) {
	const url = new URL(BASE + path, window.location.origin);
	if (params) {
		Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
	}
	const res = await fetch(url.toString());
	if (!res.ok) throw new Error(`API ${path}: ${res.status}`);
	return res.json();
}

async function post(path: string, body: unknown) {
	const res = await fetch(BASE + path, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});
	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: res.statusText }));
		throw new Error(err.detail || `API ${path}: ${res.status}`);
	}
	return res.json();
}

// ============ Matches ============
export interface Team {
	code: string;
	name: string;
	name_en: string;
	flag: string;
	confederation: string;
	fifa_rank: number;
	strength: number;
}

export interface Match {
	id: number;
	stage: string;
	group: string | null;
	round: number | null;
	home: string | null;
	away: string | null;
	homeScore: number | null;
	awayScore: number | null;
	venue: string;
	city: string;
	date: string | null;
	status: string;
}

export const fetchMatches = (stage?: string, group?: string, limit?: number) => {
	const params: Record<string, string> = {};
	if (stage) params.stage = stage;
	if (group) params.group = group;
	if (limit) params.limit = String(limit);
	return get('/matches', params) as Promise<Match[]>;
};

export const fetchTeams = () => get('/matches/teams') as Promise<Team[]>;

// ============ Predictions ============
export interface ScorePred {
	score: string;
	home: number;
	away: number;
	probability: number;
}

export interface MarketExpectedGoals {
	home: number;
	away: number;
	total: number;
	marketHome: number | null;
	marketAway: number | null;
	marketTotal: number | null;
}

export interface HandicapRec {
	line: number;
	label: string;
	confidence: string;
	xgDiff: number;
}

export interface BookmakerOddsEntry {
	name: string;
	slug: string;
	outcome: { home: number; draw: number; away: number };
	over25: number | null;
	under25: number | null;
	over15: number | null;
	under15: number | null;
	bttsYes: number | null;
	bttsNo: number | null;
	spread: { home: number; line: number; away: number } | null;
	marketHomeGoals: number | null;
	marketAwayGoals: number | null;
	margin: number;
	fetchedAt: string | null;
}

export interface Prediction {
	matchId: number;
	match: string;
	homeName: string;
	awayName: string;
	stage: string;
	date: string | null;
	venue: string;
	prediction: { home: number; draw: number; away: number };
	predictedScore: string;
	confidence: string;
	fairOdds: { home: number; draw: number; away: number };
	bookmakerOdds: Record<string, BookmakerOddsEntry>;
	valueBets: Array<{
		type: string;
		bookie: string;
		marketOdds: number;
		ourOdds: number;
		value: number;
		market: string;
	}>;
	recommendation: {
		action: string;
		reason: string;
		stake: string;
		bet: unknown;
	};
	factors: { strength: number; form: number; news: number };
	news: Record<string, unknown>;
	form: Record<string, unknown>;
	modelFactors: Record<string, unknown>;
	topScores: ScorePred[];
	marketExpectedGoals: MarketExpectedGoals;
	handicapRec: HandicapRec;
}

export const fetchPredictions = (limit?: number) => {
	const params: Record<string, string> = {};
	if (limit) params.limit = String(limit);
	return get('/predictions', params) as Promise<Prediction[]>;
};

export const fetchPrediction = (matchId: number) =>
	get(`/predictions/${matchId}`) as Promise<Prediction>;

// ============ Odds ============
export interface OddsComparison {
	matchId: number;
	bookmakers: BookmakerOddsEntry[];
	bestOdds: Record<string, { odds: number; bookie: string } | null>;
	lastUpdated: string | null;
}

export const fetchOdds = (matchId: number) =>
	get(`/odds/${matchId}`) as Promise<{ matchId: number; bookmakerOdds: Record<string, BookmakerOddsEntry> }>;
export const fetchOddsComparison = (matchId: number) =>
	get(`/odds/${matchId}/comparison`) as Promise<OddsComparison>;
export const fetchOddsHistory = (matchId: number) => get(`/odds/history/${matchId}`);

// ============ News ============
export interface NewsItem {
	headline: string;
	source: string;
	url: string;
	date: string | null;
	sentiment: string;
	sentimentScore: number;
	category: string;
	importance: string;
}

export interface InjuryItem {
	player: string;
	position: string;
	status: string;
	reason: string;
}

export interface TeamNewsResponse {
	teamCode: string;
	score: number;
	news: NewsItem[];
	injuries: InjuryItem[];
}

export const fetchNews = (teamCode: string) => get(`/news/${teamCode}`) as Promise<TeamNewsResponse>;
export const fetchNewsImpact = (matchId: number) => get(`/news/impact/${matchId}`);

// ============ Betting ============
export interface BetResult {
	id: number;
	matchId: number;
	matchLabel: string;
	selection: string;
	selectionLabel: string;
	betType: string;
	spreadLine: number | null;
	totalLine: number | null;
	odds: number;
	stake: number;
	potentialReturn: number;
	potentialProfit: number;
	status: string;
	placedAt: string;
	bankroll: number;
}

export interface BettingStats {
	bankroll: number;
	startBankroll: number;
	totalBets: number;
	wins: number;
	losses: number;
	winRate: number;
	roi: number;
	totalProfit: number;
	profitPercent: number;
	pending: number;
}

const SESSION_ID_KEY = 'wc2026_session_id';

export function getSessionId(): string {
	let id = localStorage.getItem(SESSION_ID_KEY);
	if (!id) {
		id = 'user-' + Math.random().toString(36).slice(2, 10);
		localStorage.setItem(SESSION_ID_KEY, id);
	}
	return id;
}

export const placeBet = (
	matchId: number,
	selection: string,
	odds: number,
	stake: number,
	betType: string = '1x2',
	spreadLine?: number | null,
	totalLine?: number | null,
	bookmaker?: string
) =>
	post('/bet', {
		session_id: getSessionId(),
		match_id: matchId,
		selection,
		odds,
		stake,
		bet_type: betType,
		spread_line: spreadLine ?? null,
		total_line: totalLine ?? null,
		bookmaker: bookmaker || '',
	}) as Promise<BetResult>;

export const settleBet = (betId: number, result: 'won' | 'lost') =>
	post(`/bet/${betId}/settle`, { bet_id: betId, result }) as Promise<{
		id: number;
		result: string;
		profit: number;
		bankroll: number;
		settledAt: string;
	}>;

export const cancelBet = (betId: number) =>
	post(`/bet/${betId}/cancel`, { bet_id: betId }) as Promise<{
		id: number;
		bankroll: number;
	}>;

export const fetchPendingBets = () =>
	get('/bet/pending', { session_id: getSessionId() }) as Promise<BetResult[]>;

export const fetchBetHistory = (limit?: number) =>
	get('/bet/history', {
		session_id: getSessionId(),
		...(limit ? { limit: String(limit) } : {})
	});

export const fetchBettingStats = () =>
	get('/bet/stats', { session_id: getSessionId() }) as Promise<BettingStats>;

export const resetBetting = () =>
	post('/bet/reset?session_id=' + getSessionId(), {}) as Promise<{ ok: boolean; bankroll: number }>;

// ============ Health ============
export const fetchHealth = () => get('/health');

// ============ Teams data (static, for UI display) ============
export const TEAMS: Record<string, { name: string; flag: string; strength: number }> = {
	USA: { name: '美国', flag: '🇺🇸', strength: 82 },
	MEX: { name: '墨西哥', flag: '🇲🇽', strength: 78 },
	CAN: { name: '加拿大', flag: '🇨🇦', strength: 68 },
	ESP: { name: '西班牙', flag: '🇪🇸', strength: 92 },
	ARG: { name: '阿根廷', flag: '🇦🇷', strength: 91 },
	FRA: { name: '法国', flag: '🇫🇷', strength: 90 },
	ENG: { name: '英格兰', flag: '🏴󠁧󠁢󠁥󠁮󠁧󠁿', strength: 89 },
	BRA: { name: '巴西', flag: '🇧🇷', strength: 88 },
	POR: { name: '葡萄牙', flag: '🇵🇹', strength: 86 },
	NED: { name: '荷兰', flag: '🇳🇱', strength: 85 },
	BEL: { name: '比利时', flag: '🇧🇪', strength: 83 },
	GER: { name: '德国', flag: '🇩🇪', strength: 84 },
	CRO: { name: '克罗地亚', flag: '🇭🇷', strength: 80 },
	MAR: { name: '摩洛哥', flag: '🇲🇦', strength: 79 },
	COL: { name: '哥伦比亚', flag: '🇨🇴', strength: 77 },
	URU: { name: '乌拉圭', flag: '🇺🇾', strength: 76 },
	SUI: { name: '瑞士', flag: '🇨🇭', strength: 75 },
	JPN: { name: '日本', flag: '🇯🇵', strength: 76 },
	SEN: { name: '塞内加尔', flag: '🇸🇳', strength: 74 },
	IRN: { name: '伊朗', flag: '🇮🇷', strength: 71 },
	KOR: { name: '韩国', flag: '🇰🇷', strength: 70 },
	ECU: { name: '厄瓜多尔', flag: '🇪🇨', strength: 69 },
	AUT: { name: '奥地利', flag: '🇦🇹', strength: 72 },
	AUS: { name: '澳大利亚', flag: '🇦🇺', strength: 67 },
	NOR: { name: '挪威', flag: '🇳🇴', strength: 68 },
	PAN: { name: '巴拿马', flag: '🇵🇦', strength: 60 },
	EGY: { name: '埃及', flag: '🇪🇬', strength: 66 },
	ALG: { name: '阿尔及利亚', flag: '🇩🇿', strength: 65 },
	SCO: { name: '苏格兰', flag: '🏴󠁧󠁢󠁳󠁣󠁴󠁿', strength: 64 },
	PAR: { name: '巴拉圭', flag: '🇵🇾', strength: 63 },
	TUN: { name: '突尼斯', flag: '🇹🇳', strength: 64 },
	CIV: { name: '科特迪瓦', flag: '🇨🇮', strength: 65 },
	UZB: { name: '乌兹别克斯坦', flag: '🇺🇿', strength: 60 },
	QAT: { name: '卡塔尔', flag: '🇶🇦', strength: 58 },
	KSA: { name: '沙特', flag: '🇸🇦', strength: 58 },
	RSA: { name: '南非', flag: '🇿🇦', strength: 56 },
	JOR: { name: '约旦', flag: '🇯🇴', strength: 55 },
	CPV: { name: '佛德角', flag: '🇨🇻', strength: 55 },
	GHA: { name: '加纳', flag: '🇬🇭', strength: 62 },
	CUW: { name: '库拉索', flag: '🇨🇼', strength: 52 },
	HAI: { name: '海地', flag: '🇭🇹', strength: 50 },
	NZL: { name: '新西兰', flag: '🇳🇿', strength: 54 },
	IRQ: { name: '伊拉克', flag: '🇮🇶', strength: 58 },
	COD: { name: '刚果民主', flag: '🇨🇩', strength: 56 },
	BIH: { name: '波黑', flag: '🇧🇦', strength: 62 },
	CZE: { name: '捷克', flag: '🇨🇿', strength: 63 },
	SWE: { name: '瑞典', flag: '🇸🇪', strength: 68 },
	TUR: { name: '土耳其', flag: '🇹🇷', strength: 70 }
};

export function stageLabel(s: string): string {
	const map: Record<string, string> = {
		group: '小组赛',
		R32: '32强赛',
		R16: '16强赛',
		QF: '四分之一决赛',
		SF: '半决赛',
		'3RD': '三四名决赛',
		FINAL: '决赛'
	};
	return map[s] || s;
}

export function stageColor(s: string): string {
	if (s === 'group') return '#1565c0';
	if (s === 'R32' || s === 'R16') return '#6a1b9a';
	return '#e65100';
}

export function teamName(code: string | null): string {
	if (!code) return 'TBD';
	return TEAMS[code]?.name || code;
}

export function teamFlag(code: string | null): string {
	if (!code) return '❓';
	return TEAMS[code]?.flag || '❓';
}
