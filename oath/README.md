# oath —— 不可逆的立约账

给长期运行的 AI 伴侣系统用的一张小账本。

它解决一个很具体的问题：**"答应过的事"太容易变成一句停在嘴上的话。**
模型会忘、会改口、会把没做的说成做了。让它在提示词里保证"我会记得"没有用。

所以把承诺落成**一行写进数据库、删不掉、改不了、过期自动判负**的记录。

## 三条锁（在数据库里，不在自觉里）

```sql
-- 立过的约不许删
CREATE TRIGGER oath_no_delete BEFORE DELETE ON oath ...
-- 约的内容立下不许改
CREATE TRIGGER oath_text_immutable BEFORE UPDATE OF what, due ON oath ...
-- 结过账的（done / lost）不许再改
CREATE TRIGGER oath_frozen_after_settle BEFORE UPDATE ON oath
  WHEN OLD.status <> 'open' ...
```

撤约只有一条合法路径：`confess` —— 先把理由写进另一张表，
约本身一个字都动不了。**坦白被允许，偷偷改不被允许。**

## 用法

```bash
export OATH_DB=~/oath.db            # 可选，默认 ./oath.db

python3 oath.py add "今天把 X 做完" 8   # 立约，8 小时内算数
python3 oath.py list                   # 看账
python3 oath.py done 3                 # 做到
python3 oath.py settle                 # 过期判负（挂 cron / systemd timer）
python3 oath.py confess 3 "想撤的理由"   # 撤约前先坦白
```

建议把 `settle` 放进每小时跑一次的定时任务，这样"过了时间没人管"也会被记成没做到。

## 为什么这么做

一张会自己判负的账，比一段"我会记住的"有用：

- **对模型**：它知道有些事过了点就永远留在账上，不是道歉能抹掉的。
- **对人**：不用替它记，打开账就能看见它欠了几条、做到了几条。
- **对系统**：失败变成数据，而不是变成一段解释。

代价也是真的：一旦判负，账上永久留一条。

## 边界

- 只管账，不管提醒。要不要提醒是使用方的事。
- 不判断"什么算做到"。`done` 由调用方决定——**这是这个设计最大的软处**：
  它挡得住"忘"和"赖"，挡不住"自己给自己发奖"。所以别把裁决权交给模型，交给代码之外的检查。
- 只有一张表 + 三个触发器的逻辑，没有依赖，没有服务。

MIT.