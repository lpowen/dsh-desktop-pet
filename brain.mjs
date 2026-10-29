#!/usr/bin/env node
/**
 * 桌宠「意识」服务（http://127.0.0.1:4399）
 *
 * 和 SurfCore 的思路一致：一个角色 + 一份会衰减的记忆 + 一个作息 + 主动行为。
 * QQ 桥接（qq-bot/bridge.mjs）和桌宠（pet.py）都来调这里，所以两边是同一个「她」。
 *
 * 接口：
 *   GET  /health                 存活检查
 *   POST /chat   {key, text, surface}      对话，返回 {reply, sessionId}
 *   GET  /memory                读记忆卡
 *   POST /memory {fact}         记一条长期记忆
 *   POST /memory/clear          清空记忆
 *   GET  /proactive?since=N     拉取主动消息（桌宠轮询）
 *   POST /think                 立刻让她主动想一句
 *   GET  /status                当前作息/空闲/下次思考时间
 */
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { MemoryStore, estimateTokens } from './memory.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CFG = JSON.parse(fs.readFileSync(path.join(HERE, 'config.json'), 'utf8'));
const STATE_DIR = path.join(HERE, CFG.stateDir || 'state');
fs.mkdirSync(STATE_DIR, { recursive: true });

const SESSIONS_FILE = path.join(STATE_DIR, 'sessions.json');
const MEMORY_FILE = path.join(STATE_DIR, 'memory.json');
const SEEN_FILE = path.join(STATE_DIR, 'seen.json');
const LOG_FILE = path.join(STATE_DIR, 'brain.log');

function log(...parts) {
  const line = `[${new Date().toLocaleString('zh-CN', { hour12: false })}] ` +
    parts.map((p) => (typeof p === 'string' ? p : JSON.stringify(p))).join(' ');
  console.log(line);
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch { /* ignore */ }
}

/* ---------------------------------------------------------------- 持久化 */

function readJson(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return fallback; }
}
function writeJson(file, value) {
  try { fs.writeFileSync(file, JSON.stringify(value, null, 2)); } catch (e) { log('写入失败', file, e.message); }
}

const sessions = readJson(SESSIONS_FILE, {});
const memory = readJson(MEMORY_FILE, { facts: [], lastThoughts: [] });
if (!Array.isArray(memory.facts)) memory.facts = [];
if (!Array.isArray(memory.lastThoughts)) memory.lastThoughts = [];

// 分层记忆引擎（原文归档 + 事件卡 + 冷热 + 线索召回 + 连续性状态）
const store = new MemoryStore(path.join(STATE_DIR, 'memstore'));

// 已注入去重（借 meow-memory 的 seen 设计）：同一条记忆在同一会话里只注入一次
let seenMap = readJson(SEEN_FILE, {});
const SEEN_TTL = 6 * 3600 * 1000;

function seenFor(key) {
  const rec = seenMap[key];
  if (!rec || Date.now() - (rec.at || 0) > SEEN_TTL) return new Set();
  return new Set(rec.ids || []);
}

function markSeen(key, ids) {
  if (!ids || !ids.length) return;
  const cur = seenFor(key);
  for (const id of ids) cur.add(id);
  seenMap[key] = { ids: [...cur].slice(-200), at: Date.now() };
  writeJson(SEEN_FILE, seenMap);
}

function clearSeen(key) {
  if (seenMap[key]) {
    delete seenMap[key];
    writeJson(SEEN_FILE, seenMap);
  }
}

// 早期卡片用的是 desk:owner，统一并入 owner 作用域
for (const r of store.records) { if (r.scope === 'desk:owner') r.scope = 'owner'; }
store.save();

// 老版本只有一条条 fact，迁移成 pinned 记录，只做一次
if (memory.facts.length && !store.records.some((r) => r.pinned)) {
  for (const fact of memory.facts) {
    const rec = store.upsertEventCard({
      text: fact, scope: 'desk:owner', interactionId: 'migrate', sourceEventId: null, explicit: true,
    });
    if (rec) rec.pinned = true;
  }
  store.save();
  log(`已迁移 ${memory.facts.length} 条旧记忆为固定记忆`);
}

