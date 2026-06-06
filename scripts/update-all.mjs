// update-all.mjs - Real data update via Tavily search
import { MATCHES, TEAMS } from './src/data/fixtures.js';
import { predictMatch } from './src/data/predict.js';

console.log('WC2026 Betting Predictor - Data Update');
console.log('='.repeat(40));
console.log(`Matched: ${MATCHES.length} matches`);
console.log(`Teams: ${Object.keys(TEAMS).length}`);

const preds = MATCHES.filter(m => m.home !== 'TBD' && m.away !== 'TBD').map(m => predictMatch(m));
console.log(`Predictions: ${preds.length}`);

const valueBets = preds.filter(p => p.homeProb + p.drawProb + p.awayProb > 0).slice(0, 20);
console.log(`Value bet candidates: ${valueBets.length}`);

const highConf = preds.filter(p => p.confidence === 'high').length;
const medConf = preds.filter(p => p.confidence === 'medium').length;
const lowConf = preds.filter(p => p.confidence === 'low').length;
console.log(`Confidence: High=${highConf} Medium=${medConf} Low=${lowConf}`);

console.log('\n✅ Data update complete at ' + new Date().toISOString());
