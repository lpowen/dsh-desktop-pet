# 桌宠是怎么实现的

一份「给自己看的实现说明」：讲清楚每一层在做什么、为什么这么做、踩过哪些坑。
代码在 [pet.py](pet.py)（约 660 行），大脑在 [brain.mjs](brain.mjs)。

---

## 0. 全景

```
┌──────────── 素材层（静态） ────────────┐
│ characters/<名字>/{idle,blink,talk,happy,sleepy}.png │
│ 240~500px、背景填 #FF00FE（抠图色）                    │
└───────────────┬────────────────────────┘
                │ tk.PhotoImage 加载
┌───────────────▼────────────────────────┐
│ 渲染层：一个 240×300 左右的无边框窗口     │
│  overrideredirect + topmost + 色键透明   │
└───────────────┬────────────────────────┘
                │ 鼠标 / 键盘
┌───────────────▼────────────────────────┐
│ 交互层：拖拽、点击开对话、右键菜单、气泡  │
└───────────────┬────────────────────────┘
                │ HTTP (urllib)
┌───────────────▼────────────────────────┐
│ 大脑：brain.mjs :4399                   │
│  人格 + 分层记忆 + 称呼 + 主动行为        │
└───────────────┬────────────────────────┘
                │ spawn
┌───────────────▼────────────────────────┐
│ dsh --profile qq（每轮一个进程）          │
└────────────────────────────────────────┘
```

**为什么不用 Electron**：一个透明窗 + 5 张 PNG + 一个输入框，Tk 足够；Electron 要多带 100MB 运行时和一套构建流程。
**为什么不用 Live2D**：需要专有渲染运行时，而且素材要建模。静态帧 + 少量变换已经能有「活着」的感觉。

---

## 1. 透明窗口：色键，而不是 alpha

```python
root.overrideredirect(True)          # 去掉标题栏/边框，不进任务栏
root.attributes("-topmost", True)    # 置顶
root.attributes("-transparentcolor", "#ff00fe")   # 指定颜色透明
root.configure(bg="#ff00fe")
```

`-transparentcolor` 是 **chroma key**（色键）：窗口里等于这个颜色的像素变全透明，其余全不透明——**没有中间透明度**。

所以素材必须是「以 `#ff00fe` 为底、alpha 要么 0 要么 255」的图。生成时这么做：

```python
small = img.resize((W, H), Image.LANCZOS)   # 先按目标尺寸缩放（带抗锯齿）
for y in range(H):                          # 再二值化：alpha ≥ 120 保留，否则填抠图色
    for x in range(W):
        r, g, b, a = px[x, y]
        op[x, y] = (r, g, b) if a >= 120 else KEY
```

顺序很重要：**先缩放再二值化**。反过来会得到锯齿边；先二值化再缩放会把边缘糊成半透明色块，边缘泛紫。

> 这也是为什么这套东西做不出封面上那种柔和发光——那是真 alpha。要真 alpha 得换成
> Win32 的分层窗口（`UpdateLayeredWindow`）+ 预乘 alpha 的位图，Tk 不做这个。

## 2. 置顶：Tk 抢不过别人的置顶窗

一开始只写 `-topmost` 就完事，结果桌宠被 DSH 的窗口压住了。原因是：所有 `topmost` 窗口在同一个 Z 序带里，谁最后被激活谁在上面。

