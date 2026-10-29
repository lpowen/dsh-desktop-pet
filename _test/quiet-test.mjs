// 静默时段边界测试（Asia/Shanghai，23:00–08:00）
import { isQuiet, quietLabel } from '../quiet.mjs';

let fail = 0;
const ok = (name, cond, extra = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? '  ' + extra : ''}`);
  if (!cond) fail++;
};

const cfg = { quietHours: { start: 23, end: 8 }, timeZone: 'Asia/Shanghai' };
const at = (hhmm) => new Date(`2026-10-29T${hhmm}:00+08:00`).getTime();

ok('22:59 还在说话', isQuiet(at('22:59'), cfg) === false);
ok('23:00 开始静默', isQuiet(at('23:00'), cfg) === true);
ok('00:30 静默', isQuiet(at('00:30'), cfg) === true);
ok('07:59 还静默', isQuiet(at('07:59'), cfg) === true);
ok('08:00 恢复', isQuiet(at('08:00'), cfg) === false);
ok('中午不静默', isQuiet(at('12:00'), cfg) === false);

// 同日窗口：1 点 → 6 点
const dayCfg = { quietHours: { start: 1, end: 6 }, timeZone: 'Asia/Shanghai' };
ok('同日窗口 02:00 静默', isQuiet(at('02:00'), dayCfg) === true);
ok('同日窗口 06:30 恢复', isQuiet(at('06:30'), dayCfg) === false);
ok('同日窗口 00:30 不静默', isQuiet(at('00:30'), dayCfg) === false);

// 没配 / 配坏
ok('未配置 = 不静默', isQuiet(at('23:30'), {}) === false);
ok('start=end = 不静默', isQuiet(at('23:30'), { quietHours: { start: 23, end: 23 } }) === false);

ok('标签可读', quietLabel(cfg) === '23:00–08:00', quietLabel(cfg));

console.log(fail === 0 ? '\n全部通过' : `\n${fail} 项失败`);
process.exit(fail === 0 ? 0 : 1);
