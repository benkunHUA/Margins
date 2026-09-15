"""黄金集 payload 校验测试。"""

import pytest
from pydantic import ValidationError

from app.domain.entities import EvalDatasetPayload, EvalGold, EvalItemPayload


def _gold(**overrides) -> EvalGold:
    values = {"doc_title": "a.pdf", "snippet": "答案片段"}
    values.update(overrides)
    return EvalGold(**values)


def test_gold_requires_one_locator() -> None:
    with pytest.raises(ValidationError):
        EvalGold(doc_title="a.pdf")


def test_no_answer_item_must_have_empty_gold() -> None:
    with pytest.raises(ValidationError):
        EvalItemPayload(id="q1", question="q", category="no_answer", gold=[_gold()])
    assert EvalItemPayload(id="q2", question="q", category="no_answer").gold == []


def test_dataset_rejects_duplicate_item_ids() -> None:
    item = EvalItemPayload(
        id="q1", question="q", category="single_doc_fact", gold=[_gold()]
    )
    with pytest.raises(ValidationError):
        EvalDatasetPayload(name="集", items=[item, item])


def test_dataset_valid_payload() -> None:
    payload = EvalDatasetPayload(
        name="公告集",
        description="d",
        items=[
            EvalItemPayload(
                id="q1",
                question="价格上限？",
                category="single_doc_fact",
                gold=[_gold(keywords=["40.2 元/股"])],
            )
        ],
    )
    assert payload.items[0].gold[0].keywords == ["40.2 元/股"]
