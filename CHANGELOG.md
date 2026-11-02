# CHANGELOG

## v0.1.0 — 2026-11-01

第一次打包。三个零件都能单独跑，测试能过，样本能照着改。

### 新增

- **`hormone/endocrine.py`** —— 四个慢变量（多巴胺 / 催产素 / 皮质醇 / 内啡肽）的事件账。
  `observe_her` / `observe_me` 记账，`snapshot()` 出值，`mood()` / `render()` 出话，`shape()` / `beat()` 出形。
  关键词打分，不调模型。
- **`oath/oath.py`** —— 立约账。`add` / `done` / `settle` / `confess` / `rows`，四道数据库触发器把"删、改、反悔、抹坦白"堵死。
- **`memory/schema.sql`** —— 记忆库结构（messages / memories / memory_archive / mem_embedding），messages 带 FTS5 trigram 同步触发器。
- **`demo-app/`** —— 三接口的最小壳（`/`、`/say`、`/state`），激素驱动提示词的那一段能完整跑通。
- **`tests/test_protocol.py`** —— 18 条断言，只用标准库；验的就是这个仓库承诺过的事。
- **`docs/API.md`** —— 函数签名、返回结构、以及"数字别进提示词"这条总则。
- **`examples/pet_state.py`** —— 把"状态 → 动作"算成 JSON 的小样本，可以 `--serve` 起一个端点，给桌面宠物之类的客户端用。
- **`ARCHITECTURE.md` / `USAGE.md` / `NOTES.md`** —— 设计、边界与踩坑记录。

### 这一版**没有**的东西（写明白，省得猜）

- 没有 web 框架之外的依赖；没有数据库迁移工具；没有打包发布到 PyPI。
- `hormone` 不是情感计算：它不产生情绪，只给情绪一个出处。
- `oath` 不判断"什么算做到"：`done` 由调用方决定，裁决权别交给模型。
- `memory/schema.sql` 只是结构，**不含任何真实数据**；`memory/demo.py` 用的是假数据。

### 修正

- **中文关键词补回来了**（2026-11-01）。英文重写版把线上一直在用的中文词表整段丢了 —— 「我想你了」「抱抱我」在这个仓库里一条都不记。现在 `KW` 中英并存，`NEG` 也补了中文否定（不疼／没生气／不是骂你），并加 3 条测试钉住。

### 已知限制

- 关键词是**字面匹配**，没有分词也没有语义：同一句话换个说法就不认。要更准得自己换实现，`KW` 只是把它压到能维护的大小。
- FTS5 trigram 匹配不到 1–2 个字的查询（要用 `LIKE` 兜底）。
- `render()` 在没有事件时返回空字符串 —— 这是设计，不是 bug。
- `settle()` 需要外部定时器驱动（每小时一次就够）。

### 怎么验

```bash
python3 -m unittest discover -s tests -v     # 18 passed
```
