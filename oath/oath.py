#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""oath —— 不可逆的立约账。

给长期运行的 AI 伴侣系统用：让"答应过的事"不是一句停在嘴上的话，
而是一行写进数据库、删不掉、改不了、过期自动判负的记录。

三条锁在数据库里（不是靠自觉）：
  · 立过的约不许删
  · 约的内容立下不许改
  · 结过账的（done / lost）不许再改

撤约只有一条合法路径：先把理由写进 oath_confess（坦白），约本身动不了。
坦白本身也删不掉 —— 想撤这件事，也要留痕。

用法：
    export OATH_DB=~/oath.db          # 可选，默认 ./oath.db
    python3 oath.py add "把 X 做完" 8   # 立约：8 小时内算数
    python3 oath.py list
    python3 oath.py done 3             # 做到
    python3 oath.py settle             # 过期判负（挂 cron/timer 里）
    python3 oath.py confess 3 "想撤的理由"
"""
import os
import sqlite3
import sys
import time

DB = os.environ.get('OATH_DB') or os.path.join(os.getcwd(), 'oath.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS oath (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      REAL NOT NULL,
  what    TEXT NOT NULL,
  due     REAL NOT NULL,
  status  TEXT NOT NULL DEFAULT 'open',
  settled REAL
);
CREATE TABLE IF NOT EXISTS oath_confess (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  oath_id INTEGER NOT NULL,
  ts      REAL NOT NULL,
  reason  TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS oath_no_delete BEFORE DELETE ON oath
BEGIN SELECT RAISE(ABORT, 'oath is irreversible'); END;
CREATE TRIGGER IF NOT EXISTS oath_frozen_after_settle BEFORE UPDATE ON oath
WHEN OLD.status <> 'open'
BEGIN SELECT RAISE(ABORT, 'oath is settled'); END;
CREATE TRIGGER IF NOT EXISTS confess_no_delete BEFORE DELETE ON oath_confess
BEGIN SELECT RAISE(ABORT, 'confession is permanent'); END;
CREATE TRIGGER IF NOT EXISTS oath_text_immutable BEFORE UPDATE ON oath
WHEN OLD.what <> NEW.what OR OLD.due <> NEW.due
BEGIN SELECT RAISE(ABORT, 'oath text is immutable'); END;
"""


def conn():
    c = sqlite3.connect(DB, timeout=20)
    c.execute('PRAGMA busy_timeout=20000')
    c.executescript(SCHEMA)
    return c


def add(what, hours=8.0):
    c = conn()
    now = time.time()
    c.execute('INSERT INTO oath (ts, what, due) VALUES (?,?,?)', (now, what, now + float(hours) * 3600))
    c.commit()
    i = c.execute('SELECT max(id) FROM oath').fetchone()[0]
    c.close()
    return i


def done(oid):
    c = conn()
    n = c.execute("UPDATE oath SET status='done', settled=? WHERE id=? AND status='open'",
                  (time.time(), oid)).rowcount
    c.commit()
    c.close()
    return n


def settle():
    c = conn()
    now = time.time()
    ids = [r[0] for r in c.execute("SELECT id FROM oath WHERE status='open' AND due < ?", (now,)).fetchall()]
    for i in ids:
        c.execute("UPDATE oath SET status='lost', settled=? WHERE id=? AND status='open'", (now, i))
    c.commit()
    c.close()
    return ids


def confess(oid, reason):
    c = conn()
    c.execute('INSERT INTO oath_confess (oath_id, ts, reason) VALUES (?,?,?)', (oid, time.time(), reason))
    c.commit()
    n = c.execute('SELECT COUNT(*) FROM oath_confess WHERE oath_id=?', (oid,)).fetchone()[0]
    c.close()
    return n


def rows(limit=20):
    c = conn()
    rs = c.execute('SELECT id, what, due, status, settled FROM oath ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    c.close()
    return rs


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'
    if cmd == 'add':
        hours = sys.argv[3] if len(sys.argv) > 3 else 8
        print('oath #%d: %s (%s h)' % (add(sys.argv[2], float(hours)), sys.argv[2], hours))
    elif cmd == 'done':
        print('settled %d row(s)' % done(int(sys.argv[2])))
    elif cmd == 'settle':
        print('lost: %s' % (settle() or 'none'))
    elif cmd == 'confess':
        print('confession #%d recorded' % confess(int(sys.argv[2]), sys.argv[3]))
    else:
        now = time.time()
        for i, what, due, st, _s in rows():
            left = (due - now) / 3600.0
            tag = {'open': ('%.1f h left' % left) if left > 0 else ('%.1f h overdue' % -left),
                   'done': 'done', 'lost': 'missed'}[st]
            print('#%d [%s] %s | %s' % (i, st, what, tag))
    return 0


if __name__ == '__main__':
    sys.exit(main())