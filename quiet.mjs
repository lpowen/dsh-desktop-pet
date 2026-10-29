/**
 * 静默时段判断：跨零点也支持（23 → 8 表示 23:00–次日 08:00）。
 * 用固定时区算「现在几点」，不依赖机器本地时区。
 */
export function isQuiet(nowMs, cfg = {}) {
  const q = cfg.quietHours;
  if (!q) return false;
  const start = Number(q.start);
  const end = Number(q.end);
  if (!Number.isFinite(start) || !Number.isFinite(end) || start === end) return false;

  const tz = cfg.timeZone || 'Asia/Shanghai';
  let hour;
  try {
    const parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: tz, hour: '2-digit', hourCycle: 'h23',
    }).formatToParts(new Date(nowMs));
    hour = Number(parts.find((p) => p.type === 'hour').value);
  } catch {
    hour = new Date(nowMs).getHours();
  }

  if (start < end) return hour >= start && hour < end;   // 同日，如 1 → 6
  return hour >= start || hour < end;                    // 跨零点，如 23 → 8
}

/** 给日志用的可读描述 */
export function quietLabel(cfg = {}) {
  const q = cfg.quietHours;
  if (!q) return '未设置';
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(Number(q.start))}:00–${pad(Number(q.end))}:00`;
}
