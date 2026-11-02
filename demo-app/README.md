# demo-app —— 把三块零件接成一条能跑的链

一条消息进来经过五步：

```
写原文 → 记激素 → 提炼一条记忆 → 拼上下文（激素的形 + 最近几条 + 召回到的旧事）→ 出回复
```

**默认用假模型**（规则回话，不需要任何 API key），换真模型只改一个环境变量。

## 跑起来

```bash
# 方式一：本地
pip install fastapi uvicorn
python3 app.py                 # → http://127.0.0.1:8000

# 方式二：docker
cd .. && docker compose up     # → http://127.0.0.1:8000
```

打开页面，随便说两句。每说一句，库里会多一条原文 + 一到两条记忆；
再说一句跟前面有关的话，它会从记忆里把旧事捞出来（看响应里的 `state`）。

## 换真模型

```bash
MODEL=openai \
MODEL_BASE=https://api.openai.com/v1 \
MODEL_KEY=sk-xxx \
MODEL_NAME=gpt-4o-mini \
python3 app.py
```

任何 OpenAI 兼容的接口都行（自建 vLLM、one-api 之类改 `MODEL_BASE` 就可以）。

## 它做了什么、没做什么

**做了：**
- 每条消息都过一遍激素引擎（`hormone/endocrine.py`），状态会随说话变
- 原文与提炼分开写（`messages` / `memories` 两张表）
- 拼上下文时把激素的「形」和召回到的旧事一起给模型
- 中文关键词表是**示例**，写在 `app.py` 开头 —— 引擎里那份是英文占位

**没做（这是 demo，不是产品）：**
- 没有登录、没有多用户、没有并发控制
- 召回只做关键词匹配，没有向量（真实的记忆层有，见 `memory/`）
- 记忆不做去重、不做分层老化（真实系统靠 `importance` 和 `layer`）
- 假模型的回话只按激素状态选一句，跟内容无关

## 一句话

这个 demo 只想证明一件事：**激素和记忆不是两套装饰，它们真能改变一句话是怎么被拼出来的。**