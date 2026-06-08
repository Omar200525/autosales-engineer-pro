"""FastAPI service exposing the AutoSales Engineer pipeline."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from core.catalog import get_catalog_stats, get_product_by_id, search_products
from core.models import SolutionReport
from core.pdf_generator import generate_pdf
from core.telegram_config import get_telegram_settings, telegram_notifications_requested
from core.tools import calculate_budget_fit
from pipeline import SalesEngineerPipeline

from backend.run_store import PipelineRunStore
from backend.schemas import (
    BudgetFitRequest,
    CatalogProductsResponse,
    PipelineRunCreateRequest,
    PipelineRunCreated,
    PipelineRunSnapshot,
)
from backend.telegram_bot import TelegramBotService
from backend.telegram_notifications import TelegramNotificationResult, notify_run_completed, notify_run_failed


logger = logging.getLogger(__name__)
run_store = PipelineRunStore()
telegram_bot_service = TelegramBotService(run_store, logger=logger)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Manage backend background services."""
    telegram_bot_service.start()
    try:
        yield
    finally:
        telegram_bot_service.stop()


app = FastAPI(
    title="AutoSales Engineer Pro API",
    version="0.1.0",
    description="Backend API for pipeline execution, catalog browsing, and quote export.",
    lifespan=lifespan,
)

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "API_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _decode_optional_image(payload: PipelineRunCreateRequest) -> tuple[bytes | None, str | None]:
    if not payload.image_base64:
        return None, None
    try:
        return base64.b64decode(payload.image_base64, validate=True), payload.image_media_type
    except Exception as exc:
        raise HTTPException(status_code=422, detail="image_base64 must be valid base64") from exc


def _sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _telegram_requested_safely() -> bool:
    try:
        return telegram_notifications_requested()
    except Exception as exc:
        logger.warning("Telegram configuration could not be read: %s", _safe_notification_error(exc))
        return True


def _safe_notification_error(exc: Exception) -> str:
    return str(exc) if str(exc) else type(exc).__name__


def _apply_telegram_result(run_id: str, result: TelegramNotificationResult) -> None:
    if result.status == "sent":
        run_store.mark_telegram_sent(run_id)
        return
    if result.status == "failed":
        error = result.error or "Telegram notification failed"
        logger.warning("Telegram notification failed for run %s: %s", run_id, error)
        run_store.mark_telegram_failed(run_id, error)
        return
    run_store.mark_telegram_disabled(run_id)


def _notify_telegram_completed(run_id: str, report: SolutionReport) -> None:
    if not _telegram_requested_safely():
        run_store.mark_telegram_disabled(run_id)
        return

    run_store.mark_telegram_pending(run_id)
    try:
        settings = get_telegram_settings(validate=False)
        pdf_bytes = generate_pdf(report) if settings.include_pdf else None
    except Exception as exc:
        error = f"Telegram PDF preparation failed: {_safe_notification_error(exc)}"
        logger.warning("%s", error)
        run_store.mark_telegram_failed(run_id, error)
        return

    _apply_telegram_result(run_id, notify_run_completed(run_id, report, pdf_bytes))


def _notify_telegram_failed(run_id: str, error: str) -> None:
    if not _telegram_requested_safely():
        run_store.mark_telegram_disabled(run_id)
        return

    run_store.mark_telegram_pending(run_id)
    _apply_telegram_result(run_id, notify_run_failed(run_id, error))


def _run_pipeline_in_background(run_id: str, payload: PipelineRunCreateRequest) -> None:
    image_bytes, image_media_type = _decode_optional_image(payload)
    pipeline = SalesEngineerPipeline()

    def on_step(step) -> None:
        run_store.add_step(run_id, step)
        telegram_bot_service.update_run_progress(run_id)

    run_store.mark_running(run_id)
    telegram_bot_service.update_run_progress(run_id)
    try:
        report = pipeline.run(
            raw_brief=payload.raw_brief,
            image_bytes=image_bytes,
            image_media_type=image_media_type,
            on_step=on_step,
        )
    except Exception as exc:
        error = str(exc)
        run_store.mark_failed(run_id, error)
        telegram_bot_service.update_run_progress(run_id)
        _notify_telegram_failed(run_id, error)
        return
    run_store.mark_completed(run_id, report)
    telegram_bot_service.update_run_progress(run_id)
    _notify_telegram_completed(run_id, report)


