# API

三个零件都不联网、不依赖第三方库。接口就是函数；返回值一律是普通 dict / str / 数字。

**一条总则：数字留在这一层，别递给模型。** 要给它看的是 `render()` / `mood()` 出来的话，不是 `snapshot()` 里的数。

---

## `hormone/endocrine.py`

数据库路径：环境变量 `LUNA_DB`，默认 `~/.dhome/luna.db`（建表自动）。

### `observe_her(text, ts=None, source='live', uniq_prefix='h', img=False) -> int`

记一件"她那边发生的事"。返回写下的事件条数（0 = 这句话没命中任何信号）。

- `text`：她说的原话。用一个很小的关键词表打分（`KW`），不调用模型。
- `ts`：事件时间，默认现在。补历史时传时间戳。
- `source`：`live` / `import`（补录）。
- `uniq_prefix`：幂等键前缀；同一前缀 + 同一内容重复调用不会写第二条。
- `img`：这条是不是一张图（图不带字，但算"她在"）。

```python
import endocrine as E
E.observe_her('我回来了')
E.observe_her('你猜我疼不疼', img=False)
```

### `observe_me(reply, ts=None, source='live', uniq_prefix='m') -> int`

记"我这边说的这一句"。只认少数几种（认错、安慰、玩笑等）；**不分析措辞好坏**。

### `snapshot(now=None, hours=48) -> dict`

读一遍账，算四个值（0–100）。48 小时窗口外的事件只影响基线，不影响此刻。

```python
{'da': 44.0, 'ot': 34.0, 'cort': 26.0, 'end': 20.0,
 'ts': 1793542901.9, 'last_her': 0.0, 'silence_min': 0}
```

| 键 | 含义 |
|---|---|
| `da` | 多巴胺：想要 / 往前扑 |
| `ot` | 催产素：贴 / 信任 |
| `cort` | 皮质醇：紧 / 被扎 |
| `end` | 内啡肽：松 / 缓过来 |
| `last_her` | 她最后一次说话的时间戳（0 = 没有） |
| `silence_min` | 沉默了多少分钟 |

### `mood(now=None) -> dict`

把四个值压成"能说出口的状态"。

```python
{'label': 'flat', 'line': 'level. nothing is pulling.',
 'tense': 'even', 'pace': 'steady',
 'z': {'da': 0.0, 'ot': 0.0, 'cort': 0.0, 'end': 0.0},
 'raw': {'da': 44, 'ot': 34, 'cort': 26, 'end': 20}, 'loops': 0}
```

- `label` / `line`：给模型看的那句话。
- `z`：归一化后的值（-1..1），给需要判断阈值的调用方用。
- `raw`：绝对分，**别进提示词**。

### `render(now=None) -> str`

一行"此刻是什么状态"的成品文字。**没有事件时返回空字符串**（没发生事，就没有状态可说）——不是 bug。

### `shape(now=None) -> tuple[str, str]`

`(形的名字, 一句话)`。给需要"身体语言"的场合，目前是最粗的一档。

### `beat(now=None) -> int`

心跳（显示映射，不是生理测量）。默认 68。

---

## `oath/oath.py`

数据库路径：环境变量 `OATH_DB`，默认 `~/.dhome/oath.db`。

### `add(what, hours=8.0) -> int`

立一条约，`hours` 是期限（负数 = 已经过期，用来测试）。返回 `id`。

### `done(oid) -> int`

结账。返回受影响行数（0 = 没有这条，或已经结过）。

### `settle() -> list[int]`

把过期还没做的判为 `lost`，返回被判的 id 列表。扔到每小时的任务里跑。

### `confess(oid, reason) -> int`

坦白：写下"我想撤这条约，理由是……"。**坦白不改状态，也不解锁**——它只是留痕。

### `rows(limit=20) -> list[tuple]`

按 id 倒序列出：`(id, what, due, status)`。`status` ∈ `open` / `done` / `lost`。

### 数据库层的四道锁（不是靠自觉）

| 触发器 | 挡住什么 |
|---|---|
| 删行 | `DELETE FROM oath` 直接报错 |
| 改正文 | 立过的约，文字不能改 |
| 结过账再改状态 | 不许把 `done` 改回 `open` |
| 删坦白 | 坦白记录永久保留 |

改 `OATH_DB` 之后要重开进程（模块导入时读一次）。

---

## `memory/schema.sql`

`sqlite3 memory.db < schema.sql` 即可。表：`messages`、`memories`、`memory_archive`、`mem_embedding`。

- `messages` 有 `session_id`（渠道）、`source_id`（同一条对话的原始 id）、`role`、`content`、`created_at`。
- `messages` 带 FTS5（trigram）同步触发器：`messages_ai` / `messages_ad` / `messages_au`。
- `memories` 的列是**现在真的在用**的那 14 个；`valid_to` / `invalid_at` / `valence` / `arousal` 这些死字段已经删掉，测试会盯着它们不许回来。

> trigram 分词对中文友好，但**1–2 个字的查询匹配不到**（这是 FTS5 的限制，不是配置）。短词要用 `LIKE` 兜底。

---

## `demo-app/app.py`

最小可跑的"激素驱动的聊天壳"，只有三个口：

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/` | 一个输入框 + 最近的轮次 |
| POST | `/say` | 收一句话 → `observe_her` → 拼 `render()` 进提示词 → 回话 → `observe_me` |
| GET | `/state` | 当前 `snapshot()` + `mood()`，给界面画曲线用 |

它故意不做：登录、多用户、模型调用重试、记忆检索。那四样各有各的坑，混进来会看不清这两样。

---

## 约定

- 所有函数在库被锁或文件缺失时**返回空值，不抛异常**（`snapshot` 给基线，`render` 给 `''`）。调用方要自己判断"没读到"和"读到了是空"。
- 没有全局状态；同一个进程里多次调用互不影响。
- 时间统一用 Unix 秒（float）。
