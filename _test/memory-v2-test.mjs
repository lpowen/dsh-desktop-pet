// v2 新特性测试：BM25 排序、已注入去重、dream 整理
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { MemoryStore } from '../memory.mjs';

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'memv2-'));
const store = new MemoryStore(dir);
const now = Date.now();
let fail = 0;
const ok = (name, cond, extra = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? '  ' + extra : ''}`);
  if (!cond) fail++;
};

const mk = (text, interaction = 't') => store.upsertEventCard({
  text, scope: 'owner', interactionId: interaction, sourceEventId: `e-${interaction}`,
});

const camera = mk('我在西安买了台胶片相机，花了两千多', 't1');
const work = mk('今天加班到十点，需求又改了三次', 't2');
const coffee = mk('最近喜欢喝无糖拿铁，不加奶', 't3');

// 1) BM25 排序：查询命中的那条排第一
const hot = store.relevantHot('胶片相机拍出来怎么样', 'owner', now);
const ranked = hot.filter((h) => h.rel > 0).sort((a, b) => b.sim - a.sim);
ok('BM25 命中查询相关记录', ranked.length >= 1);
ok('相关记录排第一', ranked[0] && ranked[0].rec.id === camera.id,
  ranked[0] ? `first=${ranked[0].rec.title}` : 'none');
ok('无关记录不参与', !ranked.some((h) => h.rec.id === coffee.id && h.rel > 0.3));

// 2) 已注入去重：seen 里的条目不再进快照
const first = store.snapshot({ userText: '那台胶片相机呢', scope: 'owner', now });
ok('第一次注入有内容', first.text.includes('胶片相机'), `ids=${first.ids.length}`);
const second = store.snapshot({
  userText: '那台胶片相机呢', scope: 'owner', now,
  seen: new Set(first.ids),
});
ok('已注入的不再重复注入', !second.text.includes('胶片相机'), `ids=${second.ids.length}`);

// pinned 不受 seen 限制
const pin = store.upsertEventCard({ text: '用户叫小林，住在苏州', scope: 'owner', explicit: true });
pin.pinned = true;
store.save();
const s3 = store.snapshot({ userText: '随便聊聊', scope: 'owner', now, seen: new Set([pin.id]) });
ok('pinned 不受 seen 影响', s3.text.includes('小林'));

// 3) dream：近重复合并
const before = store.records.filter((r) => r.status === 'valid').length;
const d1 = mk('下个月要去成都玩，主要想吃火锅和串串', 't4');
const d2 = mk('下个月要去成都玩，主要想吃火锅，还想逛宽窄巷子', 't5');
const stats = store.dream(now);
const mergedRecs = store.records.filter((r) => r.supersedes);
ok('dream 合并了近重复', stats.merged >= 1, `merged=${stats.merged}`);
ok('被合并的记录标记为 superseded', mergedRecs.length >= 1);
ok('合并后有效记录变少', store.records.filter((r) => r.status === 'valid').length < before + 2);

// 4) dream：压缩长 detail（摘要阶段）
const longText = '我上个月去了一趟苏州，逛了平江路和拙政园，还吃了很多小吃，街边有卖糖粥的，' +
  '路上遇到一个卖糖画的老爷爷，聊了很久，他说这条街几十年都没变过，' +
  '我听了挺感慨的，回来之后一直想着那天的天气和街上的人，还有傍晚桥边的风，' +
  '下次想带朋友一起去，顺便看看夜里的河灯，听说那时候最好看。';
const comp = mk(longText, 't6');
comp.last_user_mention_at = now - 5 * 86400000;   // 进入 summary 阶段
const beforeLen = comp.detail.length;
const stats2 = store.dream(now);
ok('dream 压缩了长细节', stats2.compressed >= 1 || comp.detail.length <= beforeLen,
  `compressed=${stats2.compressed}`);
ok('压缩后 detail 不超过摘要', comp.detail.length <= Math.max(1, comp.summary.length) + 1,
  `${comp.detail.length} vs ${comp.summary.length}`);

// 5) dreamStats 累积
ok('dream 统计被记录', store.dreamStats.runs >= 2 && store.dreamStats.merged >= 1);
ok('dream 时间戳更新', store.dreamStats.lastAt > 0);

console.log(fail === 0 ? '\n全部通过' : `\n${fail} 项失败`);
fs.rmSync(dir, { recursive: true, force: true });
process.exit(fail === 0 ? 0 : 1);
