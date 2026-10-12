"""Pydantic request and response contracts for runtime ticket APIs."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

UrgencyLevel = Literal["Low", "Medium", "High"]
TicketStatus = Literal["open", "in_progress", "resolved"]


class TicketRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000, description="Support ticket text")


class TicketStatusUpdateRequest(BaseModel):
    status: TicketStatus = Field(description="New ticket processing status")


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticket_id: str
    text: str
    status: TicketStatus
    category: str
    assigned_team: str
    urgency: float = Field(ge=0, le=1)
    urgency_level: UrgencyLevel
    created_at: datetime
    confidence: float | None = Field(default=None, ge=0, le=1)
    explanation: dict[str, object] | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["connected"]
    model: Literal["loaded"]
    nlp: Literal["ready"]


class TicketListResponse(TicketResponse):
    pass


class StatisticsResponse(BaseModel):
    total_tickets: int = Field(ge=0)
    average_urgency: float = Field(ge=0, le=1)
    category_distribution: dict[str, int]


class MetricsResponse(BaseModel):
    accuracy: float = Field(ge=0, le=1)
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    f1_score: float = Field(ge=0, le=1)
    macro_precision: float = Field(ge=0, le=1)
    macro_recall: float = Field(ge=0, le=1)
    macro_f1: float = Field(ge=0, le=1)
    majority_baseline_accuracy: float = Field(ge=0, le=1)
    dataset_rows: int = Field(ge=0)
    test_rows: int = Field(ge=0)
