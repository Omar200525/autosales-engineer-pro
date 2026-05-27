"""In-memory pipeline run state for local API development."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4

from core.llm_utils import now_iso
from core.models import AgentStep, SolutionReport

from backend.schemas import PipelineRunSnapshot, PipelineRunStatus, TelegramNotificationStatus


@dataclass
class PipelineRunRecord:
    """Mutable state for one pipeline execution."""

    run_id: str
    status: PipelineRunStatus
    created_at: str
    updated_at: str
    steps: list[AgentStep] = field(default_factory=list)
    report: SolutionReport | None = None
    error: str | None = None
    telegram_status: TelegramNotificationStatus = "disabled"
    telegram_error: str | None = None
    telegram_sent_at: str | None = None


class PipelineRunStore:
    """Thread-safe local run store.

    This is intentionally simple for the first API slice. A later persistence
    layer can keep the same snapshot contract and move records into SQLite or
    PostgreSQL.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._records: dict[str, PipelineRunRecord] = {}
        self._latest_run_id: str | None = None
        self._telegram_subscribers: set[str] = set()
        self._telegram_progress_messages: dict[str, dict[str, int]] = {}

    def create(self) -> PipelineRunRecord:
        timestamp = now_iso()
        record = PipelineRunRecord(
            run_id=str(uuid4()),
            status="queued",
            created_at=timestamp,
            updated_at=timestamp,
        )
        with self._lock:
            self._records[record.run_id] = record
            self._latest_run_id = record.run_id
        return record

    def latest_run_id(self) -> str | None:
        with self._lock:
            return self._latest_run_id

    def mark_running(self, run_id: str) -> None:
        with self._lock:
            record = self._require(run_id)
            record.status = "running"
            record.updated_at = now_iso()

    def add_step(self, run_id: str, step: AgentStep) -> None:
        with self._lock:
            record = self._require(run_id)
            record.steps.append(step)
            record.updated_at = now_iso()

    def mark_completed(self, run_id: str, report: SolutionReport) -> None:
        with self._lock:
            record = self._require(run_id)
            record.status = "completed"
            record.report = report
            record.error = None
            record.updated_at = now_iso()

    def mark_failed(self, run_id: str, error: str) -> None:
        with self._lock:
            record = self._require(run_id)
            record.status = "failed"
            record.error = error
            record.updated_at = now_iso()

    def mark_telegram_pending(self, run_id: str) -> None:
        self._set_telegram_status(run_id, "pending")

    def mark_telegram_disabled(self, run_id: str) -> None:
        self._set_telegram_status(run_id, "disabled")

    def mark_telegram_sent(self, run_id: str) -> None:
        self._set_telegram_status(run_id, "sent", sent_at=now_iso())

    def mark_telegram_failed(self, run_id: str, error: str) -> None:
        self._set_telegram_status(run_id, "failed", error=error)

    def subscribe_telegram_chat(self, chat_id: str) -> None:
        with self._lock:
            self._telegram_subscribers.add(chat_id)

    def unsubscribe_telegram_chat(self, chat_id: str) -> None:
        with self._lock:
            self._telegram_subscribers.discard(chat_id)

    def list_telegram_subscribers(self) -> list[str]:
        with self._lock:
            return sorted(self._telegram_subscribers)

    def set_telegram_progress_message(self, run_id: str, chat_id: str, message_id: int) -> None:
        with self._lock:
            self._telegram_progress_messages.setdefault(run_id, {})[chat_id] = message_id

    def list_telegram_progress_messages(self, run_id: str) -> dict[str, int]:
        with self._lock:
            return dict(self._telegram_progress_messages.get(run_id, {}))

    def snapshot(self, run_id: str) -> PipelineRunSnapshot:
        with self._lock:
            record = self._require(run_id)
            return PipelineRunSnapshot.model_validate(
                {
                    "run_id": record.run_id,
                    "status": record.status,
                    "steps": [step.model_dump() for step in record.steps],
                    "report": record.report.model_dump() if record.report else None,
                    "error": record.error,
                    "created_at": record.created_at,
                    "updated_at": record.updated_at,
                    "telegram_status": record.telegram_status,
                    "telegram_error": record.telegram_error,
                    "telegram_sent_at": record.telegram_sent_at,
                }
            )

    def _set_telegram_status(
        self,
        run_id: str,
        status: TelegramNotificationStatus,
        error: str | None = None,
        sent_at: str | None = None,
    ) -> None:
        with self._lock:
            record = self._require(run_id)
            record.telegram_status = status
            record.telegram_error = error
            record.telegram_sent_at = sent_at
            record.updated_at = now_iso()

    def _require(self, run_id: str) -> PipelineRunRecord:
        try:
            return self._records[run_id]
        except KeyError as exc:
            raise KeyError(f"Pipeline run not found: {run_id}") from exc
