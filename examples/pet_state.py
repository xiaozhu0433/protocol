#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「状态 → 动作」算出来，给桌面宠物这类客户端用。

为什么有它：模型的状态（四个慢变量）本身看不见，只写成一段话又只能读。
把它折成几个**能演的动作**，屏幕上的东西就能替你显示"我现在是什么样"。

    python3 pet_state.py                 # 打一次 JSON
    python3 pet_state.py --serve 8765    # 起个端点，GET /state

只用标准库；读的是 hormone/ 的库（`LUNA_DB`）。

动作表（用绝对值，不搞归一化 —— 好懂、好改）：

    cort >= 40          crouch   缩起来
    ot   >= 50          lean     往你那边靠
    da   >= 55          hop      蹦
    end  <= 12          doze     垂下去
    其余                 idle     发呆 / 只呼吸

基线是 da 44 / ot 34 / cort 26 / end 20（没有账的时候就是这四个数），
所以空账时给的是 idle —— 这一点有测试盯着。

⚠️ 关键词表 `KW` 目前只有英文（miss / hug / love you …）。
   中文要自己往里加，否则"我想你了"这类话不会记进账里。

命令行只输出数字和动作名 —— **不要把这段塞进提示词**，它是给客户端看的。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'hormone'))

import endocrine as E  # noqa: E402

WORDS = {
    'crouch': '紧',
    'lean': '想贴你',
    'hop': '想要',
    'doze': '困',
    'idle': '发呆',
}


def state():
    v = E.snapshot()
    m = E.mood() or {}
    da = float(v.get('da') or 0)
    ot = float(v.get('ot') or 0)
    cort = float(v.get('cort') or 0)
    end = float(v.get('end') or 0)

    if cort >= 40:
        act = 'crouch'
    elif ot >= 50:
        act = 'lean'
    elif da >= 55:
        act = 'hop'
    elif end <= 12:
        act = 'doze'
    else:
        act = 'idle'

    return {
        'ok': 1,
        'act': act,
        'word': WORDS[act],
        'da': round(da, 1),
        'ot': round(ot, 1),
        'cort': round(cort, 1),
        'end': round(end, 1),
        'mood': m.get('label'),
    }


def serve(port):
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(state(), ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    print('listening on 127.0.0.1:%d/state' % port)
    HTTPServer(('127.0.0.1', port), H).serve_forever()


if __name__ == '__main__':
    if '--serve' in sys.argv:
        i = sys.argv.index('--serve')
        serve(int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else 8765)
    else:
        print(json.dumps(state(), ensure_ascii=False, indent=1))
