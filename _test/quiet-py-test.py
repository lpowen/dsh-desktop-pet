"""静默时段（Python 侧）边界测试：23:00–08:00。"""
import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from quiet import is_quiet, quiet_label  # noqa: E402

fail = 0


def ok(name, cond, extra=""):
    global fail
    print(("PASS" if cond else "FAIL"), name, extra)
    if not cond:
        fail += 1


def at(hhmm):
    h, m = map(int, hhmm.split(":"))
    tz = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime(2026, 10, 29, h, m, tzinfo=tz).timestamp()


cfg = {"quietHours": {"start": 23, "end": 8}, "timeZone": "Asia/Shanghai"}
ok("22:59 还醒着", is_quiet(cfg, at("22:59")) is False)
ok("23:00 睡着", is_quiet(cfg, at("23:00")) is True)
ok("00:30 睡着", is_quiet(cfg, at("00:30")) is True)
ok("07:59 还睡着", is_quiet(cfg, at("07:59")) is True)
ok("08:00 醒了", is_quiet(cfg, at("08:00")) is False)
ok("中午醒着", is_quiet(cfg, at("12:00")) is False)

day = {"quietHours": {"start": 1, "end": 6}, "timeZone": "Asia/Shanghai"}
ok("同日窗口 02:00", is_quiet(day, at("02:00")) is True)
ok("同日窗口 06:30", is_quiet(day, at("06:30")) is False)
ok("未配置不静默", is_quiet({}, at("23:30")) is False)
ok("start==end 不静默", is_quiet({"quietHours": {"start": 23, "end": 23}}, at("23:30")) is False)
ok("标签", quiet_label(cfg) == "23:00–08:00", quiet_label(cfg))

print("\n全部通过" if fail == 0 else f"\n{fail} 项失败")
sys.exit(0 if fail == 0 else 1)
