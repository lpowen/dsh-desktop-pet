# 桌宠 · 和 QQ 机器人共用一个「意识」

参考 B 站视频里那个 **SurfCore** 的设计（一个身份、会衰减的记忆、一份作息、主动行为、多个说话的地方），
但做成适合你这台机器的轻量版：不装 SnowLuma、不依赖 Electron，两个文件就能跑。

```
                 ┌──────────────────────────────┐
                 │  brain.mjs  「意识」服务 :4399 │
                 │  人格 / 记忆卡 / 作息 / 主动行为 │
                 └───────┬──────────────┬───────┘
          HTTP /chat     │              │      HTTP /chat
                 ┌───────▼──────┐  ┌────▼─────────────┐
                 │ pet.py 桌宠   │  │ dsh-qq-bot bridge │
                 │ 桌面上的她     │  │ QQ 里的她          │
                 └──────────────┘  └───────────────────┘
                          │                  │
                          └──── 同一个 dsh profile（qq）────┘
                                 人格：~/.dsh/persona/qq.md
```

**同一个她**：人格文件只有一份，记忆卡只有一份，作息只有一套。你在 QQ 里让她记住的事，桌面上她也记得。

## 启动

双击 `启动桌宠.cmd`：先检查 `4399` 端口的意识服务，没起就起一个，然后打开桌宠窗口。

想让它跟着 QQ 一起开机：QQ 那边用 **dsh-qq-bot** 仓库的 `启动（无窗口）.vbs`，桌宠用本仓库的 `启动（无窗口）.vbs`。

## 怎么玩

| 操作 | 效果 |
| --- | --- |
| 单机小人 | 打开对话窗（回车发送，ESC 关不掉，点右上角关闭） |
| 拖动 | 摆到任意位置，位置会记住 |
| 右键 | 说话 / 让她主动说一句 / 记住一件事 / 看记忆 / 换位置 / 隐藏 / 退出 |
| **Ctrl+Alt+P** | 隐藏 / 叫回来（全局热键，窗口藏起来也有效） |
| 什么都不做 | 每 25～55 分钟自己冒一句话（作息 8:00–24:00 内，且你 12 分钟没理她） |
| 双击 `编辑人格.cmd` | 改人格，下一条消息 + 下次主动说话都生效 |

主动说话是 SurfCore 那条「人格 × 记忆 × 新信息 → 目的 → 主动行为」的最小实现：
`brain.mjs` 到点挑一个时机，只用她的人设 + 最近说过的话生成一句，不重复。

## 记忆：分层冷热 + 线索召回

按 [Companion-AI-Memory 的规格](MEMORY.md) 落地了一版：

| 层 | 在哪 | 什么时候进提示词 |
| --- | --- | --- |
| 原文归档 | `state/memstore/archive.jsonl` | 永不直接进，只是证据 |
| detail | 最近 3 天的相关事件 | 相关才进（≤8 条 / 960 tokens） |
| summary | 3～7 天，或热度回落 | 同上，用短摘要 |
| cold | 7 天且 heat<0.3，或 14 天无提及 | 默认不进；只有用户给线索才找回（≤3 条 / 480） |
| pinned | 你说“记住这个” | 每轮都带（≤4 条 / 160） |

- 桌面和 QQ 私聊共用一份记忆（同一个 `owner` 作用域），群聊各自隔离；
- 内存快照每轮有硬上限 1600 tokens，日志里会打印 `记忆快照 28+0+0t`；
- 线索识别靠规则（记得/上次/那次/当年/去年 + 地点/物品/年份），线索不够时她会反问一句，不会扫全库；
- 相关度用**稀有词证据**（借自 dsh-fish-memory）：命中词的 idf 之和、不除以问句长度；问句全是常见词时这轮干脆不翻记忆；
- 注入行带日期（`（今天）`/`（3天前）`/`（去年 09-17）`），重要度越高半衰期越长（7～21 天）；
- 每天最多建 12 张记忆卡（手动固定不受限），防止鸡毛蒜皮都记；
- 同一会话里注入过的记忆不重复注入（`state/seen.json`，6 小时 TTL），pinned 与进行中事项豁免；
- 空闲时自动 **dream** 整理：合并近重复、压缩长细节，**不调用模型**，零成本；
- 详细设计与差距见 [MEMORY.md](MEMORY.md)，跑测试：`node _test/memory-test.mjs`（20 项）、`node _test/memory-v2-test.mjs`（13 项）、`node _test/memory-v3-test.mjs`（8 项）。

## 配置（`config.json`）

