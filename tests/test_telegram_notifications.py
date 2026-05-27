"""Tests for Telegram notification configuration, formatting, and delivery."""

from __future__ import annotations

import httpx
import pytest

from backend.run_store import PipelineRunStore
from backend.telegram_bot import TelegramBotService, format_progress_message
import backend.telegram_notifications as notifications
from core.llm_utils import now_iso
from core.models import AgentStep, CompatibilityMatrix, QuoteLineItem, ReviewerFeedback, SolutionReport
from core.telegram_client import TelegramClient, TelegramDeliveryError, TelegramDocument
from core.telegram_config import TelegramConfigError, TelegramSettings, get_telegram_settings


def test_telegram_config_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_telegram_env(monkeypatch)

    settings = get_telegram_settings()

    assert settings.enabled is False
    assert settings.bot_token == ""
    assert settings.chat_id == ""


def test_telegram_config_enabled_requires_token_and_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_telegram_env(monkeypatch)
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")

    with pytest.raises(TelegramConfigError) as exc_info:
        get_telegram_settings()

    message = str(exc_info.value)
    assert "TELEGRAM_BOT_TOKEN" in message
    assert "TELEGRAM_CHAT_ID" in message


def test_telegram_client_sends_message_with_mock_transport() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    client = TelegramClient(valid_settings(), transport=httpx.MockTransport(handler))

    response = client.send_message("Quote ready")

    assert response["ok"] is True
    assert len(requests) == 1
    assert requests[0].url.path.endswith("/sendMessage")


def test_telegram_client_edits_message_and_gets_updates_with_mock_transport() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/getUpdates"):
            return httpx.Response(200, json={"ok": True, "result": [{"update_id": 10}]})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    client = TelegramClient(valid_settings(), transport=httpx.MockTransport(handler))

    client.edit_message_text("-100123", 7, "Progress")
    updates = client.get_updates(offset=10, timeout_seconds=1, allowed_updates=["message"])

    assert paths[0].endswith("/editMessageText")
    assert paths[1].endswith("/getUpdates")
    assert updates == [{"update_id": 10}]


