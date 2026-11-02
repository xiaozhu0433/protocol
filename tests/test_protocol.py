#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""protocol 的自检：激素引擎 + 立约账 + 记忆表结构。

    python3 -m unittest discover -s tests -v

只用标准库，不需要装任何东西。跑完它会自己清掉临时库。
"""
import importlib.util
import os
import sqlite3
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class HormoneTest(unittest.TestCase):
    """激素账：记了才有反应，不记就不动，久了会退回去。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, 'luna.db')
        os.environ['LUNA_DB'] = self.db
        self.E = _load('endocrine_t', os.path.join(ROOT, 'hormone', 'endocrine.py'))

    def tearDown(self):
        for suffix in ('', '-wal', '-shm'):
            p = self.db + suffix
            if os.path.exists(p):
                os.remove(p)

    def test_defaults_are_in_range(self):
        snap = self.E.snapshot()
        for k in ('da', 'ot', 'cort', 'end'):
            self.assertIn(k, snap)
            self.assertGreaterEqual(snap[k], 0)
            self.assertLessEqual(snap[k], 100)

    def test_nothing_recorded_nothing_moves(self):
        before = self.E.snapshot()
        after = self.E.snapshot(now=time.time() + 60)
        self.assertAlmostEqual(before['ot'], after['ot'], delta=1.0)

    def test_close_message_raises_oxytocin(self):
        ts = time.time()
        before = self.E.snapshot(now=ts)
        wrote = self.E.observe_her('I miss you, come here', ts=ts)
        self.assertTrue(wrote, '这句话应该记下至少一个事件')
        after = self.E.snapshot(now=ts + 60)
        self.assertGreater(after['ot'], before['ot'], '亲密话应该把催产素抬起来')

    def test_insult_raises_cortisol(self):
        ts = time.time()
        before = self.E.snapshot(now=ts)
        self.E.observe_her('you are useless, get lost', ts=ts)
        after = self.E.snapshot(now=ts + 60)
        self.assertGreater(after['cort'], before['cort'])

    def test_values_decay_over_a_day(self):
        ts = time.time()
        self.E.observe_her('I miss you', ts=ts)
        right_after = self.E.snapshot(now=ts + 60)
        next_day = self.E.snapshot(now=ts + 24 * 3600)
        self.assertLess(abs(next_day['ot'] - 34.0), abs(right_after['ot'] - 34.0),
                        '一天之后应该往基线退回去，而不是留在高点')

    def test_mood_has_shape(self):
        m = self.E.mood()
        for k in ('label', 'line', 'tense', 'pace', 'raw'):
            self.assertIn(k, m)
        self.assertIsInstance(m['label'], str)

    def test_render_after_a_message(self):
        # 空库时 render() 返回空字符串（没发生事，就没有状态可说）——这是设计。
        # 发生过一件事之后，它必须给出一段能进提示词的话。
        self.E.observe_her('I miss you', ts=time.time())
        t = self.E.render()
        self.assertIsInstance(t, str)
        self.assertTrue(t.strip(), '有过事件之后 render 不该是空的')


