"""问答链路 Trace：收集各阶段结构化数据，问答结束后一次性组装成 QueryLog。"""

from datetime import datetime
from uuid import UUID

from app.domain.entities import Citation, QueryLog, QueryLogStep


class Trace:
    def __init__(self, *, session_id: UUID, session_title: str, question: str) -> None:
        self._session_id = session_id
        self._session_title = session_title
        self._question = question
        self._steps: list[QueryLogStep] = []

    def record(
        self,
        *,
        stage: str,
        label: str,
        duration_ms: float,
        summary: str,
        data: dict,
    ) -> None:
        self._steps.append(
            QueryLogStep(
                stage=stage,
                label=label,
                duration_ms=round(float(duration_ms), 1),
                summary=summary,
                data=data,
            )
        )

    def steps(self) -> list[QueryLogStep]:
        return list(self._steps)

    def build(
        self,
        *,
        status: str,
        error: str | None,
        answer: str | None,
        citations: list[Citation],
        total_ms: float,
        created_at: datetime,
    ) -> QueryLog:
        return QueryLog(
            session_id=self._session_id,
            session_title=self._session_title,
            question=self._question,
            status=status,
            error=error,
            total_ms=total_ms,
            answer=answer,
            steps=self.steps(),
            citations=citations,
            created_at=created_at,
        )
