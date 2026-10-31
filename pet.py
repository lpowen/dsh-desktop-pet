# -*- coding: utf-8 -*-
"""
桌面分身：一个坐在桌面上的她。

- 透明无边框、置顶、可拖动
- 单击说话、右键菜单、气泡对话
- 闲着会自己冒话（主动行为来自 brain.mjs）
- 和 QQ 机器人共用同一个「意识」（人格 + 记忆 + 作息）

启动：python pet.py
依赖：tkinter（Python 自带）、Pillow 仅用于生成素材
"""
import json
import os
import queue
import random
import sys
import threading
import time
import tkinter as tk
from tkinter import simpledialog
from urllib import request as urlreq

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
    CFG = json.load(f)

from quiet import is_quiet, quiet_label

KEY = "#ff00fe"           # 抠图色，和 make_sprites.py 里一致
ASSETS = os.path.join(HERE, "assets")
CHAR_ROOT = os.path.join(HERE, "characters")
STATE = os.path.join(HERE, CFG.get("stateDir", "state"))
os.makedirs(STATE, exist_ok=True)

# 用户点「退出」时写这个标记；启动器/看门狗看到就不再把桌宠拉起来
STOPPED_FLAG = os.path.join(STATE, "pet.stopped")


def character_dirs():
    """可用形象：默认（assets）+ characters/* 子目录，按 idle.png 判断是否有效。"""
    found = [("阿柒", ASSETS)]
    if os.path.isdir(CHAR_ROOT):
        for name in sorted(os.listdir(CHAR_ROOT)):
            d = os.path.join(CHAR_ROOT, name)
            if os.path.isdir(d) and os.path.exists(os.path.join(d, "idle.png")):
                found.append((name, d))
    return found


LOG_PATH = os.path.join(STATE, "pet.log")


def log(msg):
    """把输入框焦点、按键这类问题记下来，排查用。"""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass

BRAIN = CFG.get("brainUrl", "http://127.0.0.1:4399")
NAME = CFG.get("name", "阿柒")
BUBBLE_MS = int(CFG.get("bubbleMs", 9000))
POS_FILE = os.path.join(STATE, "pos.json")
SESSION_KEY = "desk:owner"

FONT = ("Microsoft YaHei UI", 10)
FONT_SM = ("Microsoft YaHei UI", 9)
BG = "#1f1b2e"
FG = "#eee9fb"

# Win32：把窗口真正提到所有置顶窗口之上（Tk 的 lift() 抢不过 Electron 的置顶窗）
_MUTEX_HANDLE = None

def already_running():
    """单实例：命名互斥量。已有桌宠在跑时返回 True（防止看门狗/手动同时拉起两个）。"""
    global _MUTEX_HANDLE
    if os.name != "nt":
        return False
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        _MUTEX_HANDLE = kernel32.CreateMutexW(None, False, "Local\\dsh-desktop-pet")
        return ctypes.get_last_error() == 183   # ERROR_ALREADY_EXISTS
    except Exception:
        return False

if os.name == "nt":
    import ctypes
    _user32 = ctypes.windll.user32
    HWND_TOPMOST = -1
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOACTIVATE = 0x0010

    def raise_window(win):
        try:
            hwnd = _user32.GetParent(win.winfo_id()) or win.winfo_id()
            _user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                 SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
        except Exception:
            pass
else:
    def raise_window(win):
        try:
            win.lift()
        except Exception:
            pass


# --------------------------------------------------------------- HTTP 小工具

def get_json(url, timeout=10):
    with urlreq.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def post_json(url, payload, timeout=180):
    data = json.dumps(payload).encode("utf-8")
    req = urlreq.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urlreq.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# -------------------------------------------------------------------- 桌宠

