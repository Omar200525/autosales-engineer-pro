"""API request and response schemas for the backend service."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from core.models import AgentStep, Product, SolutionReport


PipelineRunStatus = Literal["queued", "running", "completed", "failed"]
TelegramNotificationStatus = Literal["disabled", "pending", "sent", "failed"]
SupportedImageType = Literal["image/jpeg", "image/png", "image/webp"]


class PipelineRunCreateRequest(BaseModel):
    """Payload for starting a new pipeline run."""

    raw_brief: str = Field(min_length=1, max_length=12000)
    image_base64: Optional[str] = None
    image_media_type: Optional[SupportedImageType] = None

    @model_validator(mode="after")
    def validate_image_fields(self) -> "PipelineRunCreateRequest":
        if self.image_base64 and not self.image_media_type:
            raise ValueError("image_media_type is required when image_base64 is provided")
        if self.image_media_type and not self.image_base64:
            raise ValueError("image_base64 is required when image_media_type is provided")
        return self


class PipelineRunCreated(BaseModel):
    """Response returned immediately after a pipeline run is created."""

    run_id: str
    status: PipelineRunStatus
    events_url: str
    result_url: str


class PipelineRunSnapshot(BaseModel):
    """Current state of a pipeline run."""

    run_id: str
    status: PipelineRunStatus
    steps: list[AgentStep]
    report: Optional[SolutionReport] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str
    telegram_status: TelegramNotificationStatus = "disabled"
    telegram_error: Optional[str] = None
    telegram_sent_at: Optional[str] = None


class CatalogProductsResponse(BaseModel):
    """Catalog search response."""

    products: list[Product]
    count: int


class BudgetFitRequest(BaseModel):
    """Payload for quote budget what-if analysis."""

    product_ids: list[str] = Field(min_length=1)
    quantities: dict[str, int]
    budget_myr: float = Field(gt=0)