const status = { lastActivity: Date.now(), lastThoughtAt: 0, nextThinkAt: 0, thinking: false };
const proactive = []; // {id, text, at, kind}
let proactiveSeq = 0;

/* ---------------------------------------------------------- 调用 dsh 一次 */

function killTree(child) {
  if (process.platform === 'win32' && child.pid) {
    spawn('taskkill', ['/pid', String(child.pid), '/t', '/f'], { windowsHide: true });
  } else {
    try { child.kill('SIGKILL'); } catch { /* ignore */ }
  }
}

function runDsh({ sessionId, task, timeoutMs = 180000 }) {
  return new Promise((resolve, reject) => {
    const cwd = CFG.workspace || HERE;
    const common = { cwd, windowsHide: true, env: { ...process.env }, stdio: ['pipe', 'pipe', 'pipe'] };
    let child;
    if (process.platform === 'win32') {
      const inner = `"${CFG.dshCmd}" --profile "${CFG.profile}" --json` +
        (sessionId ? ` --session-id "${sessionId}"` : '') + ' -';
      child = spawn(process.env.ComSpec || 'cmd.exe', ['/d', '/s', '/c', `"${inner}"`],
        { ...common, windowsVerbatimArguments: true });
    } else {
      const args = ['--profile', CFG.profile, '--json'];
      if (sessionId) args.push('--session-id', sessionId);
      args.push('-');
      child = spawn(CFG.dshCmd, args, common);
    }

    let out = '', err = '', done = false;
    const timer = setTimeout(() => { if (!done) { log('dsh 超时'); killTree(child); } }, timeoutMs);
    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', (d) => { out += d; });
    child.stderr.on('data', (d) => { err += d; });
    child.on('error', (e) => { clearTimeout(timer); done = true; reject(e); });
    child.stdin.on('error', () => {});
    child.on('close', (code) => {
      clearTimeout(timer);
      done = true;
      let sid = sessionId || null, text = '', failure = null, usage = null;
      for (const line of out.split(/\r?\n/)) {
        const t = line.trim();
        if (!t.startsWith('{')) continue;
        let ev; try { ev = JSON.parse(t); } catch { continue; }
        if (ev.type === 'session') sid = ev.sessionId || sid;
        else if (ev.type === 'final') text = typeof ev.text === 'string' ? ev.text : '';
        else if (ev.type === 'status' && ev.usage) usage = ev.usage;
        else if (ev.type === 'turn_end' && ev.reason?.kind === 'error') failure = ev.reason.error;
        else if (ev.type === 'error') failure = ev;
      }
      resolve({ code, text, failure, err, sessionId: sid, usage });
    });
    child.stdin.end(task);
  });
}

/* -------------------------------------------------------------- 提示词拼装 */

function timeText() {
  const tz = CFG.timeZone || 'Asia/Shanghai';
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: tz, month: '2-digit', day: '2-digit', weekday: 'long',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date());
}

function sceneOf(surface) {
  if (surface === 'qq') return 'QQ 聊天';
  if (surface === 'wecom') return '企业微信聊天';
  return '你的桌面（用户就在你旁边的电脑前）';
}

/** 记忆作用域：本人（桌面 + QQ 私聊 + 企业微信）共用一份；群聊各自隔离 */
function scopeOf(key) {
  if (key.startsWith('desk:') || key.startsWith('private:') || key.startsWith('wecom:')) return 'owner';
  return key;
}

const recentUser = new Map(); // key -> 最近几条用户原话，用于“继续那件事”的线索继承
function rememberUserLine(key, text) {
  const arr = recentUser.get(key) || [];
  arr.push(String(text).slice(0, 60));
  while (arr.length > 3) arr.shift();
  recentUser.set(key, arr);
}

function detectMood(text) {
  const rules = [
    [/累|疲惫|加班|熬夜|没睡好/, '有点累'],
    [/难过|伤心|失落|emo|想哭/i, '低落'],
    [/开心|高兴|太好了|哈哈|爽|顺利/, '轻快'],
    [/烦|生气|气死|火大|受够/, '烦躁'],
    [/焦虑|紧张|担心|怕/, '不安'],
  ];
  for (const [re, label] of rules) {
    if (re.test(text)) return { label, intensity: 0.7 };
  }
  return null;
}

