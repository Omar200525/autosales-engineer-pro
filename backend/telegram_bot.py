"""Conversational Telegram bot service for live pipeline progress."""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable
from typing import Any

from backend.run_store import PipelineRunStore
from backend.schemas import PipelineRunSnapshot
from core.models import AgentStep
from core.telegram_client import TelegramClient, TelegramDeliveryError
from core.telegram_config import TelegramConfigError, TelegramSettings, get_telegram_settings, telegram_notifications_requested


AGENT_ORDER = ("VisualAnalyst", "Parser", "SalesEngineer", "Reviewer")
AGENT_LABELS = {
    "VisualAnalyst": "Vision",
    "Parser": "Parser",
    "SalesEngineer": "Sales Engineer",
    "Reviewer": "Reviewer",
}

HELP_TEXT = """AutoSales Engineer Pro bot

Commands:
/start - connect this chat and subscribe to live quote progress
/help - show commands
/status - show the latest run
/status <run_id> - show a specific run
/quote <brief> - start a quote from this chat
/subscribe - receive live run progress in this chat
/unsubscribe - stop live progress in this chat
""".strip()

QuoteStarter = Callable[[str], str]


class TelegramBotService:
    """Runs a small Telegram long-polling command bot in a background thread."""

    def __init__(
        self,
        run_store: PipelineRunStore,
        *,
        client_factory: Callable[[TelegramSettings], TelegramClient] = TelegramClient,
        quote_starter: QuoteStarter | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._run_store = run_store
        self._client_factory = client_factory
        self._quote_starter = quote_starter
        self._logger = logger or logging.getLogger(__name__)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._offset: int | None = None
        self._progress_lock = threading.Lock()
        self._progress_inflight: set[str] = set()
        self._progress_dirty: set[str] = set()

    def start(self) -> None:
        """Start long polling if Telegram is enabled for this process."""
        if self._thread and self._thread.is_alive():
            return
        if _running_under_pytest():
            return
        try:
            settings = get_telegram_settings(validate=False)
        except TelegramConfigError as exc:
            self._logger.warning("Telegram bot settings invalid: %s", exc)
            return
        if not settings.enabled or not settings.bot_polling_enabled:
            return
        if not settings.bot_token:
            self._logger.warning("Telegram bot polling is enabled but TELEGRAM_BOT_TOKEN is missing")
            return

        if settings.chat_id:
            self._run_store.subscribe_telegram_chat(settings.chat_id)

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, name="telegram-bot-poller", daemon=True)
        self._thread.start()
        self._logger.info("Telegram bot polling started")

    def stop(self) -> None:
        """Ask the poll loop to stop."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None

    def set_quote_starter(self, quote_starter: QuoteStarter) -> None:
        """Register the callback used to start quote runs from Telegram."""
        self._quote_starter = quote_starter

    def notify_run_started(self, run_id: str) -> None:
        """Create one live progress message per subscribed chat."""
        threading.Thread(target=self._notify_run_started_sync, args=(run_id,), daemon=True).start()

    def _notify_run_started_sync(self, run_id: str) -> None:
        client = self._client_or_none()
        if client is None:
            return
        for chat_id in self._run_store.list_telegram_subscribers():
            try:
                snapshot = self._run_store.snapshot(run_id)
                response = client.send_message(format_progress_message(snapshot), chat_id=chat_id)
                message_id = _message_id_from_response(response)
                if message_id is not None:
                    self._run_store.set_telegram_progress_message(run_id, chat_id, message_id)
            except Exception as exc:
                self._logger.warning("Could not create Telegram progress message for run %s: %s", run_id, _safe_error(exc))

    def update_run_progress(self, run_id: str) -> None:
        """Edit live Telegram progress messages for a run."""
        with self._progress_lock:
            if run_id in self._progress_inflight:
                self._progress_dirty.add(run_id)
                return
            self._progress_inflight.add(run_id)
        threading.Thread(target=self._progress_worker, args=(run_id,), daemon=True).start()

    def _progress_worker(self, run_id: str) -> None:
        while True:
            self._update_run_progress_sync(run_id)
            with self._progress_lock:
                if run_id in self._progress_dirty:
                    self._progress_dirty.remove(run_id)
                    continue
                self._progress_inflight.discard(run_id)
                return

    def _update_run_progress_sync(self, run_id: str) -> None:
        progress_messages = self._run_store.list_telegram_progress_messages(run_id)
        if not progress_messages:
            return
        client = self._client_or_none()
        if client is None:
            return
        try:
            snapshot = self._run_store.snapshot(run_id)
        except KeyError:
            return
        message = format_progress_message(snapshot)
        for chat_id, message_id in progress_messages.items():
            try:
                client.edit_message_text(chat_id, message_id, message)
            except TelegramDeliveryError as exc:
                if "message is not modified" not in str(exc).lower():
                    self._logger.warning("Could not edit Telegram progress message for run %s: %s", run_id, _safe_error(exc))
            except Exception as exc:
                self._logger.warning("Could not edit Telegram progress message for run %s: %s", run_id, _safe_error(exc))

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                settings = get_telegram_settings(validate=False)
                if not settings.enabled or not settings.bot_polling_enabled or not settings.bot_token:
                    self._stop_event.wait(5)
                    continue
                client = self._client_factory(settings)
                updates = client.get_updates(
                    offset=self._offset,
                    timeout_seconds=settings.polling_timeout_seconds,
                    allowed_updates=["message", "edited_message"],
                )
                for update in updates:
                    update_id = update.get("update_id")
                    if isinstance(update_id, int):
                        self._offset = update_id + 1
                    self._handle_update(update, client)
            except Exception as exc:
                self._logger.warning("Telegram bot polling error: %s", _safe_error(exc))
                self._stop_event.wait(5)

    def _handle_update(self, update: dict[str, Any], client: TelegramClient) -> None:
        message = update.get("message") or update.get("edited_message")
        if not isinstance(message, dict):
            return
        chat = message.get("chat")
        if not isinstance(chat, dict) or "id" not in chat:
            return
        chat_id = str(chat["id"])
        text = str(message.get("text") or "").strip()

        if not text.startswith("/"):
            if _looks_like_brief(text):
                self._start_quote_from_chat(chat_id, text, client)
            else:
                client.send_message("Send /help to see bot commands, or paste a full brief to start a quote.", chat_id=chat_id)
            return

        parts = text.split(maxsplit=1)
        command_text = parts[0]
        argument = parts[1].strip() if len(parts) > 1 else ""
        command = command_text.split("@", 1)[0].lower()

        if command == "/start":
            self._run_store.subscribe_telegram_chat(chat_id)
            if argument:
                self._start_quote_from_chat(chat_id, argument, client)
                return
            client.send_message(f"Connected. This chat is subscribed to live quote progress.\n\n{HELP_TEXT}", chat_id=chat_id)
            return
        if command == "/help":
            client.send_message(HELP_TEXT, chat_id=chat_id)
            return
        if command == "/subscribe":
            self._run_store.subscribe_telegram_chat(chat_id)
            client.send_message("Subscribed. New quote runs will show live progress here.", chat_id=chat_id)
            return
        if command == "/unsubscribe":
            self._run_store.unsubscribe_telegram_chat(chat_id)
            client.send_message("Unsubscribed. You can re-enable live progress with /subscribe.", chat_id=chat_id)
            return
        if command == "/status":
            client.send_message(self._status_message(argument), chat_id=chat_id)
            return
        if command == "/quote":
            if not argument:
                client.send_message(
                    "Send /quote followed by the client brief, or paste the full brief directly into chat.",
                    chat_id=chat_id,
                )
                return
            self._start_quote_from_chat(chat_id, argument, client)
            return

        client.send_message("Unknown command. Send /help to see available commands.", chat_id=chat_id)

    def _start_quote_from_chat(self, chat_id: str, brief: str, client: TelegramClient) -> None:
        brief = brief.strip()
        if not self._quote_starter:
            client.send_message("Telegram quote creation is not available in this backend process.", chat_id=chat_id)
            return
        if len(brief) < 20:
            client.send_message("That brief is too short. Send client, use case, budget, location, and requirements.", chat_id=chat_id)
            return

        self._run_store.subscribe_telegram_chat(chat_id)
        try:
            run_id = self._quote_starter(brief)
        except Exception as exc:
            self._logger.warning("Could not start Telegram quote: %s", _safe_error(exc))
            client.send_message(f"Could not start quote: {_safe_error(exc)}", chat_id=chat_id)
            return
        client.send_message(
            f"Quote run started: {run_id}\nI will update the live progress message in this chat.",
            chat_id=chat_id,
        )

    def _status_message(self, run_id: str) -> str:
        target_run_id = run_id or self._run_store.latest_run_id()
        if not target_run_id:
            return "No pipeline runs yet. Start a quote in the React app, then use /status."
        try:
            return format_progress_message(self._run_store.snapshot(target_run_id))
        except KeyError:
            return f"Run not found: {target_run_id}"

    def _client_or_none(self) -> TelegramClient | None:
        try:
            settings = get_telegram_settings(validate=False)
            if not settings.enabled or not settings.bot_token:
                return None
            return self._client_factory(settings)
        except Exception as exc:
            self._logger.warning("Telegram client unavailable: %s", _safe_error(exc))
            return None


def format_progress_message(snapshot: PipelineRunSnapshot) -> str:
    """Format one compact live-progress message for Telegram."""
    latest_step = snapshot.steps[-1] if snapshot.steps else None
    status = snapshot.status.capitalize()
    lines = [
        "AutoSales Engineer Pro live progress",
        f"Run: {snapshot.run_id}",
        f"Status: {status}",
        "",
    ]
    lines.extend(_agent_lines(snapshot.steps, snapshot.status))

    if latest_step:
        lines.extend(["", f"Latest: {_clean(latest_step.action)}"])
        if latest_step.tool_result_summary:
            lines.append(_clean(latest_step.tool_result_summary)[:220])

    if snapshot.status == "completed" and snapshot.report:
        report = snapshot.report
        budget_status = "within budget" if report.within_budget else "over budget"
        delivery_status = "delivery feasible" if report.delivery_feasible else "delivery needs review"
        lines.extend(
            [
                "",
                f"Client: {_clean(report.client_name)}",
                f"Total: MYR {report.total_price_myr:,.0f} ({budget_status})",
                f"Delivery: {delivery_status}",
            ]
        )
    elif snapshot.status == "failed":
        lines.extend(["", f"Error: {_clean(snapshot.error or 'Pipeline failed')}"])

    return "\n".join(lines)[:3900]


def _agent_lines(steps: list[AgentStep], status: str) -> list[str]:
    seen = {step.agent_name for step in steps}
    latest = steps[-1].agent_name if steps else None
    lines = []
    for agent_name in AGENT_ORDER:
        if status == "running" and latest == agent_name:
            marker = "active"
        elif agent_name in seen or status == "completed":
            marker = "done"
        elif status == "failed" and latest == agent_name:
            marker = "failed"
        else:
            marker = "pending"
        lines.append(f"[{marker}] {AGENT_LABELS[agent_name]}")
    return lines


def _message_id_from_response(response: dict[str, Any]) -> int | None:
    result = response.get("result")
    if isinstance(result, dict) and isinstance(result.get("message_id"), int):
        return result["message_id"]
    return None


def _safe_error(exc: Exception) -> str:
    return str(exc) if str(exc) else type(exc).__name__


def _clean(value: object) -> str:
    return " ".join(str(value).split())


def _looks_like_brief(text: str) -> bool:
    lowered = text.lower()
    markers = ("client:", "use case:", "budget:", "delivery location:", "specific requirements:")
    return len(text.strip()) >= 60 and sum(marker in lowered for marker in markers) >= 2


def _running_under_pytest() -> bool:
    return any("pytest" in argument for argument in sys.argv)