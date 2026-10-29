// 分层记忆引擎的场景测试（不连模型，纯规则验证）
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { MemoryStore, estimateTokens } from '../memory.mjs';

const DAY = 86400000;
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'memtest-'));
const store = new MemoryStore(dir);
const now = Date.now();
let fail = 0;

function check(name, cond, extra = '') {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? '  ' + extra : ''}`);
  if (!cond) fail++;
}

// 1. 建卡
const e1 = store.archive({ role: 'user', text: '我在西安买了台胶片相机，花了两千多', scope: 'desk:owner' });
const card = store.upsertEventCard({
  text: '我在西安买了台胶片相机，花了两千多', scope: 'desk:owner',
  interactionId: 'turn-1', sourceEventId: e1.id,
});
check('建卡成功', !!card);
check('识别地点/物品', card.facets.places.includes('西安') && card.facets.objects.includes('相机'),
  JSON.stringify(card.facets));
check('初始是 detail', store.stageOf(card, now) === 'detail');

// 2. 当天提问：相关就带上
const s1 = store.snapshot({ userText: '那台相机好用吗', scope: 'desk:owner', now });
check('当天相关记忆进快照', s1.text.includes('胶片相机'), `tokens=${s1.used?.total}`);
check('快照有预算内 token', (s1.used.total || 0) <= store.budget.total);

// 3. 无关问候：不应注入
const s2 = store.snapshot({ userText: '今天好累啊', scope: 'desk:owner', now });
check('无关问候不塞旧事', !s2.text.includes('胶片相机'));

// 4. 4 天后变摘要
card.last_user_mention_at = now - 4 * DAY;
card.mentions = [{ interaction_id: 'turn-1', at: now - 4 * DAY }];
check('4 天后是 summary', store.stageOf(card, now) === 'summary');
const s3 = store.snapshot({ userText: '相机还在用吗', scope: 'desk:owner', now });
check('摘要仍能进快照', s3.text.includes('(摘要)'), s3.text.split('\n').find((l) => l.includes('相机')) || '');

// 5. 15 天后冷存
card.last_user_mention_at = now - 15 * DAY;
card.mentions = [{ interaction_id: 'turn-1', at: now - 15 * DAY }];
check('15 天后冷存', store.stageOf(card, now) === 'cold');
const s4 = store.snapshot({ userText: '今天好累啊', scope: 'desk:owner', now });
check('冷存后普通问候不注入', !s4.text.includes('胶片相机'));

// 6. 线索召回
const s5 = store.snapshot({ userText: '还记得西安那台相机吗？', scope: 'desk:owner', now });
check('线索召回命中', s5.recalled.length === 1 && s5.text.includes('胶片相机'), `recalled=${s5.recalled.length}`);
check('召回占 recalled 预算', (s5.used.recalled || 0) > 0);

// 7. 无定位线索 → 拒绝并要用户补充
const s6 = store.snapshot({ userText: '你还记得那次吗', scope: 'desk:owner', now });
check('模糊线索不扫描全库', s6.recalled.length === 0 && s6.cue?.needsClarify === true);

// 8. 旧事不被年代惩罚：20 年前的事也能召回
const oldCard = store.upsertEventCard({
  text: '2005年在成都看过一场演唱会', scope: 'desk:owner', interactionId: 'turn-old', sourceEventId: 'e-old',
});
oldCard.last_user_mention_at = now - 20 * 365 * DAY;
oldCard.mentions = [{ interaction_id: 'turn-old', at: now - 20 * 365 * DAY }];
const s7 = store.snapshot({ userText: '还记得成都那场演唱会吗', scope: 'desk:owner', now });
check('久远事件不被年代衰减埋掉', s7.recalled.some((r) => r.id === oldCard.id));

// 9. pinned 固定事实
const pin = store.upsertEventCard({ text: '用户叫小林，住在苏州', scope: 'desk:owner', explicit: true });
pin.pinned = true;
store.save();
const s8 = store.snapshot({ userText: '随便聊聊', scope: 'desk:owner', now });
check('pinned 每轮都带上', s8.text.includes('小林'));

// 10. 预算硬上限：灌 60 条相关记忆
for (let i = 0; i < 60; i++) {
  store.upsertEventCard({
    text: `我记得那次一起去西安看展，第${i}次，还聊了很多关于相机的事`,
    scope: 'desk:owner', interactionId: `bulk-${i}`, sourceEventId: `e-bulk-${i}`,
  });
}
const s9 = store.snapshot({ userText: '西安看展相机', scope: 'desk:owner', now });
check('快照总 token ≤ 1600', (s9.used.total || 0) <= store.budget.total, `total=${s9.used.total}`);
check('热记忆条数 ≤ 8', (s9.stages || []).length <= store.budget.hotCount);

// 11. 连续性：情绪按半衰期回落
store.addAnchor({ text: '今天加班到很晚，有点累', mood: { label: '有点累', intensity: 0.8 } });
const c1 = store.continuityText(now);
check('连续性状态进提示', c1.includes('有点累'));
store.continuity.mood.value_as_of = now - 24 * 3600000;
store.continuity.mood.intensity = 0.8;
store.decayMood(now);
check('24 小时后情绪衰减到 0.2 左右', store.continuity.mood && Math.abs(store.continuity.mood.intensity - 0.2) < 0.05,
  `intensity=${store.continuity.mood?.intensity}`);

// 12. 记忆卡去重：同一件事说两遍不新建
const before = store.records.length;
store.upsertEventCard({ text: '我在西安买了台胶片相机，花了两千多', scope: 'desk:owner', interactionId: 'turn-9' });
check('同一事实合并而不是新建', store.records.length === before, `records=${store.records.length}`);

console.log(fail === 0 ? '\n全部通过' : `\n${fail} 项失败`);
fs.rmSync(dir, { recursive: true, force: true });
process.exit(fail === 0 ? 0 : 1);
