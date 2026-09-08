"""ParseMode 枚举 / Document 实体 / SQL 列测试。"""

from pathlib import Path

import pytest

from app.domain.entities import Document
from app.domain.enums import ParseMode
from app.repositories.sql.database import create_engine_and_sessionmaker, init_db
from app.repositories.sql.documents import DocumentSqlRepository


def _doc(**overrides) -> Document:
    values = dict(
        filename="a.pdf",
        file_type="pdf",
        file_size=10,
        file_path=Path(__file__),
    )
    values.update(overrides)
    return Document(**values)


def test_document_defaults_to_mineru() -> None:
    doc = Document(filename="x.pdf", file_type="pdf", file_size=1, file_path=Path("x.pdf"))
    assert doc.parse_mode == ParseMode.MINERU


@pytest.fixture
async def sql_repo(tmp_path):
    engine, session_factory = create_engine_and_sessionmaker(tmp_path)
    await init_db(engine)
    yield DocumentSqlRepository(session_factory)
    await engine.dispose()


async def test_sql_repository_persists_parse_mode(sql_repo) -> None:
    created = await sql_repo.create(_doc(parse_mode=ParseMode.PLAIN_TEXT))
    got = await sql_repo.get(created.id)
    assert got is not None and got.parse_mode == ParseMode.PLAIN_TEXT

    defaulted = await sql_repo.create(_doc(filename="b.pdf"))
    assert (await sql_repo.get(defaulted.id)).parse_mode == ParseMode.MINERU
