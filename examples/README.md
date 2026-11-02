# examples

能直接跑、不用装东西的小样本。每个文件顶上写了它解决的那件具体事。

| 文件 | 跑法 | 做什么 |
|---|---|---|
| `pet_state.py` | `python3 pet_state.py` | 把四个慢变量折成一个**能演的动作名**（crouch / lean / hop / doze / idle） |
| | `python3 pet_state.py --serve 8765` | 起一个 `GET /state` 端点，给桌面宠物、小组件之类的客户端拉 |

```bash
cd examples
LUNA_DB=/tmp/luna.db python3 pet_state.py          # 空账 → idle（发呆）
```

空账输出：

```json
{"ok": 1, "act": "idle", "word": "发呆", "da": 44.0, "ot": 34.0, "cort": 26.0, "end": 20.0, "mood": "flat"}
```

中文也能记：

```python
E.observe_her('我想你了')      # → close：催产素抬起来
E.observe_her('你累不累')      # → care：关心（不是诉苦）
E.observe_her('我不疼，也没生气')  # → 不记（NEG 挡住）
```

往里记点东西，它就会变：

```python
import sys; sys.path.insert(0, '../hormone')
import endocrine as E
for i in range(10):
    E.observe_her('i miss you', uniq_prefix='t%d' % i)   # 十次"想你" → 催产素过 50 → lean
```

```json
{"ok": 1, "act": "lean", "word": "想贴你", "ot": 51.2, ...}
```

## 两个要注意的

1. **关键词表 `KW` 中英并存**（`miss` / `hug` 和「想你」「抱抱」都在）。中文是 2026-11-01 补回来的 —— 之前英文重写版把线上一直在用的中文整段丢了，「我想你了」一条都不记。否定词（不疼／没生气）也在 `NEG` 里，别让关心听成诉苦。
2. **别把这个 JSON 塞进提示词。** 它是给客户端看的；给模型看的是 `endocrine.render()`。数字一旦进提示词，模型就会照着数演。

阈值在文件开头的表里，是商量出来的，不是算出来的 —— 按自己的习惯改。