def test_telegram_client_error_does_not_leak_token() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    client = TelegramClient(valid_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(TelegramDeliveryError) as exc_info:
        client.send_message("Quote ready")

    assert "Unauthorized" in str(exc_info.value)
    assert "secret-token" not in str(exc_info.value)


def test_build_completion_message_includes_quote_summary() -> None:
    message = notifications.build_completion_message("run-123", sample_report())

    assert "AutoSales Engineer Pro quote completed" in message
    assert "Client: Acme KL Office" in message
    assert "Total: MYR 3,000 of MYR 5,000" in message
    assert "2 x Cisco Catalyst 1000" in message
    assert len(message) <= notifications.MAX_MESSAGE_CHARS


def test_notify_run_completed_sends_message_and_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_telegram_env(monkeypatch)
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")
    sent: list[tuple[str, object]] = []

    class FakeTelegramClient:
        def __init__(self, settings: TelegramSettings) -> None:
            sent.append(("init", settings.chat_id))

        def send_message(self, text: str) -> dict:
            sent.append(("message", text))
            return {"ok": True}

        def send_document(self, document: TelegramDocument) -> dict:
            sent.append(("document", document.filename))
            return {"ok": True}

    monkeypatch.setattr(notifications, "TelegramClient", FakeTelegramClient)

    result = notifications.notify_run_completed("run-123456", sample_report(), b"%PDF-1.4")

    assert result.status == "sent"
    assert sent[0] == ("init", "-100123")
    assert sent[1][0] == "message"
    assert sent[2] == ("document", "quote_Acme_KL_Office_run-1234.pdf")


def test_run_store_exposes_telegram_status() -> None:
    store = PipelineRunStore()
    record = store.create()

    assert store.snapshot(record.run_id).telegram_status == "disabled"

    store.mark_telegram_pending(record.run_id)
    assert store.snapshot(record.run_id).telegram_status == "pending"

    store.mark_telegram_failed(record.run_id, "chat not found")
    snapshot = store.snapshot(record.run_id)

    assert snapshot.telegram_status == "failed"
    assert snapshot.telegram_error == "chat not found"


def test_run_store_tracks_telegram_subscribers_and_progress_messages() -> None:
    store = PipelineRunStore()
    record = store.create()

    store.subscribe_telegram_chat("123")
    store.subscribe_telegram_chat("456")
    store.unsubscribe_telegram_chat("456")
    store.set_telegram_progress_message(record.run_id, "123", 99)

    assert store.latest_run_id() == record.run_id
    assert store.list_telegram_subscribers() == ["123"]
    assert store.list_telegram_progress_messages(record.run_id) == {"123": 99}


def test_format_progress_message_for_running_snapshot() -> None:
    store = PipelineRunStore()
    record = store.create()
    store.mark_running(record.run_id)
    store.add_step(
        record.run_id,
        AgentStep(
            iteration=1,
            agent_name="Parser",
            action="Parsed client requirements",
            tool_called=None,
            tool_args=None,
            tool_result_summary="Detected budget and location",
            timestamp=now_iso(),
        ),
    )

    message = format_progress_message(store.snapshot(record.run_id))

    assert "Status: Running" in message
    assert "[active] Parser" in message
    assert "Parsed client requirements" in message


def test_bot_start_subscribes_chat_and_replies(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_telegram_env(monkeypatch)
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    store = PipelineRunStore()
    sent: list[tuple[str, str]] = []

    class FakeClient:
        def send_message(self, text: str, chat_id: str | None = None) -> dict:
            sent.append((chat_id or "", text))
            return {"ok": True, "result": {"message_id": 1}}

    service = TelegramBotService(store)
    service._handle_update(  # noqa: SLF001 - targeted command handling test
        {"message": {"chat": {"id": 5776996033}, "text": "/start"}},
        FakeClient(),
    )

    assert store.list_telegram_subscribers() == ["5776996033"]
    assert sent[0][0] == "5776996033"
    assert "subscribed to live quote progress" in sent[0][1]


def test_bot_quote_command_starts_run_and_subscribes_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_telegram_env(monkeypatch)
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    store = PipelineRunStore()
    started: list[str] = []
    sent: list[tuple[str, str]] = []

    class FakeClient:
        def send_message(self, text: str, chat_id: str | None = None) -> dict:
            sent.append((chat_id or "", text))
            return {"ok": True, "result": {"message_id": 1}}

    def start_quote(brief: str) -> str:
        started.append(brief)
        return "run-from-telegram"

    service = TelegramBotService(store, quote_starter=start_quote)
    service._handle_update(  # noqa: SLF001 - targeted command handling test
        {"message": {"chat": {"id": 5776996033}, "text": f"/quote {sample_brief_text()}"}},
        FakeClient(),
    )

    assert store.list_telegram_subscribers() == ["5776996033"]
    assert started == [sample_brief_text()]
    assert "Quote run started: run-from-telegram" in sent[0][1]


def test_bot_pasted_brief_starts_run(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_telegram_env(monkeypatch)
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    store = PipelineRunStore()
    started: list[str] = []

    class FakeClient:
        def send_message(self, text: str, chat_id: str | None = None) -> dict:
            return {"ok": True, "result": {"message_id": 1}}

    def start_quote(brief: str) -> str:
        started.append(brief)
        return "run-direct-brief"

    service = TelegramBotService(store, quote_starter=start_quote)
    service._handle_update(  # noqa: SLF001 - targeted command handling test
        {"message": {"chat": {"id": 5776996033}, "text": sample_brief_text()}},
        FakeClient(),
    )

    assert started == [sample_brief_text()]


def clear_telegram_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "TELEGRAM_ENABLED",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "TELEGRAM_INCLUDE_PDF",
        "TELEGRAM_BOT_POLLING_ENABLED",
        "TELEGRAM_POLLING_TIMEOUT_SECONDS",
        "TELEGRAM_TIMEOUT_SECONDS",
        "TELEGRAM_API_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def valid_settings() -> TelegramSettings:
    return TelegramSettings(
        enabled=True,
        bot_token="secret-token",
        chat_id="-100123",
        include_pdf=True,
        bot_polling_enabled=True,
        polling_timeout_seconds=1,
        timeout_seconds=5,
        api_base_url="https://api.telegram.org",
    )


def sample_report() -> SolutionReport:
    line_item = QuoteLineItem(
        product_id="prod_net_001",
        product_name="Cisco Catalyst 1000",
        brand="Cisco",
        category="networking",
        quantity=2,
        unit_price_myr=1500,
        subtotal_myr=3000,
        confidence_score=0.92,
        confidence_reason="Fits managed switching requirement",
        product_url="https://example.com/cisco",
        source_platform="catalog",
        shipping_fee_myr=0,
        sst_myr=180,
        tco_myr=3180,
    )
    return SolutionReport(
        client_name="Acme KL Office",
        use_case="Office network refresh",
        delivery_location="Kuala Lumpur",
        line_items=[line_item],
        total_price_myr=3000,
        budget_myr=5000,
        within_budget=True,
        budget_utilization_pct=60,
        compatibility_matrix=CompatibilityMatrix(pairs_checked=[], all_compatible=True, issues=[]),
        delivery_feasible=True,
        unavailable_products=[],
        self_critique_history=[],
        reviewer_feedback=ReviewerFeedback(
            approved=True,
            risk_flags=["Confirm rack space before delivery"],
            suggestions=["Add a spare switch if budget allows"],
            overall_assessment="Strong fit for the client brief.",
            technical_score=8.8,
            commercial_score=8.1,
        ),
        executive_summary="A concise network refresh package.",
        recommendations=["Proceed with catalog-backed switch selection"],
        warnings=[],
        agent_steps=[],
        total_iterations=1,
        pipeline_duration_seconds=12.5,
        brief_source="text",
        reasoning_summary="Selected managed switching for office requirements.",
        delivery_timeline_estimate="3-5 business days",
        logistics_tco_total_myr=3180,
    )


def sample_brief_text() -> str:
    return """Client: Acme KL Office
Use case: Small office setup for 15 staff with secure internet, WiFi, file sharing, Microsoft 365, and video conferencing.
Budget: MYR 25000
Delivery location: Kuala Lumpur
Number of users: 15
Specific requirements:
- WiFi coverage for 3 floors
- NAS for shared files
- UPS backup power
- Microsoft 365 for all users
- Video conferencing room setup"""