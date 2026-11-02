# memory —— 一个给长期对话用的记忆层

不是向量数据库的封装，是一套**取舍**：什么进记忆、什么留在原文、什么永远不召回。

## 三层

| 层 | 是什么 | 谁读 |
|---|---|---|
| `messages` | **原文**，带 `channel` 区分来源 | 拼上下文时取最近几十条 |
| `memories` | **提炼**，带 tags / importance / layer | 召回只查这一张 |
| `memory_archive` | 被清出去的东西（含原文备份） | 没人读，只作审计 |

这样分的好处：召回永远不会把三天前一句闲聊原样倒出来，也不会把剧情台词当成"她说过的话"。

## 来源（channel）必须先分开

同一句话，从聊天窗口说出来、从电话里说出来、从剧情游戏里说出来，语义完全不同。

```
chat    日常对话       → 全量进上下文
call    语音通话       → 落库，不进日常
wechat  手机消息       → 只带她那半句
story   文字剧情       → 只留原文，不进记忆
dev     开发记录       → 只报条数，正文不进来
```

混在一起的后果很具体：把开发窗口的原话塞进聊天上下文，说话口气会串。

## 召回的筛选顺序（demo.py 里能看见）

1. **丢机器稿**：`Background subagent…` / `Current runtime context…` / `<system-reminder>` 这类管道文本，不是记忆。
2. **丢低重要度**：`importance` 有门槛，不是所有记忆都配进上下文。
3. **丢 legacy**：降级的历史旧话（`layer='legacy'`）只留档，不参与召回。
4. **按重要度排**，不是按时间——时间是上下文那条线的事。

## 表结构

`schema.sql`，29 个对象。核心四张：

```sql
messages   (id, session_id, source_id, role, content, model, created_at, dedupe_key, bone)
memories   (id, content, tags, importance, layer, machine, created_at, updated_at, ...)
memory_archive (memory_id, action, why, score, at, note)
mem_embedding  (memory_id, model, dim, vec, norm)
```

`dedupe_key` 是入库时算的，同一句话说两遍只留一条。
`machine=1` 用来标机器稿——**这个字段是事后加的**，因为一开始没分，导致一批管道文本进了 hot 层。

## 这里有什么 / 没有什么

**有**：`schema.sql`（结构）、`demo.py`（构造数据 + 演示筛选）。

**没有**：服务代码（`server.js`，还在脱敏——它现在有两处扎在原作者自己的其它组件上：
一个分流分类器、一个向量服务），也没有任何真实数据。

## 一条经验

**记忆的敌人不是"记不住"，是"记串了"。**
把不同来源混进一个池子，比忘记更糟：忘记是缺，记串是错，而且错得听起来很合理。

MIT.

> 提炼规则（什么留下、什么丢弃、怎么去重合并、导入历史怎么处理）见 [docs/MEMORY-EXTRACTION.md](../docs/MEMORY-EXTRACTION.md)。
