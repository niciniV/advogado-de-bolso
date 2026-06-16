"""Wire types for the Advogado de Bolso API.

These are the snake_case types used at the HTTP boundary. The service layer
fills the optional fields and the frontend maps them to camelCase. All
field-level validation lives here so the API returns 422 before the service
runs (ISSUE-REVIEW-007, ISSUE-M3-007).

Related
-------
- `contracts.py` — typed tool-return envelopes referenced inside
  `StructuredChatResponse.deadline` and `.template_letter`.
- `adapter.py` — produces `StructuredChatResponse` from `prose + tool_returns`.
- `.opencode/plans/02-schemas.md` — the wire-type spec.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.types import StringConstraints

from advogado_de_bolso.contracts import DeadlineResult, DraftedDocument

# ---------------------------------------------------------------------------
# Shared literal aliases
# ---------------------------------------------------------------------------

# Reused on `StructuredChatRequest` and `UpdateCaseRequest` (ISSUE-REVIEW-007)
IconName = Literal["shopping_bag", "receipt_long", "local_shipping", "gavel"]
ResponseStyle = Literal["simples", "detalhado", "firme"]

CaseTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


# ---------------------------------------------------------------------------
# Chat request / response
# ---------------------------------------------------------------------------


class StructuredChatRequest(BaseModel):
    """POST /api/chat/structured body."""

    message: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=8_000),
    ]
    session_id: UUID | None = None
    response_style: ResponseStyle | None = None
    title: CaseTitle | None = None
    icon_name: IconName | None = None


class StructuredChatResponse(BaseModel):
    """POST /api/chat/structured response.

    The adapter constructs this BEFORE the service appends the current turn,
    so `updated_at` and `chat_history` MUST have assembly-safe defaults
    (ISSUE-USR-015). The service overwrites both before returning.
    """

    session_id: str = ""
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    chat_history: list[ChatMessage] = Field(default_factory=list)
    step_title: str = ""
    step_content: str = ""
    relevant_title: str = ""
    relevant_content: str = ""
    deadline: DeadlineResult | None = None
    questions: list[str] = Field(default_factory=list)
    suggestive_text: str | None = None
    template_letter: str | None = None
    template_letter_assunto: str | None = None
    quick_replies: list[str] = Field(default_factory=list)
    blocked: bool = False
    blocked_message: str | None = None


# ---------------------------------------------------------------------------
# Case listing / detail
# ---------------------------------------------------------------------------


class CaseSummary(BaseModel):
    """GET /api/cases item."""

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    last_message: str
    icon_name: IconName
    response_style: ResponseStyle
    tag_text: str | None = None
    is_demo: bool = False


class CaseResponse(BaseModel):
    """GET /api/cases/{id} full detail."""

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    icon_name: IconName
    response_style: ResponseStyle
    chat_history: list[ChatMessage] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Chat history message
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    """One entry in the chat history. Mirrors the React `ChatMessage` type."""

    id: str
    sender: Literal["user", "assistant"]
    text: str
    timestamp: int  # milliseconds since epoch (NOT a datetime — Pydantic
    # auto-coerces `int`-typed fields; we keep it as int to match the
    # frontend's `Number(id.split("-")[1])` ordering).

    # Optional assistant-side display fields. Kept optional so a user-side
    # message is `ChatMessage(id=..., sender="user", text=..., timestamp=...)`.
    deadline: DeadlineResult | None = None
    questions: list[str] = Field(default_factory=list)
    step_title: str | None = None
    step_content: str | None = None
    relevant_title: str = ""
    relevant_content: str = ""
    suggestive_text: str | None = None
    template_letter: str | None = None
    template_letter_assunto: str | None = None
    quick_replies: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# PATCH body
# ---------------------------------------------------------------------------


class UpdateCaseRequest(BaseModel):
    """PATCH /api/cases/{id} body.

    At least one of the optional fields MUST be set; the `model_validator`
    below enforces this with a 422 if all are `None`. `extra="forbid"`
    rejects unknown fields with 422.
    """

    model_config = ConfigDict(extra="forbid")

    title: CaseTitle | None = None
    icon_name: IconName | None = None
    response_style: ResponseStyle | None = None

    @model_validator(mode="after")
    def _at_least_one_field_must_be_set(self) -> UpdateCaseRequest:
        if (
            self.title is None
            and self.icon_name is None
            and self.response_style is None
        ):
            raise ValueError(
                "Informe ao menos um campo: title, icon_name ou response_style."
            )
        return self


# ---------------------------------------------------------------------------
# Forward references (ChatMessage is used in StructuredChatResponse/CaseResponse)
# ---------------------------------------------------------------------------

StructuredChatResponse.model_rebuild()
CaseResponse.model_rebuild()


# Re-export for callers that import the envelope aliases from schemas
__all__ = [
    "CaseResponse",
    "CaseSummary",
    "CaseTitle",
    "ChatMessage",
    "IconName",
    "ResponseStyle",
    "StructuredChatRequest",
    "StructuredChatResponse",
    "UpdateCaseRequest",
    # Convenience re-exports for adapters/clients that want both:
    "DeadlineResult",
    "DraftedDocument",
]