class Pet:
    def __init__(self, root):
        self.root = root
        try:
            with open(os.path.join(STATE, "pet.pid"), "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
        except Exception:
            pass
        self.character = CFG.get("character") or ""
        self.frames = {}
        self.w, self.h = 240, 280
        self.load_frames(self.dir_for(self.character), initial=True)

        self.chat = None
        self.chat_text = None
        self.chat_entry = None
        self.bubble = None
        self.bubble_job = None
        self.sleeping = False
        self.manualAwakeUntil = 0
        self._restore_job = None
        self._last_hotkey = 0
        self.memory_win = None

        self.busy = False
        self.moved = False
        self.press_xy = (0, 0)
        self.last_id = 0
        self.inbox = queue.Queue()

        x, y = self.load_pos()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        # 上次位置如果跑出屏幕（换显示器/改分辨率），拉回来
        x = max(20, min(x, sw - self.w - 20))
        y = max(20, min(y, sh - self.h - 60))
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        if os.environ.get("PET_OPAQUE"):
            root.configure(bg="#2b2438")
        else:
            try:
                root.attributes("-transparentcolor", KEY)
            except tk.TclError:
                pass
            root.configure(bg=KEY)
        root.geometry(f"{self.w}x{self.h}+{x}+{y}")

        self.canvas = tk.Canvas(root, width=self.w, height=self.h, bg=KEY,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.sprite = self.canvas.create_image(0, 0, anchor="nw", image=self.frames["idle"])

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_menu)
        root.bind("<Escape>", lambda e: None)

        self.set_face("idle")
        self.bind_idle_anim()
        self.root.after(300, self.bob_loop)
        self.root.after(400, self.hotkey_loop)
        self.root.after(900, self.check_quiet_loop)
        self.root.after(150, lambda: raise_window(self.root))
        self.root.after(600, self.drain_inbox)
        self.root.after(1200, self.keep_on_top)
        threading.Thread(target=self.poll_loop, daemon=True).start()
        self.root.after(900, self.check_brain)

    def keep_on_top(self):
        """overrideredirect 窗口容易失去置顶，定时重新抢一次。"""
        try:
            if self.root.state() != "withdrawn":
                self.root.attributes("-topmost", True)
                raise_window(self.root)
            if self.chat is not None and self.chat.winfo_exists():
                self.chat.attributes("-topmost", True)
                raise_window(self.chat)
        except tk.TclError:
            pass
        self.root.after(2500, self.keep_on_top)

    # ---------------------------------------------------------------- 位置

    def dir_for(self, name):
        if name:
            d = os.path.join(CHAR_ROOT, name)
            if os.path.exists(os.path.join(d, "idle.png")):
                return d
        return ASSETS

    def load_frames(self, dirpath, initial=False):
        frames = {}
        for name in ("idle", "blink", "talk", "happy", "sleepy"):
            p = os.path.join(dirpath, f"{name}.png")
            if os.path.exists(p):
                frames[name] = tk.PhotoImage(file=p)
        if not frames:
            return False
        self.frames = frames
        self.w = frames["idle"].width()
        self.h = frames["idle"].height()
        if not initial:
            self.canvas.configure(width=self.w, height=self.h)
            x, y = self.root.winfo_x(), self.root.winfo_y()
            self.root.geometry(f"{self.w}x{self.h}+{x}+{y}")
            self.canvas.itemconfig(self.sprite, image=self.frames["idle"])
            self.set_face("idle")
        return True

    def switch_character(self):
        options = character_dirs()
        cur = self.character
        idx = next((i for i, (n, d) in enumerate(options)
                    if (cur and n == cur) or (not cur and d == ASSETS)), 0)
        name, d = options[(idx + 1) % len(options)]
        self.character = "" if d == ASSETS else name
        self.load_frames(d)
        self.save_character(self.character)
        self.say("变回阿柒啦。" if not self.character else f"换好啦，现在是{name}。")

    def save_character(self, name):
        try:
            p = os.path.join(HERE, "config.json")
            with open(p, encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["character"] = name
            with open(p, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_pos(self):
        try:
            with open(POS_FILE, encoding="utf-8") as f:
                p = json.load(f)
                return int(p["x"]), int(p["y"])
        except Exception:
            return int(CFG.get("startX", 1100)), int(CFG.get("startY", 560))

    def save_pos(self):
        try:
            with open(POS_FILE, "w", encoding="utf-8") as f:
                json.dump({"x": self.root.winfo_x(), "y": self.root.winfo_y()}, f)
        except Exception:
            pass

    # ---------------------------------------------------------------- 拖拽

    def on_press(self, e):
        self.press_xy = (e.x_root, e.y_root)
        self.drag_origin = (self.root.winfo_x() - e.x_root, self.root.winfo_y() - e.y_root)
        self.moved = False

    def on_drag(self, e):
        dx = abs(e.x_root - self.press_xy[0])
        dy = abs(e.y_root - self.press_xy[1])
        if dx + dy > 4:
            self.moved = True
        if self.moved:
            x = self.drag_origin[0] + e.x_root
            y = self.drag_origin[1] + e.y_root
            self.root.geometry(f"+{x}+{y}")

    def on_release(self, e):
        if self.moved:
            self.save_pos()
        else:
            self.open_chat()

    def on_menu(self, e):
        m = tk.Menu(self.root, tearoff=0, font=FONT)
        m.add_command(label=f"和{NAME}说话", command=self.open_chat)
        m.add_command(label="让她主动说一句", command=self.force_think)
        m.add_separator()
        m.add_command(label="记住一件事…", command=self.remember_dialog)
        m.add_command(label="看看她记得什么", command=self.show_memory)
        m.add_separator()
        m.add_command(label="换个位置", command=self.wander)
        m.add_command(label="换个形象", command=self.switch_character)
        m.add_command(label="隐藏 / 显示（Ctrl+Alt+P 恢复）", command=self.toggle_hide)
        m.add_command(label="睡觉 / 起床", command=self.toggle_sleep)
        m.add_command(label="退出", command=self.quit)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def wander(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = random.randint(60, max(60, sw - self.w - 60))
        y = random.randint(60, max(60, sh - self.h - 80))
        self.root.geometry(f"+{x}+{y}")
        self.save_pos()

    def toggle_hide(self):
        if self.root.state() == "withdrawn":
            self.show_pet("toggle")
        else:
            self.hide_pet()

    def hide_pet(self):
        """隐藏只是 withdraw，所以必须留一条回来的路：全局热键 + 定时自动恢复。"""
        self.root.withdraw()
        minutes = int(CFG.get("autoShowMinutes", 10))
        if self._restore_job is not None:
            try:
                self.root.after_cancel(self._restore_job)
            except Exception:
                pass
        self._restore_job = self.root.after(minutes * 60 * 1000, lambda: self.show_pet("auto"))
        log(f"pet hidden; Ctrl+Alt+P or {minutes} min 后自动恢复")

    def show_pet(self, why="manual"):
        self._restore_job = None
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.update_idletasks()
        raise_window(self.root)
        self.save_pos()
        log(f"pet shown ({why})")

    def hotkey_loop(self):
        """全局热键 Ctrl+Alt+P：窗口被 withdraw 时也能把桌宠叫回来。"""
        try:
            if os.name == "nt":
                u = _user32
                down = (u.GetAsyncKeyState(0x11) & 0x8000) and \
                       (u.GetAsyncKeyState(0x12) & 0x8000) and \
                       (u.GetAsyncKeyState(0x50) & 0x8000)
                if down and time.time() - getattr(self, "_last_hotkey", 0) > 0.8:
                    self._last_hotkey = time.time()
                    log("hotkey Ctrl+Alt+P")
                    self.toggle_hide()
        except Exception as e:
            log(f"hotkey loop error: {e}")
        self.root.after(150, self.hotkey_loop)

    def quit(self):
        self.save_pos()
        try:
            os.remove(os.path.join(STATE, "pet.pid"))
        except Exception:
            pass
        # 用户主动退出：留个标记，看门狗/启动器就不会再把桌宠拉起来
        try:
            with open(STOPPED_FLAG, "w", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception:
            pass
        log("pet 已退出（不会再被自动拉起，直到下次手动启动）")
        self.root.destroy()

    # ---------------------------------------------------------------- 睡眠

    def apply_sleep(self, on):
        on = bool(on)
        if on == self.sleeping:
            return
        self.sleeping = on
        if on:
            self.set_face("sleepy")
            try:
                self.root.attributes("-alpha", 0.82)
            except tk.TclError:
                pass
            if self.bubble is not None:
                try:
                    self.bubble.destroy()
                except tk.TclError:
                    pass
                self.bubble = None
            if self.chat is not None:
                try:
                    self.chat.withdraw()
                except tk.TclError:
                    pass
            log(f"pet 睡着（{quiet_label(CFG)}）")
        else:
            try:
                self.root.attributes("-alpha", 1.0)
            except tk.TclError:
                pass
            self.set_face("idle")
            log("pet 醒了")

    def check_quiet_loop(self):
        """每分钟看一次到没到静默时段；手动「起床」后 30 分钟内不再压回去。"""
        try:
            want = is_quiet(CFG)
            if want and self.manualAwakeUntil > time.time():
                want = False
            self.apply_sleep(want)
        except Exception as e:
            log(f"quiet check error: {e}")
        self.root.after(60000, self.check_quiet_loop)

    def toggle_sleep(self):
        if self.sleeping:
            self.manualAwakeUntil = time.time() + 1800
            self.apply_sleep(False)
            self.say("唔…我醒啦（30 分钟内不会再睡）")
        else:
            self.manualAwakeUntil = 0
            self.apply_sleep(True)
            self.say("好，那我先睡一会儿，晚安～")

    # ---------------------------------------------------------------- 表情

    def set_face(self, name, hold_ms=None, then="idle"):
        if name not in self.frames:
            return
        self.canvas.itemconfig(self.sprite, image=self.frames[name])
        if hold_ms:
            self.root.after(hold_ms, lambda: self.set_face(then))

    def bind_idle_anim(self):
        """随机换表情 / 眨眼；素材没有 blink 帧时会自动跳过。"""
        faces = [f for f in (CFG.get("idleFaces") or ["idle", "idle", "idle", "blink", "sleepy"])
                 if f in self.frames]

        def loop():
            if not self.busy and not self.sleeping:
                face = random.choice(faces) if faces else "idle"
                hold = 150 if face == "blink" else random.randint(900, 1800)
                self.set_face(face, hold_ms=hold, then="idle")
            self.root.after(random.randint(2600, 6200), loop)
        self.root.after(2000, loop)

    def bob_loop(self):
        """静态立绘的呼吸感：整体上下浮动几像素。睡着时不浮动。"""
        if not self.busy and not self.sleeping:
            self._bob = 0 if getattr(self, "_bob", -3) == -3 else -3
            try:
                self.canvas.coords(self.sprite, 0, self._bob)
            except tk.TclError:
                return
        self.root.after(1800, self.bob_loop)

    # ---------------------------------------------------------------- 气泡

    def say(self, text, ms=None):
        if self.bubble is not None:
            try:
                self.bubble.destroy()
            except tk.TclError:
                pass
        text = (text or "").strip()
        if not text:
            return
        ms = ms or min(BUBBLE_MS + len(text) * 90, 30000)

        top = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.configure(bg="#ffffff")

        frame = tk.Frame(top, bg="#ffffff", highlightbackground="#2a2438",
                         highlightthickness=2, padx=12, pady=9)
        frame.pack()
        tk.Label(frame, text=text, bg="#ffffff", fg="#1f1b2e", font=FONT,
                 wraplength=250, justify="left").pack()

        top.update_idletasks()
        bw, bh = top.winfo_reqwidth(), top.winfo_reqheight()
        px, py = self.root.winfo_x(), self.root.winfo_y()
        sw = self.root.winfo_screenwidth()
        x = max(10, min(px + self.w // 2 - bw // 2, sw - bw - 10))
        y = max(10, py - bh - 6)
        top.geometry(f"+{x}+{y}")
        raise_window(top)
        self.bubble = top
        self.bubble_job = self.root.after(ms, self.hide_bubble)
        self.set_face("happy", hold_ms=1200)

    def hide_bubble(self):
        if self.bubble is not None:
            try:
                self.bubble.destroy()
            except tk.TclError:
                pass
            self.bubble = None

    # ---------------------------------------------------------------- 聊天窗

    def open_chat(self):
        if self.sleeping:
            self.say(f"zZz…（{quiet_label(CFG)} 是我睡觉的时间，明早再来找我吧）")
            return
        if self.chat is not None and self.chat.winfo_exists():
            self.chat.deiconify()
            self.chat.lift()
            self.chat.focus_force()
            self.chat_entry.focus_force()
            return

        win = tk.Toplevel(self.root)
        win.title(f"{NAME} · 桌面对话")
        win.configure(bg=BG)
        win.geometry(self.chat_geometry())
        win.attributes("-topmost", True)
        win.resizable(True, True)

        head = tk.Label(win, text=f"  {NAME}", bg=BG, fg=FG,
                        font=("Microsoft YaHei UI", 11, "bold"), anchor="w")
        head.pack(side="top", fill="x", pady=(8, 2))

        # 先给底部输入区占位（顺序很重要：body 的 expand 会把后 pack 的控件挤成 0 高）
        bar = tk.Frame(win, bg=BG)
        bar.pack(side="bottom", fill="x", padx=10, pady=(2, 10))
        self.chat_entry = tk.Entry(bar, bg="#f3f0fb", fg="#1f1b2e",
                                   font=("Microsoft YaHei UI", 11), bd=0,
                                   insertbackground="#1f1b2e", relief="flat",
                                   disabledbackground="#f3f0fb")
        self.chat_entry.pack(side="left", fill="x", expand=True, ipady=9)
        self.chat_entry.bind("<Return>", lambda e: (self.send(), "break")[1])
        tk.Button(bar, text="发送", command=self.send, bg="#6b5f96", fg="white",
                  bd=0, font=FONT, padx=16).pack(side="left", padx=(8, 0), ipady=7)

        hint = tk.Label(win, text="在下面输入，回车发送", bg=BG, fg="#8a83a3",
                        font=FONT_SM, anchor="w")
        hint.pack(side="bottom", fill="x", padx=12)

        body = tk.Frame(win, bg=BG)
        body.pack(side="top", fill="both", expand=True, padx=10, pady=6)
        self.chat_text = tk.Text(body, bg="#151221", fg=FG, font=FONT, wrap="word",
                                 bd=0, padx=10, pady=8, insertbackground=FG,
                                 height=10, width=30, cursor="arrow")
        self.chat_text.pack(fill="both", expand=True)
        self.chat_text.configure(state="disabled")
        self.append_chat(f"{NAME}：在的，直接说就好。", who="her")

        # 点窗口任何地方都把焦点交给输入框（之前点大块文本区会没反应）
        for w in (win, head, body, self.chat_text, hint):
            w.bind("<Button-1>", lambda e: self.focus_entry(), add="+")
        # 窗口自己拿到焦点时，转给输入框
        win.bind("<FocusIn>", lambda e: self.focus_entry() if e.widget is win else None, add="+")
        # 兜底：即使焦点在窗口上，敲字也直接灌进输入框
        win.bind("<KeyPress>", self.route_key, add="+")
        win.bind("<Return>", lambda e: (self.send(), "break")[1])
        self.chat_entry.bind("<KeyPress>", lambda e: log(f"key {e.char!r}"), add="+")

        self.chat = win
        raise_window(win)
        win.lift()
        win.update_idletasks()
        self.focus_entry_retry()
        win.after(600, self.dump_focus)
        log("chat window opened")

    def focus_entry_retry(self, tries=8):
        """窗口刚建好时 Entry 可能还没映射，重试几次直到焦点真的落上去。"""
        self.focus_entry()
        try:
            got = self.root.focus_get()
        except tk.TclError:
            got = None
        if got is not self.chat_entry and tries > 0:
            self.chat.after(120, lambda: self.focus_entry_retry(tries - 1))
        else:
            log(f"focus settled on {got.__class__.__name__ if got is not None else None}")

    def focus_entry(self):
        try:
            self.chat_entry.focus_force()
            self.chat_entry.focus_set()
        except tk.TclError:
            pass

    def route_key(self, e):
        """兜底输入：只在焦点不在输入框时接管，否则交给 Entry 自己处理（否则会插入两次）。"""
        try:
            if self.root.focus_get() is self.chat_entry:
                return None
        except tk.TclError:
            pass

        if e.char and e.char.isprintable():
            self.chat_entry.insert("end", e.char)
            return "break"
        if e.keysym == "Return":
            self.send()
            return "break"
        if e.keysym == "BackSpace":
            cur = self.chat_entry.get()
            self.chat_entry.delete(0, "end")
            self.chat_entry.insert(0, cur[:-1])
            return "break"
        return None

    def dump_focus(self):
        try:
            def name(w):
                return w.__class__.__name__ if w is not None else None
            log(f"focus root={name(self.root.focus_get())} "
                f"chat={name(self.chat.focus_get() if self.chat else None)} "
                f"entry={name(self.chat_entry.focus_get() if self.chat_entry else None)} "
                f"entry_mapped={self.chat_entry.winfo_ismapped()}")
        except Exception as e:
            log(f"focus_get error {e}")

    def chat_geometry(self):
        px, py = self.root.winfo_x(), self.root.winfo_y()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = min(max(10, px - 320), sw - 400)
        y = min(max(10, py - 120), sh - 460)
        return f"380x420+{x}+{y}"

    def append_chat(self, line, who="me"):
        if self.chat_text is None:
            return None
        tag = "her" if who == "her" else "me"
        self.chat_text.configure(state="normal")
        pos = self.chat_text.index("end-1c")
        prefix = "" if pos == "1.0" else "\n"
        self.chat_text.insert("end", prefix + line + "\n", tag)
        self.chat_text.tag_configure("her", foreground="#c8b6ff")
        self.chat_text.tag_configure("me", foreground="#8fe3c0")
        self.chat_text.configure(state="disabled")
        self.chat_text.see("end")
        return pos

    def send(self):
        if self.busy or self.chat_entry is None:
            log(f"send ignored (busy={self.busy})")
            return
        text = self.chat_entry.get().strip()
        if not text:
            return
        log(f"send {text!r}")
        self.chat_entry.delete(0, "end")
        self.append_chat(f"你：{text}", who="me")
        self.busy = True
        self.set_face("talk")
        placeholder = self.append_chat(f"{NAME}：……", who="her")

        def worker():
            try:
                out = post_json(f"{BRAIN}/chat",
                                {"key": SESSION_KEY, "text": text, "surface": "desk"},
                                timeout=180)
                reply = (out.get("reply") or "").strip() or "（这次没想出来）"
            except Exception as e:
                reply = f"（意识服务没连上：{e}）"

            def done():
                self.busy = False
                if placeholder is not None:
                    self.chat_text.configure(state="normal")
                    self.chat_text.delete(placeholder, "end")
                    self.chat_text.configure(state="disabled")
                self.append_chat(f"{NAME}：{reply}", who="her")
                self.set_face("happy", hold_ms=1200)
                self.say(reply)
            self.root.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    # ---------------------------------------------------------------- 记忆

    def remember_dialog(self):
        fact = simpledialog.askstring(f"记住一件事 · {NAME}", "要她记住什么？", parent=self.root)
        if not fact:
            return
        try:
            post_json(f"{BRAIN}/memory", {"fact": fact}, timeout=15)
            self.say("记住了喵。")
        except Exception as e:
            self.say(f"没记住：{e}")

    def show_memory(self):
        try:
            facts = get_json(f"{BRAIN}/memory").get("facts", [])
        except Exception as e:
            self.say(f"读不到记忆：{e}")
            return

        if self.memory_win is not None and self.memory_win.winfo_exists():
            self.memory_win.lift()
            return

        win = tk.Toplevel(self.root)
        win.title(f"{NAME} 的记忆")
        win.configure(bg=BG)
        win.geometry("360x400+" + str(self.root.winfo_x() - 340) + "+" + str(self.root.winfo_y()))
        win.attributes("-topmost", True)

        tk.Label(win, text="长期记忆（会一直带着）", bg=BG, fg=FG, font=FONT).pack(anchor="w", padx=12, pady=(10, 6))
        txt = tk.Text(win, bg="#151221", fg=FG, font=FONT_SM, wrap="word", bd=0, padx=10, pady=8)
        txt.pack(fill="both", expand=True, padx=12)
        txt.insert("1.0", "\n".join(f"· {x}" for x in facts) if facts else "（还什么都没记住）")
        txt.configure(state="disabled")

        tk.Button(win, text="清空记忆（不可恢复）", bg="#3a2b3f", fg="#ffb3c6", bd=0,
                  font=FONT_SM, command=lambda: self.clear_memory(win)).pack(pady=10)
        self.memory_win = win

    def clear_memory(self, win):
        try:
            post_json(f"{BRAIN}/memory/clear", {}, timeout=15)
            win.destroy()
            self.say("我从头认识你一次喵。")
        except Exception as e:
            self.say(f"清空失败：{e}")

    # ------------------------------------------------------------ 主动消息

    def force_think(self):
        if self.busy:
            return
        self.busy = True
        self.set_face("talk")

        def worker():
            try:
                out = post_json(f"{BRAIN}/think", {}, timeout=120)
                item = out.get("item")
                text = item["text"] if item else "（她这会儿没想说什么）"
                self.last_id = max(self.last_id, item["id"]) if item else self.last_id
            except Exception as e:
                text = f"（想不出来：{e}）"

            def done():
                self.busy = False
                self.set_face("happy", hold_ms=900)
                self.say(text)
            self.root.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def poll_loop(self):
        while True:
            try:
                data = get_json(f"{BRAIN}/proactive?since={self.last_id}", timeout=8)
                for it in data.get("items", []):
                    self.last_id = max(self.last_id, int(it["id"]))
                    self.inbox.put(it.get("text", ""))
            except Exception:
                pass
            time.sleep(12)

    def drain_inbox(self):
        try:
            while True:
                text = self.inbox.get_nowait()
                if text:
                    self.say(text)
                    if self.chat is not None and self.chat.winfo_exists():
                        self.append_chat(f"{NAME}：{text}", who="her")
        except queue.Empty:
            pass
        self.root.after(700, self.drain_inbox)

    # ---------------------------------------------------------------- 启动

    def check_brain(self):
        try:
            info = get_json(f"{BRAIN}/health", timeout=3)
            self.say(f"{info.get('name', NAME)} 醒着了喵。")
        except Exception:
            self.say("意识服务没启动，先运行 启动桌宠.cmd。")


def main():
    root = tk.Tk()
    root.title(NAME)
    if already_running():
        log("已经有一只桌宠在跑了，这个实例直接退出")
        root.destroy()
        return
    # 只要是「手动启动」，就清掉上次的退出标记（看门狗看到标记会一直跳过）
    try:
        if os.path.exists(STOPPED_FLAG):
            os.remove(STOPPED_FLAG)
            log("已清除上次的退出标记（手动启动）")
    except Exception:
        pass
    pet = Pet(root)
    root.protocol("WM_DELETE_WINDOW", pet.quit)

    # 自测/演示参数：--open-chat 打开聊天窗，--say 立刻说一句
    if "--open-chat" in sys.argv:
        root.after(2500, pet.open_chat)
    if "--say" in sys.argv:
        i = sys.argv.index("--say")
        if i + 1 < len(sys.argv):
            root.after(800, lambda: pet.say(sys.argv[i + 1]))
    if "--think" in sys.argv:
        root.after(1200, pet.force_think)
    if "--selftest-hide" in sys.argv:
        root.after(3000, pet.hide_pet)
        root.after(5000, pet.toggle_hide)   # 走和热键同一条恢复路径
    if "--selftest-type" in sys.argv:
        def type_test():
            pet.focus_entry()
            for ch in "abc":
                pet.chat_entry.event_generate("<KeyPress>", keysym=ch)
                pet.root.update()
            root.after(250, lambda: log(f"typed={pet.chat_entry.get()!r} len={len(pet.chat_entry.get())}"))
        root.after(3600, type_test)
    if "--selftest-quit" in sys.argv:
        root.after(3000, pet.quit)
    if "--selftest-sleep" in sys.argv:
        def sleep_test():
            pet.apply_sleep(False)
            log("selftest: 已强制醒来")
            root.after(2500, lambda: (pet.apply_sleep(True), log("selftest: 已强制睡着")))
        root.after(4000, sleep_test)
    if "--selftest-send" in sys.argv:
        idx = sys.argv.index("--selftest-send")
        text = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "测试一下"
        def auto_send():
            pet.chat_entry.focus_force()
            pet.chat_entry.insert(0, text)
            pet.send()
        root.after(3200, auto_send)

    root.mainloop()


if __name__ == "__main__":
    main()