对策：直接调 Win32，每隔 2.5 秒重抢一次（[pet.py:77](pet.py#L77)、[pet.py:166](pet.py#L166)）：

```python
_user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                     SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)   # 注意 NOACTIVATE：不抢焦点
```

`SWP_NOACTIVATE` 很关键——否则每 2.5 秒你正在别处打字，焦点被抢走。

## 3. 帧动画：不是在放 GIF

五个状态就是五张静态图，`tk.PhotoImage` 各存一份：

```python
self.frames = {"idle": ..., "blink": ..., "talk": ..., "happy": ..., "sleepy": ...}
self.canvas.itemconfig(self.sprite, image=self.frames[name])   # 切图就是换 image
```

三种「动」叠在一起：

| 动作 | 实现 | 频率 |
| --- | --- | --- |
| 换表情 | `bind_idle_anim` 随机挑 idle/happy/sleepy，`after` 到时切回 idle（[pet.py:312](pet.py#L312)） | 2.6~6.2 秒 |
| 呼吸 | `bob_loop` 把图上下挪 3px（`canvas.coords`）（[pet.py:325](pet.py#L325)） | 1.8 秒 |
| 说话/思考 | `set_face("talk")` / 切 happy（[pet.py:305](pet.py#L305)） | 事件驱动 |

素材里没有 blink 帧时（比如帕秋莉那套），`bind_idle_anim` 会用 `faces` 过滤掉不存在的状态，不会 KeyError。

## 4. 拖拽 vs 点击：4px 阈值

```python
def on_press(self, e):   # 记下按下位置和窗口原点
def on_drag(self, e):    # 位移 > 4px 才认为是拖拽，然后移动窗口
def on_release(self, e): # 没拖过 → 当成点击，打开对话
```

（[pet.py:246](pet.py#L246) 起）没有这个阈值，手一抖就变成拖拽，点不开对话。

位置会存到 `state/pos.json`；启动时如果坐标跑到屏幕外（换显示器 / 改分辨率），会被钳制回来。

## 5. 气泡：一个会自己消失的 Toplevel

```python
top = tk.Toplevel(self.root); top.overrideredirect(True); top.attributes("-topmost", True)
...
x = max(10, min(px + self.w // 2 - bw // 2, sw - bw - 10))   # 水平居中在头顶，且不出屏
y = max(10, py - bh - 6)                                    # 贴在头顶上方
self.bubble_job = self.root.after(ms, self.hide_bubble)      # 到点销毁
```
（[pet.py:337](pet.py#L337)）

停留时间跟字数挂钩（`BUBBLE_MS + 字数 × 90ms`，上限 30 秒），否则长句子还没读完就没了。

## 6. 对话窗：一个真正的坑

第一版窗口打开后**打不了字**。查下来是布局问题：

```python
body.pack(fill="both", expand=True)   # Text 的默认请求尺寸是 80×24，很大
...
bar.pack(fill="x")                    # 后 pack 的控件被挤成 0 高度
```

pack 是按顺序分配空间的：`Text` 先把自己的请求尺寸占满，后 pack 的输入栏只分到 0 高度——所以窗口看着正常，底部根本没有输入框（`winfo_ismapped()` 返回 0）。

正确顺序：**底部栏先 pack（`side="bottom"`），消息区最后 expand**：

```python
head.pack(side="top", ...)
bar.pack(side="bottom", ...)     # 输入框 + 发送按钮
hint.pack(side="bottom", ...)    # 「在下面输入，回车发送」
body.pack(side="top", fill="both", expand=True)   # 消息区吃掉剩下的空间
self.chat_text = tk.Text(body, height=10, width=30)   # 给个小请求尺寸
```

（[pet.py:381](pet.py#L381)）

还有一个焦点问题：Toplevel 拿到焦点时，`focus_get()` 返回的是 Toplevel 而不是 Entry，键就丢了。对策是三层的：

```python
win.bind("<FocusIn>", lambda e: self.focus_entry())      # 窗口拿到焦点就转给输入框
self.focus_entry_retry()                                  # 重试 8 次（窗口刚建好时 Entry 可能还没 map）
win.bind("<KeyPress>", self.route_key)                    # 兜底：字直接塞进 Entry
```

（[pet.py:443](pet.py#L443)、[pet.py:462](pet.py#L462)）

## 7. 和她说话：线程 + after

Tk 不是线程安全的，不能在工作线程里直接改界面。所以：

```python
def send(self):
    self.busy = True
    self.set_face("talk")
    threading.Thread(target=worker, daemon=True).start()   # 线程里发 HTTP
    # worker 拿到结果后：
    self.root.after(0, done)                               # 回到主线程再改界面
```

请求体就是给大脑的：

```json
{"key": "desk:owner", "text": "…", "surface": "desk"}
```

`key` 决定记忆归属：`desk:` 前缀归到 `owner` 作用域，所以桌面上聊的内容，QQ 里她也记得。

同理，**主动说话**是另一个线程每 12 秒轮询 `/proactive`，把新消息塞进 `queue.Queue`，主线程用 `after(700)` 取（[pet.py:617](pet.py#L617)、[pet.py:628](pet.py#L628)）。

## 8. 换形象：目录约定 + 运行时重载

```python
def dir_for(self, name):           # characters/<name>/ 存在就用它，否则用 assets/
def load_frames(self, dirpath):    # 重新读 5 张 PNG，更新 w/h，窗口跟着 resize
def switch_character(self):        # 右键菜单里轮换，写回 config.json
```
（[pet.py:181](pet.py#L181) 起）

不同形象的尺寸可以不同（阿柒 240×280、灵梦 360×420），窗口会自适应；气泡位置、拖拽坐标都是按 `self.w/h` 算的，所以不用改别处。

## 9. 没有控制台窗口

- 用 `pythonw.exe` 启动（不是 `python.exe`），没有控制台；
- 父进程用 VBS + `WScript.Shell.Run(..., 0, False)` 隐藏启动；
- dsh 子进程用 `spawn(..., { windowsHide: true })`，每轮对话都不会闪窗。

验证方法很土但有效：数屏幕上有多少个 `ConsoleWindowClass` 窗口。

## 10. 踩过的坑（真实记录）

| 现象 | 原因 | 对策 |
| --- | --- | --- |
| 窗口看不到 | 坐标跑到 1707px 屏幕外 | 启动时钳制到屏幕内 |
| 被别的窗口压住 | `topmost` 也在同一个 Z 序带 | 定时 `SetWindowPos(HWND_TOPMOST)` |
| 截图里没有它 | 截图 API 抓不到分层/透明窗 | 用 `PrintWindow` 直接渲染窗口验证 |
| 输入框点不出来 | `Text` 的 `expand` 把它挤成 0 高 | 底部先 pack |
| 能看不能打字 | 焦点停在 Toplevel 上 | `FocusIn` 转发 + 重试 + 键盘兜底 |
| 边缘发紫 | 缩放后再二值化 | 先缩放，再二值化 |
| 一条消息回两次 | 两个桥接进程 | 单实例锁 + 消息幂等（那是 QQ 侧的坑） |

## 11. 想改的话，从哪下手

| 目标 | 改哪里 |
| --- | --- |
| 换形象 | 往 `characters/<名字>/` 放 5 张 PNG（背景 `#FF00FE`），右键切换 |
| 改表情频率/组合 | `config.json` 的 `idleFaces` |
| 改气泡时长/位置 | `say()` 里的 `ms` 和坐标计算 |
| 改对话窗样式 | `open_chat()`（注意保持底部先 pack 的顺序） |
| 让她主动说话 | `brain.mjs` 的 `think()` / `tick()`（作息、间隔在 `config.json`） |
| 加新交互（双击、滚轮） | `on_press/on_drag/on_release` 附近加 bind |

## 12. 已知上限

- **没有真 alpha**：柔光、半透明发丝、投影都做不了（色键只有全透/全不透）；
- **没有 Live2D**：素材是静态帧，动作靠位移和换图模拟；
- **单实例串行**：一次只有一个请求在跑，`busy` 期间不响应新的发送；
- **依赖 Python + Tk**：DSH 自带的运行时里有，但换机器要确认路径（`启动（无窗口）.vbs` 里写死了）。