| 字段 | 说明 |
| --- | --- |
| `name` | 显示名，也是窗口标题 |
| `brainPort` | 意识服务端口，默认 4399 |
| `profile` | 用哪个 dsh profile，默认 `qq`（和 QQ 机器人同一个） |
| `activeHours` | 作息区间 `[8, 24]`，跨午夜写成 `[20, 3]` |
| `idleMinutesBeforeThink` | 你多久不理她才会主动开口 |
| `thinkEveryMinutes` | 主动说话的随机间隔区间 `[25, 55]` |
| `proactive` | 设 `false` 完全关掉主动行为 |
| `bubbleMs` | 气泡基础停留时长 |

## 换形象

| 形象 | 目录 | 尺寸 | 来源 / 脚本 |
| --- | --- | --- | --- |
| 博丽灵梦（Cylune 素材，**当前**） | `characters/reimu_cylune/` | 239×150 | 从 `themes/reimu/pet` 导入 |
| 帕秋莉（Cylune 素材） | `characters/patchouli/` | 491×300 | 从 `pet/` 导入 |
| 阿柒（猫娘） | `assets/` | 240×280 | 手绘，`make_sprites.py` |
| 博丽灵梦（精细版） | `characters/reimu/` | 320×380 | 按一设手绘，`make_sprites_reimu.py` |
| 博丽灵梦（封面 Q 版） | `characters/reimu2/` | 360×420 | 参考封面画风手绘，`make_sprites_reimu2.py` |

**Cylune 那两套**来自本机安装目录，原生是 1536×1024 的透明 PNG（四个表情：idle / happy / shy / sleepy）。
`import_cylune_pet.py` 做三件事：按 alpha 裁边 → 等比缩放到指定高度 → 以 `#FF00FE` 为底阈值抠图。
原图没有闭眼和说话帧，所以 `blink`、`talk` 复用 `idle`；`shy` 作为额外表情保留。

换角色 / 改尺寸（不用改代码）：

```powershell
python import_cylune_pet.py --char reimu     --height 150   # 灵梦，半尺寸
python import_cylune_pet.py --char patchouli --height 300   # 帕秋莉，原尺寸
python import_cylune_pet.py --char sakuya    --height 150   # 咲夜……
```

Cylune 里**带桌宠立绘**的主题只有这些（`Assets/Cylune/themes/<名字>/pet/`）：
`reimu`（灵梦）、`kokoro`（秦心）、`reisen`（铃仙）、`sanae`（早苗）、`satori`（觉）、`tenshi`（天子）、`yuyuko`（幽幽子）。
帕秋莉是默认主题，素材在 `Assets/Cylune/pet/` 而不是 themes 下。
其余角色（咲夜、魔理沙、琪露诺……）只有主题预览图，没有趴趴立绘，导不进来。

> ⚠️ 这些 PNG 是 Cylune 附带的素材，本机自用没问题，**不要随项目分发**；Cylune 本体是 AF Media Bar 的定制版（MIT），
> 但角色图是它自己的生成资产。

> ⚠️ 本仓库**只包含手绘素材**（ssets/、characters/reimu*）。源自 Cylune 的帕秋莉/灵梦立绘是第三方资产，没有随仓库分发；
> 你本机有的话可以用 import_cylune_pet.py 自己导入。

右键 → **换个形象** 即可切换，选择会写回 `config.json` 的 `character` 字段；不同形象尺寸可以不同，窗口会跟着变。
静态立绘会有轻微上下浮动（`bob_loop`）来模拟呼吸。

加新形象：在 `characters/` 下新建目录，放同名 PNG（`idle.png` 必须有，其余按需；任意尺寸，背景填 `#FF00FE`），
重启或右键切换就会出现在列表里。

Live2D 需要专有运行时（SurfCore 用的 SnowLuma），本版没接；真需要的话，用 Electron + pixi-live2d 单独做一个窗口，让它去调 `brain.mjs` 的 `/chat` 就行——两边接口是一样的。

## 接口（给以后扩展用）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 存活 + 名字 |
| POST | `/chat` | `{key, text, surface}` → `{reply}` |
| GET | `/memory` | 读长期记忆 |
| POST | `/memory` | `{fact}` 记一条 |
| POST | `/memory/clear` | 清空记忆（不可恢复） |
| POST | `/reset` | `{key}` 只清某条会话 |
| GET | `/proactive?since=N` | 拉主动消息（桌宠每 12 秒轮询） |
| POST | `/think` | 立刻让她主动想一句 |
| GET | `/status` | 作息、空闲时长、下次主动时间 |

## 已知限制

- 桌宠和 QQ 是**两条独立 session**，所以「刚才 QQ 里说的话」桌面上不会自动带过来——共享的是长期记忆，不是逐字上下文。这是故意的：省 token，也避免两边互相污染。
- 主动说话会各花一次模型调用，间隔别设太短（默认 25～55 分钟）。
- 窗口是置顶的透明窗，全屏游戏里可能挡住画面（右键可隐藏）。
- 依赖：Python 3.12（DSH 自带）、Pillow（仅生成素材时用）、Node 22+。
