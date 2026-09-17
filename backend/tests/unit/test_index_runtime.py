"""索引运行时能力测试：扩展加载 + FTS5 + jieba 分词。

这两个能力是 SQLite 索引后端（FTS5 + sqlite-vec）的硬前提：
解释器必须支持 `enable_load_extension`（uv 管理的 CPython 支持，macOS 系统自带的不支持）。
"""

import sqlite3

import jieba
import sqlite_vec


def test_sqlite_supports_extension_loading() -> None:
    con = sqlite3.connect(":memory:")
    assert hasattr(con, "enable_load_extension")
    con.enable_load_extension(True)
    sqlite_vec.load(con)
    assert con.execute("select vec_version()").fetchone()[0].startswith("v")


def test_fts5_with_jieba_tokens_matches_two_char_words() -> None:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE VIRTUAL TABLE f USING fts5(tokens)")
    tokens = " ".join(jieba.lcut("关于股份回购进展公告"))
    con.execute("INSERT INTO f(rowid, tokens) VALUES (1, ?)", (tokens,))
    query = " ".join(jieba.lcut("回购进展"))
    rows = con.execute("SELECT rowid FROM f WHERE f MATCH ?", (query,)).fetchall()
    assert rows == [(1,)]
