// v3 新特性测试：注入带日期、重要度拉长半衰期、每日配额、问句信息量门
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { MemoryStore } from '../memory.mjs';

const DAY = 86400000;
let fail = 0;
const ok = (name, cond, extra = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? '  ' + extra : ''}`);
  if (!cond) fail++;
};
const newStore = (budget) => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'memv3-'));
  const s = new MemoryStore(dir, budget ? { budget } : {});
  return { s, dir };
};

// 1) 注入行带日期
{
  const { s, dir } = newStore();
  const now = Date.now();
  s.upsertEventCard({ text: '我在西安买了台胶片相机，花了两千多', scope: 'owner', interactionId: 't1' });
  const snap = s.snapshot({ userText: '那台相机怎么样', scope: 'owner', now });
  ok('注入行带日期', /（今天）/.test(snap.text), snap.text.split('\n').find((l) => l.includes('相机')) || '');
  fs.rmSync(dir, { recursive: true, force: true });
}

// 2) 重要度拉长半衰期：同样 10 天，重要的还在摘要，不重要的已冷
{
  const { s, dir } = newStore();
  const now = Date.now();
  const a = s.upsertEventCard({ text: '她说她下个月要去成都看演唱会，票已经买好了', scope: 'owner', interactionId: 'a', importance: 5 });
  const b = s.upsertEventCard({ text: '路过楼下看到新开了一家洗衣店，门口摆着绿植', scope: 'owner', interactionId: 'b', importance: 1 });
  for (const r of [a, b]) {
    r.last_user_mention_at = now - 10 * DAY;
    r.mentions = [{ interaction_id: 'x', at: now - 10 * DAY }];
  }
  ok('重要的事 10 天后仍是摘要', s.stageOf(a, now) === 'summary', s.stageOf(a, now));
  ok('不重要的事 10 天后已冷', s.stageOf(b, now) === 'cold', s.stageOf(b, now));
  fs.rmSync(dir, { recursive: true, force: true });
}

// 3) 每日配额：默认 12，设成 3 验证
{
  const { s, dir } = newStore({ dailyCap: 3 });
  const texts = [
    '我最近开始每天早上跑步，从家跑到河边再回来',
    '公司楼下那家面馆换了老板，味道不如以前了',
    '昨天把房间彻底收拾了一遍，扔掉了两箱旧书',
    '周末想去看新上映的那部科幻电影，据说特效不错',
    '新买的键盘手感很好，敲起来比旧的安静很多',
  ];
  let made = 0;
  for (let i = 0; i < texts.length; i++) {
    const r = s.upsertEventCard({ text: texts[i], scope: 'owner', interactionId: `q${i}` });
    if (r) made++;
  }
  ok('每日配额生效', made === 3, `made=${made}`);
  const forced = s.upsertEventCard({ text: '用户明确要求记住：生日是三月十二日', scope: 'owner', interactionId: 'ex', explicit: true });
  ok('explicit 不受配额限制', !!forced);
  fs.rmSync(dir, { recursive: true, force: true });
}

// 4) 问句信息量门：寒暄不翻记忆，点名才翻
{
  const { s, dir } = newStore();
  const now = Date.now();
  const topics = [
    '我在西安买了台胶片相机，花了两千多',
    '最近在学做面包，第一次发酵失败了',
    '同事推荐了一款降噪耳机，说地铁上特别好用',
    '周末去了趟苏州，逛了平江路和拙政园',
    '家里的猫最近总在半夜跑酷，吵得睡不好',
    '想换个显示器，主要用来看代码和修图',
  ];
  topics.forEach((t, i) => s.upsertEventCard({ text: t, scope: 'owner', interactionId: `p${i}` }));

  const greeting = s.snapshot({ userText: '在吗，今天过得怎么样', scope: 'owner', now });
  ok('寒暄不翻记忆', greeting.ids.length === 0, `ids=${greeting.ids.length}`);

  const pointed = s.snapshot({ userText: '那台胶片相机后来拍了吗', scope: 'owner', now });
  ok('点名具体事物时会翻', pointed.ids.length >= 1, `ids=${pointed.ids.length}`);
  fs.rmSync(dir, { recursive: true, force: true });
}

// 5) 证据不除以问句长度：长问句里一个稀有词也能命中
{
  const { s, dir } = newStore();
  const now = Date.now();
  s.upsertEventCard({ text: '我在西安买了台胶片相机，花了两千多', scope: 'owner', interactionId: 'c' });
  s.upsertEventCard({ text: '最近在学做面包，第一次发酵失败了', scope: 'owner', interactionId: 'd' });
  s.upsertEventCard({ text: '周末去了趟苏州，逛了平江路和拙政园', scope: 'owner', interactionId: 'e' });
  const longQuery = '嗯我想想啊，之前你记不记得我有一次提到过胶片相机这件事来着';
  const snap = s.snapshot({ userText: longQuery, scope: 'owner', now });
  ok('长问句里一个稀有词仍能命中', snap.ids.length >= 1, `ids=${snap.ids.length}`);
  fs.rmSync(dir, { recursive: true, force: true });
}

console.log(fail === 0 ? '\n全部通过' : `\n${fail} 项失败`);
process.exit(fail === 0 ? 0 : 1);