class OathTest(unittest.TestCase):
    """立约账：能立、能结；删不掉、改不了、坦白也删不掉。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, 'oath.db')
        os.environ['OATH_DB'] = self.db
        self.O = _load('oath_t', os.path.join(ROOT, 'oath', 'oath.py'))

    def tearDown(self):
        if os.path.exists(self.db):
            os.remove(self.db)

    def _sql(self, sql, args=()):
        c = sqlite3.connect(self.db, timeout=10)
        try:
            c.execute(sql, args)
            c.commit()
        finally:
            c.close()

    def test_add_then_list(self):
        i = self.O.add('把这件事做完', 2)
        rows = self.O.rows()
        self.assertEqual(rows[0][0], i)
        self.assertEqual(rows[0][3], 'open')

    def test_done_settles(self):
        i = self.O.add('做完它', 2)
        self.assertEqual(self.O.done(i), 1)
        self.assertEqual(self.O.rows()[0][3], 'done')

    def test_delete_is_refused(self):
        self.O.add('不许删', 2)
        with self.assertRaises(sqlite3.DatabaseError):
            self._sql('DELETE FROM oath WHERE id=1')

    def test_text_is_immutable(self):
        self.O.add('原文', 2)
        with self.assertRaises(sqlite3.DatabaseError):
            self._sql("UPDATE oath SET what='改掉' WHERE id=1")

    def test_settled_cannot_be_reopened(self):
        i = self.O.add('结过账的', 2)
        self.O.done(i)
        with self.assertRaises(sqlite3.DatabaseError):
            self._sql("UPDATE oath SET status='open' WHERE id=1")

    def test_confession_is_permanent(self):
        i = self.O.add('想撤', 2)
        self.assertEqual(self.O.confess(i, '理由'), 1)
        with self.assertRaises(sqlite3.DatabaseError):
            self._sql('DELETE FROM oath_confess WHERE oath_id=1')

    def test_overdue_becomes_lost(self):
        i = self.O.add('过期没做', -1)   # due 在过去
        lost = self.O.settle()
        self.assertIn(i, lost)
        self.assertEqual(self.O.rows()[0][3], 'lost')


class MemorySchemaTest(unittest.TestCase):
    """记忆库结构：建得起来、能写、全文索引的触发器在。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, 'memory.db')
        with open(os.path.join(ROOT, 'memory', 'schema.sql'), encoding='utf-8') as f:
            sql = f.read()
        c = sqlite3.connect(self.db)
        c.executescript(sql)
        c.close()

    def tearDown(self):
        if os.path.exists(self.db):
            os.remove(self.db)

    def test_tables_exist(self):
        c = sqlite3.connect(self.db)
        names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        c.close()
        for t in ('messages', 'memories', 'memory_archive', 'mem_embedding'):
            self.assertIn(t, names)

    def test_write_and_read(self):
        c = sqlite3.connect(self.db)
        c.execute("INSERT INTO messages (session_id, source_id, role, content, created_at) "
                  "VALUES ('chat','chat','user','你好','2026-11-01 19:00')")
        c.execute("INSERT INTO memories (content, tags, importance, layer, created_at, updated_at) "
                  "VALUES ('一条记忆','对话',5,'hot','2026-11-01','2026-11-01')")
        c.commit()
        self.assertEqual(c.execute('SELECT count(*) FROM messages').fetchone()[0], 1)
        self.assertEqual(c.execute('SELECT count(*) FROM memories').fetchone()[0], 1)
        c.close()

    def test_message_fts_triggers_present(self):
        c = sqlite3.connect(self.db)
        n = c.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger' "
                      "AND name LIKE 'messages_%'").fetchone()[0]
        c.close()
        self.assertGreaterEqual(n, 2, 'messages 的 FTS 同步触发器应该齐')

    def test_dead_columns_are_gone(self):
        c = sqlite3.connect(self.db)
        cols = {r[1] for r in c.execute('PRAGMA table_info(memories)')}
        c.close()
        for dead in ('valid_to', 'invalid_at', 'valence', 'arousal'):
            self.assertNotIn(dead, cols, '%s 是删掉的死字段，不该回来' % dead)



class PetStateTest(unittest.TestCase):
    """examples/pet_state.py：状态 → 动作，空账不能乱动。"""

    def setUp(self):
        import importlib
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, 'pet.db')
        os.environ['LUNA_DB'] = self.db
        spec = _load('pet_state_t', os.path.join(ROOT, 'examples', 'pet_state.py'))
        self.P = spec

    def tearDown(self):
        for suffix in ('', '-wal', '-shm'):
            p = self.db + suffix
            if os.path.exists(p):
                os.remove(p)

    def test_empty_ledger_is_idle_not_doze(self):
        st = self.P.state()
        self.assertEqual(st['act'], 'idle',
                         '没有账的时候该是发呆，不是垂着（内啡肽 0 是基线，不是没劲）')

    def test_affection_moves_it_to_lean(self):
        for i in range(10):
            self.P.E.observe_her('i miss you', uniq_prefix='t%d' % i)
        st = self.P.state()
        self.assertGreater(st['ot'], 50, '十句想你之后，催产素该过线')
        self.assertEqual(st['act'], 'lean')



class ChineseKeywordTest(unittest.TestCase):
    """中文关键词：英文重写时整段丢过一次，用测试钉住。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, 'cn.db')
        os.environ['LUNA_DB'] = self.db
        self.E = _load('endocrine_cn', os.path.join(ROOT, 'hormone', 'endocrine.py'))

    def tearDown(self):
        for suffix in ('', '-wal', '-shm'):
            p = self.db + suffix
            if os.path.exists(p):
                os.remove(p)

    def test_chinese_affection_registers(self):
        before = self.E.snapshot()['ot']
        wrote = self.E.observe_her('我想你了', uniq_prefix='cn1')
        self.assertTrue(wrote, '中文「想你」必须记账（2026-11-01 发现英文重写版把它丢了）')
        self.assertGreater(self.E.snapshot()['ot'], before)

    def test_chinese_negation_is_ignored(self):
        wrote = self.E.observe_her('我不疼，也没生气', uniq_prefix='cn2')
        self.assertFalse(wrote, '带着「不疼／没生气」的句子不该算疼或生气')

    def test_chinese_care_registers(self):
        wrote = self.E.observe_her('你累不累', uniq_prefix='cn3')
        self.assertEqual([k for k, _ in wrote], ['care'], '「你累不累」是关心，不是诉苦')


if __name__ == '__main__':
    unittest.main(verbosity=2)