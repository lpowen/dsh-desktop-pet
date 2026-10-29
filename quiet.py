"""静默时段判断（Python 版，和 brain 用的 quiet.mjs 同一套规则）。

配置写法：config.json 里
    "quietHours": { "start": 23, "end": 8 }
表示 23:00–次日 08:00。start == end 或没有这一项 = 不静默。
"""
import time
from datetime import datetime
from zoneinfo import ZoneInfo


def is_quiet(cfg, now=None):
    q = cfg.get("quietHours")
    if not q:
        return False
    try:
        start = int(q.get("start"))
        end = int(q.get("end"))
    except (TypeError, ValueError):
        return False
    if start == end:
        return False

    ts = time.time() if now is None else now
    tz = cfg.get("timeZone") or "Asia/Shanghai"
    try:
        hour = datetime.fromtimestamp(ts, ZoneInfo(tz)).hour
    except Exception:
        hour = datetime.fromtimestamp(ts).hour

    if start < end:
        return start <= hour < end
    return hour >= start or hour < end   # 跨零点


def quiet_label(cfg):
    q = cfg.get("quietHours")
    if not q:
        return "未设置"
    return f"{int(q['start']):02d}:00–{int(q['end']):02d}:00"
