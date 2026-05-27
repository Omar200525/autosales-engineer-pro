"""Telegram notification formatting and delivery helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re

from core.models import SolutionReport
from core.telegram_client import TelegramClient, TelegramDeliveryError, TelegramDocument
from core.telegram_config import TelegramConfigError, get_telegram_settings, telegram_notifications_requested


MAX_MESSAGE_CHARS = 3900


@dataclass(frozen=True)
class TelegramNotificationResult:
    """Result returned after attempting to notify Telegram."""

    status: str
    error: str | None = None


def build_completion_message(run_id: str, report: SolutionReport) -> str:
    """Build a concise Telegram summary for a completed quote."""
    budget_status = "within budget" if report.within_budget else "over budget"
    delivery_status = "delivery feasible" if report.delivery_feasible else "delivery needs review"
    lines = [
        "AutoSales Engineer Pro quote completed",
        f"Run: {run_id}",
        f"Client: {_clean(report.client_name)}",
        f"Use case: {_clean(report.use_case)}",
        f"Total: {_money(report.total_price_myr)} of {_money(report.budget_myr)} ({budget_status})",
        f"Delivery: {_clean(report.delivery_location)} - {delivery_status}",
        (
            "Reviewer: "
            f"technical {report.reviewer_feedback.technical_score:.1f}/10, "
            f"commercial {report.reviewer_feedback.commercial_score:.1f}/10"
        ),
    ]

    if report.line_items:
        lines.extend(["", "Top items:"])
        for item in report.line_items[:5]:
            lines.append(f"- {item.quantity} x {_clean(item.product_name)} ({_money(item.subtotal_myr)})")

    risk_items = [*report.reviewer_feedback.risk_flags, *report.warnings]
    if risk_items:
        lines.extend(["", "Risks:"])
        for risk in risk_items[:4]:
            lines.append(f"- {_clean(risk)}")

    if report.recommendations:
        lines.extend(["", "Recommendations:"])
        for recommendation in report.recommendations[:3]:
            lines.append(f"- {_clean(recommendation)}")

    return _limit_message("\n".join(lines))


def build_failure_message(run_id: str, error: str) -> str:
    """Build a Telegram message for a failed pipeline run."""
    return _limit_message(
        "\n".join(
            [
                "AutoSales Engineer Pro quote failed",
                f"Run: {run_id}",
                f"Error: {_clean(error)}",
            ]
        )
    )


def quote_pdf_filename(run_id: str, report: SolutionReport) -> str:
    """Return a safe PDF filename for Telegram document upload."""
    safe_client = re.sub(r"[^A-Za-z0-9_.-]+", "_", report.client_name).strip("_")[:60]
    safe_client = safe_client or "client"
    return f"quote_{safe_client}_{run_id[:8]}.pdf"


def notify_run_completed(run_id: str, report: SolutionReport, pdf_bytes: bytes | None = None) -> TelegramNotificationResult:
    """Send a Telegram success notification, optionally with a quote PDF."""
    try:
        if not telegram_notifications_requested():
            return TelegramNotificationResult(status="disabled")
        settings = get_telegram_settings()
        client = TelegramClient(settings)
        client.send_message(build_completion_message(run_id, report))
        if settings.include_pdf and pdf_bytes:
            client.send_document(
                TelegramDocument(
                    filename=quote_pdf_filename(run_id, report),
                    content=pdf_bytes,
                    caption=f"Quote PDF for {_clean(report.client_name)} ({run_id[:8]})",
                )
            )
        return TelegramNotificationResult(status="sent")
    except (TelegramConfigError, TelegramDeliveryError) as exc:
        return TelegramNotificationResult(status="failed", error=str(exc))
    except Exception as exc:
        return TelegramNotificationResult(status="failed", error=f"Unexpected Telegram error: {type(exc).__name__}")


def notify_run_failed(run_id: str, error: str) -> TelegramNotificationResult:
    """Send a Telegram failure notification for a pipeline run."""
    try:
        if not telegram_notifications_requested():
            return TelegramNotificationResult(status="disabled")
        settings = get_telegram_settings()
        client = TelegramClient(settings)
        client.send_message(build_failure_message(run_id, error))
        return TelegramNotificationResult(status="sent")
    except (TelegramConfigError, TelegramDeliveryError) as exc:
        return TelegramNotificationResult(status="failed", error=str(exc))
    except Exception as exc:
        return TelegramNotificationResult(status="failed", error=f"Unexpected Telegram error: {type(exc).__name__}")


def _clean(value: object) -> str:
    return " ".join(str(value).split())


def _money(value: float) -> str:
    return f"MYR {value:,.0f}"


def _limit_message(message: str) -> str:
    if len(message) <= MAX_MESSAGE_CHARS:
        return message
    return f"{message[: MAX_MESSAGE_CHARS - 24].rstrip()}\n... truncated"