#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""memory demo —— 只演示结构，不含任何真实数据。

    python3 demo.py

它会：建一个 demo.db（从 schema.sql）、灌一批构造的对话和记忆、
然后演示两件事：
  1) 上下文里会放什么（core 钉子 + 最近的 hot 记忆）
  2) 关键词召回会怎么筛（跳过机器稿、跳过低重要度、按重要度排）

三分钟能看完，不用起服务。
"""
import os
import sqlite3
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'demo.db')


def build():
    if os.path.exists(DB):
        os.remove(DB)
    c = sqlite3.connect(DB)
    c.executescript(open(os.path.join(HERE, 'schema.sql'), encoding='utf-8').read())
    now = time.time()

    for sid, name in (('chat', '小屋'), ('call', '电话'), ('story', '剧情')):
        c.execute('INSERT OR IGNORE INTO sources (id, name, platform) VALUES (?,?,?)', (sid, name, sid))

    msgs = [
        ('chat', 'user', '今天有点累，不想说话', 0.0),
        ('chat', 'assistant', '那就别说了，靠过来。', 0.2),
        ('chat', 'user', '你记得我上次说的那个项目吗', 1.0),
        ('chat', 'assistant', '记得，卡在库存那一块。', 1.1),
        ('call', 'user', '喂，听得见吗', 2.0),
        ('call', 'assistant', '听得见，你说。', 2.2),
        ('story', 'user', '他推门进来，没有回头。', 3.0),
        ('story', 'assistant', '门在他身后合上，风把那句话带走了。', 3.1),
    ]
    for sess, role, text, dt in msgs:
        c.execute('INSERT INTO messages (session_id, source_id, role, content, created_at) VALUES (?,?,?,?,?)',
                  (sess, sess, role, text, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now - 86400 + dt))))

    mems = [
        # (层, 重要度, 标签, 内容, 是否机器稿)
        ('core', 9, '关系,钉子', '她说过：不要替她做决定，要问她。', 0),
        ('core', 8, '关系,钉子', '她怕被支到明天。', 0),
        ('hot', 7, '关系', '她说最近项目卡在库存盘点，压力大。', 0),
        ('hot', 6, '关系', '她今天累了，不想说话，只要人靠着。', 0),
        ('warm', 5, '对话', '她提过想学做面包。', 0),
        ('cold', 3, '对话', '她问过南方梅雨季怎么除湿。', 0),
        ('hot', 9, '机器', '【自动锚点】Background subagent finished and will do no further work', 1),
        ('warm', 2, 'legacy', '（一条降级的历史旧话，不参与召回）', 0),
    ]
    for layer, imp, tags, text, machine in mems:
        c.execute('INSERT INTO memories (content, tags, importance, layer, machine, created_at, updated_at) '
                  'VALUES (?,?,?,?,?,?,?)',
                  (text, tags, imp, layer, machine,
                   time.strftime('%Y-%m-%d %H:%M:%S'), time.strftime('%Y-%m-%d %H:%M:%S')))
    c.commit()
    return c


def context(c, hot_n=4, min_imp=6):
    """假装拼一次上下文：钉子 + 最近的热记忆。"""
    core = c.execute("SELECT content FROM memories WHERE layer='core' AND importance>=? "
                     "ORDER BY importance DESC LIMIT 8", (min_imp,)).fetchall()
    hot = c.execute("SELECT content FROM memories WHERE layer='hot' AND importance>=? "
                    "AND coalesce(machine,0)=0 ORDER BY updated_at DESC LIMIT ?", (min_imp, hot_n)).fetchall()
    return [r[0] for r in core], [r[0] for r in hot]


def recall(c, kw, limit=5, min_imp=3):
    """关键词召回：跳机器稿、跳 legacy、跳低重要度。

    这里用 LIKE 而不是 FTS —— 中文 FTS 需要分词器，生产里用的是「整段 FTS + 分词表」两套；
    demo 只要演示**筛什么**，不演示分词。
    """
    rows = c.execute(
        "SELECT id, content, importance, layer FROM memories "
        "WHERE content LIKE ? AND importance >= ? AND layer <> 'legacy' "
        "AND coalesce(machine,0)=0 ORDER BY importance DESC LIMIT ?",
        ('%' + kw + '%', min_imp, limit)).fetchall()
    return rows


def main():
    c = build()
    core, hot = context(c)
    print('== 每次会进上下文的（钉子） ==')
    for t in core:
        print('  ·', t)
    print('\n== 热记忆（最近 %d 条） ==' % len(hot))
    for t in hot:
        print('  ·', t)
    print('\n== 关键词召回：「项目」 ==')
    for r in recall(c, '项目'):
        print('  #%d  %s   （重要度 %s · %s）' % (r[0], r[1], r[2], r[3]))
    print('\n== 关键词召回：「subagent」（机器稿被挡在外面） ==')
    rs = c.execute("SELECT count(*) FROM memories WHERE content LIKE '%subagent%'").fetchone()[0]
    print('  库里其实有 %d 条机器稿；召回返回 %d 条' % (rs, len(recall(c, 'subagent'))))
    print('\n== 层分布 ==')
    for layer, n in c.execute('SELECT layer, count(*) FROM memories GROUP BY layer ORDER BY 2 DESC'):
        print('  %-8s %d' % (layer, n))
    c.close()
    print('\ndemo.db 留在当前目录，删掉它就是清理干净。')


if __name__ == '__main__':
    main()