def _start_pipeline_run(payload: PipelineRunCreateRequest):
    _decode_optional_image(payload)
    record = run_store.create()
    telegram_bot_service.notify_run_started(record.run_id)
    thread = threading.Thread(
        target=_run_pipeline_in_background,
        args=(record.run_id, payload),
        daemon=True,
    )
    thread.start()
    return record


def _start_telegram_quote_run(raw_brief: str) -> str:
    payload = PipelineRunCreateRequest(raw_brief=raw_brief)
    return _start_pipeline_run(payload).run_id


telegram_bot_service.set_quote_starter(_start_telegram_quote_run)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a lightweight service health response."""
    return {"status": "ok", "service": "autosales-engineer-api"}


@app.post("/api/pipeline/runs", response_model=PipelineRunCreated, status_code=202)
def create_pipeline_run(payload: PipelineRunCreateRequest) -> PipelineRunCreated:
    """Start a pipeline run and return URLs for events and final state."""
    record = _start_pipeline_run(payload)
    return PipelineRunCreated.model_validate(
        {
            "run_id": record.run_id,
            "status": record.status,
            "events_url": f"/api/pipeline/runs/{record.run_id}/events",
            "result_url": f"/api/pipeline/runs/{record.run_id}",
        }
    )


@app.get("/api/pipeline/runs/{run_id}", response_model=PipelineRunSnapshot)
def get_pipeline_run(run_id: str) -> PipelineRunSnapshot:
    """Return the latest state for a pipeline run."""
    try:
        return run_store.snapshot(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/pipeline/runs/{run_id}/events")
async def stream_pipeline_events(run_id: str) -> StreamingResponse:
    """Stream AgentStep and completion events using Server-Sent Events."""

    async def event_stream():
        cursor = 0
        while True:
            try:
                snapshot = run_store.snapshot(run_id)
            except KeyError:
                yield _sse("error", {"message": f"Pipeline run not found: {run_id}"})
                return

            while cursor < len(snapshot.steps):
                step = snapshot.steps[cursor]
                cursor += 1
                yield _sse("step", step.model_dump())

            if snapshot.status == "completed":
                yield _sse("completed", snapshot.report.model_dump() if snapshot.report else None)
                return
            if snapshot.status == "failed":
                yield _sse("failed", {"message": snapshot.error or "Pipeline failed"})
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/catalog/stats")
def catalog_stats() -> dict:
    """Return local catalog counts and price ranges."""
    return get_catalog_stats()


@app.get("/api/catalog/products", response_model=CatalogProductsResponse)
def catalog_products(
    category: Optional[str] = Query(default=None),
    max_price_myr: Optional[float] = Query(default=None, ge=0),
    min_price_myr: Optional[float] = Query(default=None, ge=0),
    in_stock_only: bool = True,
    q: Optional[str] = Query(default=None, max_length=120),
) -> CatalogProductsResponse:
    """Search local catalog products for the React catalog view."""
    products = search_products(
        category=category,
        max_price=max_price_myr,
        min_price=min_price_myr,
        in_stock_only=in_stock_only,
    )
    if q:
        needle = q.lower()
        products = [
            product
            for product in products
            if needle in product.name.lower() or needle in product.brand.lower() or needle in product.category.lower()
        ]
    return CatalogProductsResponse(products=products, count=len(products))


@app.get("/api/catalog/products/{product_id}")
def catalog_product(product_id: str):
    """Return a single catalog product."""
    product = get_product_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")
    return product


@app.post("/api/tools/budget-fit")
def budget_fit(payload: BudgetFitRequest):
    """Calculate budget fit for selected product IDs and quantities."""
    result = calculate_budget_fit(payload.product_ids, payload.quantities, payload.budget_myr)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return result


@app.post("/api/quotes/pdf")
def quote_pdf(report: SolutionReport) -> Response:
    """Generate a PDF quote from a completed SolutionReport payload."""
    try:
        pdf_bytes = generate_pdf(report)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}") from exc
    safe_client = report.client_name.replace(" ", "_") or "client"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="quote_{safe_client}.pdf"'},
    )