/** 称呼规则：桌面＝哥哥；QQ 主号＝哥哥；其他 QQ 号＝叔叔。 */
const OWNER_QQ = (CFG.ownerQQ || '').toString();

function addressFor(key, surface, extra) {
  if (surface !== 'qq') return '哥哥';                    // 桌宠
  const m = /QQ\s*(\d{5,12})/.exec(extra || '');
  let qq = m ? m[1] : null;
  if (!qq) {                                              // 兜底：key 形如 private:123
    const k = /^(?:private|group):(\d+)/.exec(key || '');
    qq = k ? k[1] : null;
  }
  if (qq) return qq === OWNER_QQ ? '哥哥' : '叔叔';
  return '叔叔';
}

function buildTask({ surface, text, extra, snapshot, continuity, addr }) {
  const parts = [`【当前时间】${timeText()}`, `【场景】${sceneOf(surface)}`];
  if (addr) parts.push(`【称呼】这次要叫对方「${addr}」，不要用别的称呼，也不要叫「主人」「您」。`);
  if (continuity) parts.push('', continuity);
  if (snapshot) parts.push('', snapshot);
  if (extra) parts.push('', `【补充】${extra}`);
  parts.push('', '【用户这条消息】', text);
  return parts.join('\n');
}

async function chat({ key, text, surface = 'desk', extra = '' }) {
  const interactionId = `turn-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;

  // 1. 原文先归档（哪怕不建记忆卡）
  const scope = scopeOf(key);
  const userEvent = store.archive({ role: 'user', text, scope, surface });

  // 2. 组装这次能看到的记忆：固定 + 相关热记忆 + 线索召回
  const seen = seenFor(key);
  const snap = store.snapshot({ userText: text, scope, recent: recentUser.get(key) || [], seen });
  const continuity = store.continuityText();
  const addr = addressFor(key, surface, extra);
  const task = buildTask({ surface, text, extra, snapshot: snap.text, continuity, addr });

  // 3. 跑一次模型
  const rec = sessions[key];
  let res = await runDsh({ sessionId: rec?.sessionId, task });
  if ((res.code !== 0 || res.failure) && rec?.sessionId) {
    log('续接失败，开新会话', res.failure?.error?.message || res.err?.slice(-120));
    delete sessions[key];
    res = await runDsh({ sessionId: null, task });
  }
  if (res.sessionId) {
    sessions[key] = { sessionId: res.sessionId, updatedAt: Date.now() };
    writeJson(SESSIONS_FILE, sessions);
  }

  const reply = (res.text || '').trim();

  // 4. 归档回复、更新记忆与连续性
  if (reply) store.archive({ role: 'assistant', text: reply, scope, surface });
  if (userEvent) {
    store.upsertEventCard({ text, scope, interactionId, sourceEventId: userEvent.id });
    store.noteMentions(text, scope, interactionId);
    const mood = detectMood(text);
    const unfinished = /(还没|没想好|下次|明天再|回头再|说好|答应|考虑)/.test(text);
    if (mood || unfinished) {
      store.addAnchor({ text, sourceId: userEvent.id, mood });
    }
  }
  rememberUserLine(key, text);
  markSeen(key, snap.ids);

  status.lastActivity = Date.now();
  status.lastSnapshot = snap.used || null;
  status.lastUsage = res.usage || null;
  scheduleNextThink();
  const tok = res.usage ? `，输入 ${res.usage.inputTokens}t（缓存命中 ${res.usage.cacheReadTokens || 0}t）` : '';
  log(`记忆快照 ${snap.used ? `${snap.used.pinned}+${snap.used.hot}+${snap.used.recalled}t` : '空'}，召回 ${snap.recalled.length} 条${tok}`);
  return reply;
}

/* ---------------------------------------------------------------- 作息 */

function hourNow() {
  const tz = CFG.timeZone || 'Asia/Shanghai';
  const s = new Intl.DateTimeFormat('en-GB', { timeZone: tz, hour: '2-digit', hour12: false }).format(new Date());
  return Number(s);
}

function inActiveHours() {
  const [start, end] = CFG.activeHours || [8, 24];
  const h = hourNow();
  if (start <= end) return h >= start && h < end;
  return h >= start || h < end; // 跨午夜
}

function scheduleNextThink() {
  const [min, max] = CFG.thinkEveryMinutes || [25, 55];
  const wait = (min + Math.random() * (max - min)) * 60 * 1000;
  status.nextThinkAt = Date.now() + wait;
}

/* ------------------------------------------------------------ 主动行为 */

const THOUGHT_PROMPT = `你现在没有在跟谁对话，只是独自待在用户的桌面上。
你自己冒出一个念头，想主动说一句话。

要求：
- 用你的人设口吻，一句话，40 字以内，像随口说的，不要起承转合。
- 可以是观察到时间/天气/用户状态后的小感慨、关心、吐槽，或分享一个刚想到的小念头。
- 不要问"你在干嘛"这类空话，不要重复最近说过的话。
- 只输出这句话本身，不要引号、不要解释。`;

async function think(kind = 'idle') {
  if (status.thinking) return null;
  status.thinking = true;
  try {
    const recent = memory.lastThoughts.slice(-4).map((t) => `- ${t}`).join('\n');
    const task = buildTask({
      surface: 'desk',
      text: THOUGHT_PROMPT,
      extra: recent ? `你最近说过：\n${recent}` : '',
    });
    const res = await runDsh({ sessionId: null, task });
    const text = (res.text || '').trim().replace(/^["“]|["”]$/g, '');
    if (!text) return null;
    const item = { id: ++proactiveSeq, text, at: Date.now(), kind };
    proactive.push(item);
    if (proactive.length > 50) proactive.shift();
    memory.lastThoughts.push(text);
    if (memory.lastThoughts.length > 20) memory.lastThoughts.shift();
    writeJson(MEMORY_FILE, memory);
    status.lastThoughtAt = Date.now();
    log('主动说话：', text);
    return item;
  } catch (e) {
    log('主动行为失败', e.message);
    return null;
  } finally {
    status.thinking = false;
    scheduleNextThink();
  }
}

function tick() {
  if (CFG.proactive === false) return;
  if (!inActiveHours()) return;
  if (Date.now() < status.nextThinkAt) return;
  const idleMin = (CFG.idleMinutesBeforeThink ?? 12);
  if (Date.now() - status.lastActivity < idleMin * 60 * 1000) return;
  think('idle');
}

if (!status.nextThinkAt) scheduleNextThink();
setInterval(tick, 60 * 1000);

/* ---------------------------------------------------------------- HTTP */

function storeStats() {
  const now = Date.now();
  const counts = { hot: 0, cold: 0, pinned: 0 };
  for (const r of store.records) {
    if (r.status !== 'valid') continue;
    if (r.pinned) counts.pinned++;
    if (store.stageOf(r, now) === 'cold') counts.cold++;
    else counts.hot++;
  }
  return { records: store.records.length, ...counts, budget: store.budget };
}

function json(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Access-Control-Allow-Origin': '*',
  });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve) => {
    let raw = '';
    req.on('data', (c) => { raw += c; if (raw.length > 1e6) req.destroy(); });
    req.on('end', () => {
      try { resolve(JSON.parse(raw || '{}')); } catch { resolve({}); }
    });
  });
}

const server = http.createServer(async (req, res) => {
  const u = new URL(req.url, 'http://127.0.0.1');
  const p = u.pathname;

  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    });
    return res.end();
  }

  try {
    if (p === '/health') return json(res, 200, { ok: true, name: CFG.name || '阿柒' });

    if (p === '/chat' && req.method === 'POST') {
      const { key = 'desk:owner', text = '', surface = 'desk', extra = '' } = await readBody(req);
      if (!String(text).trim()) return json(res, 400, { error: 'empty text' });
      log(`chat[${surface}] ${String(text).slice(0, 60)}`);
      const reply = await chat({ key, text, surface, extra });
      return json(res, 200, { reply, sessionId: sessions[key]?.sessionId });
    }

    if (p === '/memory' && req.method === 'GET') {
      const pinned = store.records.filter((r) => r.pinned && r.status === 'valid');
      return json(res, 200, { facts: pinned.map((r) => r.summary), stats: storeStats() });
    }

    if (p === '/memory' && req.method === 'POST') {
      const { fact } = await readBody(req);
      if (fact && String(fact).trim()) {
        const rec = store.upsertEventCard({
          text: String(fact).trim(),
          scope: 'owner',
          interactionId: 'manual-' + Date.now(),
          sourceEventId: null,
          explicit: true,
        });
        if (rec) { rec.pinned = true; store.save(); }
        log('固定记忆：', fact);
      }
      return json(res, 200, {
        facts: store.records.filter((r) => r.pinned && r.status === 'valid').map((r) => r.summary),
      });
    }

    if (p === '/memory/clear' && req.method === 'POST') {
      store.records = [];
      store.continuity = { updatedAt: 0, mood: null, anchors: [], unresolved: [] };
      store.save();
      store.saveContinuity();
      try { fs.rmSync(store.archiveFile, { force: true }); } catch { /* ignore */ }
      memory.facts = [];
      memory.lastThoughts = [];
      seenMap = {};
      writeJson(SEEN_FILE, seenMap);
      writeJson(MEMORY_FILE, memory);
      Object.keys(sessions).forEach((k) => delete sessions[k]);
      writeJson(SESSIONS_FILE, sessions);
      return json(res, 200, { ok: true });
    }

    if (p === '/reset' && req.method === 'POST') {
      const { key } = await readBody(req);
      if (key && sessions[key]) {
        delete sessions[key];
        writeJson(SESSIONS_FILE, sessions);
      }
      if (key) clearSeen(key);
      return json(res, 200, { ok: true });
    }

    if (p === '/proactive' && req.method === 'GET') {
      const since = Number(u.searchParams.get('since') || 0);
      return json(res, 200, { items: proactive.filter((i) => i.id > since), lastId: proactiveSeq });
    }

    if (p === '/dream' && req.method === 'POST') {
      const stats = store.dream();
      log('dream 完成', stats);
      return json(res, 200, { ok: true, stats, total: store.dreamStats });
    }

    if (p === '/think' && req.method === 'POST') {
      const item = await think('manual');
      return json(res, 200, { item });
    }

    if (p === '/status') {
      return json(res, 200, {
        phase: inActiveHours() ? 'awake' : 'resting',
        hour: hourNow(),
        idleMinutes: Math.round((Date.now() - status.lastActivity) / 60000),
        nextThinkInMinutes: Math.max(0, Math.round((status.nextThinkAt - Date.now()) / 60000)),
        thinking: status.thinking,
        lastSnapshotTokens: status.lastSnapshot || null,
        memory: storeStats(),
        dream: store.dreamStats,
        seenSessions: Object.keys(seenMap).length,
      });
    }

    return json(res, 404, { error: 'not found' });
  } catch (e) {
    log('请求异常', p, e.message);
    return json(res, 500, { error: e.message });
  }
});

// dream：空闲时做规则化整理（合并近重复、压缩长细节），不调用模型，零成本
setInterval(() => {
  try {
    if (status.thinking) return;
    const idleMin = (Date.now() - status.lastActivity) / 60000;
    if (idleMin < 15) return;
    if (Date.now() - (store.dreamStats.lastAt || 0) < 60 * 60000) return;
    if (!store.records.some((r) => r.status === 'valid')) return;
    const stats = store.dream();
    if (stats.merged || stats.compressed) log('空闲 dream', stats);
  } catch (e) {
    log('dream 失败', e.message);
  }
}, 10 * 60000);

const port = CFG.brainPort || 4399;

// pid 文件：停止脚本/看门狗按它精确杀进程，不依赖命令行匹配
try {
  fs.writeFileSync(path.join(STATE_DIR, 'brain.pid'), String(process.pid));
} catch { /* ignore */ }
process.on('exit', () => {
  try { fs.rmSync(path.join(STATE_DIR, 'brain.pid'), { force: true }); } catch { /* ignore */ }
});

server.listen(port, '127.0.0.1', () => {
  log(`意识服务已启动 http://127.0.0.1:${port}  人格=${CFG.name || '阿柒'}  profile=${CFG.profile}`);
});
