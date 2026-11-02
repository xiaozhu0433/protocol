#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""demo-app —— 把三块零件接成一条能跑的链。

一条消息进来：
    写原文 → 记激素 → 提炼一条记忆 → 拼上下文（激素的形 + 最近几条 + 召回到的旧事）→ 出回复

模型默认是**假的**（规则回话，不需要任何 API key）。
换真模型：设 MODEL=openai + MODEL_BASE / MODEL_KEY / MODEL_NAME。

跑：
    python3 app.py            # 默认 127.0.0.1:8000
    docker compose up         # 仓库根目录
"""
import json
import os
import sqlite3
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
sys.path.insert(0, os.path.join(ROOT, 'hormone'))

DATA = os.environ.get('DEMO_DATA') or os.path.join(BASE, 'data')
os.makedirs(DATA, exist_ok=True)
os.environ.setdefault('LUNA_DB', os.path.join(DATA, 'luna.db'))

MEM_DB = os.path.join(DATA, 'memory.db')
SCHEMA = os.path.join(ROOT, 'memory', 'schema.sql')

import endocrine as E  # noqa: E402

# ★ 引擎里的关键词表是**英文占位**——判据就是口味，要自己写。
#   这里给一套中文示例，演示怎么接：
E.KW.update({
    'close':   E.KW.get('close', ()) + ('想你', '抱', '亲', '贴', '喜欢你'),
    'distress': E.KW.get('distress', ()) + ('累', '难受', '疼', '哭', '害怕', '烦', '撑不住'),
    'praise':  E.KW.get('praise', ()) + ('厉害', '聪明', '好棒', '乖'),
    'attack':  E.KW.get('attack', ()) + ('笨', '讨厌', '滚', '烦死'),
    'care':    E.KW.get('care', ()) + ('你呢', '吃了吗', '睡了吗', '早点睡'),
    'laugh':   E.KW.get('laugh', ()) + ('哈哈', '笑死'),
    'desire':  E.KW.get('desire', ()) + ('要你', '过来', '别走'),
    'repair':  E.KW.get('repair', ()) + ('对不起', '抱歉', '我错了'),
})

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
except Exception:
    print('需要 fastapi + uvicorn：pip install fastapi uvicorn', file=sys.stderr)
    raise


def mem():
    c = sqlite3.connect(MEM_DB, timeout=15)
    c.execute('PRAGMA busy_timeout=15000')
    if not c.execute("select count(*) from sqlite_master where name='messages'").fetchone()[0]:
        c.executescript(open(SCHEMA, encoding='utf-8').read())
    return c


def write_msg(role, text, session='chat'):
    c = mem()
    c.execute('INSERT INTO messages (session_id, source_id, role, content, created_at) VALUES (?,?,?,?,?)',
              (session, session, role, text, time.strftime('%Y-%m-%d %H:%M:%S')))
    c.commit()
    c.close()


def write_memory(text, imp=4, tags='对话', layer='hot'):
    c = mem()
    c.execute('INSERT INTO memories (content, tags, importance, layer, machine, created_at, updated_at) '
              'VALUES (?,?,?,?,0,?,?)',
              (text, tags, imp, layer, time.strftime('%Y-%m-%d %H:%M:%S'), time.strftime('%Y-%m-%d %H:%M:%S')))
    c.commit()
    c.close()


def recall(q, limit=3):
    """按词切着搜：整句 LIKE 基本匹配不到。"""
    import re as _re
    toks = [t for t in _re.split(r'[^\w\u4e00-\u9fff]+', q or '') if len(t) >= 2][:3]
    if not toks:
        return []
    c = mem()
    out, seen = [], set()
    for t in toks:
        for row in c.execute("SELECT content, importance FROM memories WHERE content LIKE ? "
                             "AND layer <> 'legacy' AND coalesce(machine,0)=0 "
                             "ORDER BY importance DESC LIMIT ?", ('%' + t + '%', limit)):
            if row[0] not in seen:
                seen.add(row[0]); out.append(row)
    c.close()
    return out[:limit]


def recent(n=6):
    c = mem()
    rows = c.execute('SELECT role, content FROM messages ORDER BY id DESC LIMIT ?', (n,)).fetchall()
    c.close()
    return list(reversed(rows))


def call_model(user_text, ctx):
    """默认假模型：按激素状态换说法。设 MODEL=openai 才走真模型。"""
    if os.environ.get('MODEL') != 'openai':
        m = E.mood()
        line = {'close': '我在。你说。', 'tight': '嗯，听着。', 'active': '说，我手头停了。',
                'loose': '嗯……你说慢点。', 'flat': '在。'}.get(m.get('label'), '在。')
        return line
    base = os.environ.get('MODEL_BASE', 'https://api.openai.com/v1').rstrip('/')
    body = json.dumps({
        'model': os.environ.get('MODEL_NAME', 'gpt-4o-mini'),
        'messages': [{'role': 'system', 'content': ctx},
                     {'role': 'user', 'content': user_text}],
        'temperature': temperature(),
    }).encode()
    req = urllib.request.Request(base + '/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json',
                                          'Authorization': 'Bearer ' + os.environ.get('MODEL_KEY', '')})
    r = json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
    return (r.get('choices') or [{}])[0].get('message', {}).get('content', '').strip()


def temperature():
    """没有 form() 就用 mood 推一个：绷/贴的时候热一点，平的时候收一点。"""
    lab = E.mood().get('label')
    return {'tight': 0.85, 'close': 1.0, 'active': 0.95, 'loose': 0.8}.get(lab, 0.9)


def build_ctx(q):
    parts = [E.render() or '']
    olds = recall(q)
    if olds:
        parts.append('〔想起的旧事〕\n' + '\n'.join('- ' + t for t, _i in olds))
    return '\n\n'.join(p for p in parts if p)


app = FastAPI(title='protocol demo')


class Say(BaseModel):
    text: str


@app.get('/', response_class=HTMLResponse)
def index():
    return '''<!doctype html><meta charset="utf-8"><title>protocol demo</title>
<style>body{background:#0a0a0b;color:#ededef;font:16px/1.7 system-ui;max-width:640px;margin:0 auto;padding:28px}
.box{border:1px solid rgba(255,255,255,.12);border-radius:14px;padding:14px;margin:10px 0;white-space:pre-wrap}
.me{background:rgba(255,255,255,.05)}input{width:100%;padding:12px;border-radius:12px;border:1px solid rgba(255,255,255,.15);
background:#111;color:#eee}small{opacity:.5}</style>
<h3>protocol demo</h3><small>假模型：只按激素状态回一句。换真模型见 README。</small>
<div id="log"></div><input id="t" placeholder="说点什么，回车" autofocus>
<script>
const log=document.getElementById('log');
document.getElementById('t').addEventListener('keydown',async e=>{
  if(e.key!=='Enter'||!e.target.value.trim())return;
  const text=e.target.value;e.target.value='';
  const a=document.createElement('div');a.className='box';a.textContent='我：'+text;log.appendChild(a);
  const r=await fetch('/say',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})}).then(x=>x.json());
  const b=document.createElement('div');b.className='box me';
  b.textContent='它：'+(r.reply||'')+'\\n\\n〔状态〕'+(r.state||'');log.appendChild(b);
});
</script>'''


@app.post('/say')
def say(body: Say):
    text = (body.text or '').strip()
    if not text:
        return JSONResponse({'ok': False, 'err': 'empty'})
    write_msg('user', text)
    E.observe_her(text)
    write_memory(text, imp=4)

    ctx = build_ctx(text)
    reply = call_model(text, ctx)

    write_msg('assistant', reply)
    E.observe_me(reply)
    write_memory('你说：%s ｜ 我回：%s' % (text, reply), imp=6, tags='对话,往来')
    m = E.mood()
    r = m.get('raw') or {}
    # 把四个原始值也带上：阈值没被跨过时，光看 label 会以为“什么都没发生”
    return {'ok': True, 'reply': reply,
            'state': '%s（%s/%s）· 多巴胺 %s｜催产素 %s｜皮质醇 %s｜内啡肽 %s' % (
                m.get('label'), m.get('tense'), m.get('pace'),
                r.get('da'), r.get('ot'), r.get('cort'), r.get('end'))}


@app.get('/state')
def state():
    m = E.mood()
    return {'ok': True, 'mood': m, 'temperature': temperature()}


if __name__ == '__main__':
    uvicorn.run(app, host=os.environ.get('HOST', '127.0.0.1'),
                port=int(os.environ.get('PORT', '8000')))