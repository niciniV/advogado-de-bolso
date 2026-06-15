"""FastAPI transport for Advogado de Bolso (batch 4).

Endpoints:
- POST /api/chat/structured (body: StructuredChatRequest) -> StructuredChatResponse
  (200 success / 422 blocked)
- GET /api/cases -> list[CaseSummary]
- GET /api/cases/{case_id} (UUID) -> CaseResponse
- PATCH /api/cases/{case_id} (UUID, body: UpdateCaseRequest) -> CaseResponse
- DELETE /api/cases/{case_id} (UUID) -> 204
- GET /api/cases/{case_id}/history (UUID) -> list[ChatMessage]
- GET /api/health

Static serving mounts /assets if `base_frontend/dist` exists. SPA fallback
excludes /api and /assets via first-segment matching.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Protocol
from uuid import UUID

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from advogado_de_bolso.config import Settings, get_settings
from advogado_de_bolso.schemas import (
    CaseResponse,
    CaseSummary,
    ChatMessage,
    StructuredChatRequest,
    StructuredChatResponse,
    UpdateCaseRequest,
)
from advogado_de_bolso.service import ChatResult, build_chat_service
from advogado_de_bolso.storage.cases import Case

logger = logging.getLogger(__name__)


# `api.py` lives at `<project_root>/src/advogado_de_bolso/api.py`, so:
#   .parent              → .../advogado_de_bolso/
#   .parent.parent       → .../src/
#   .parent.parent.parent → <project_root>
REACT_DIST = Path(__file__).parent.parent.parent / "base_frontend" / "dist"


# ---------------------------------------------------------------------------
# Service contract (Protocol) + dependency
# ---------------------------------------------------------------------------


class ChatServiceContract(Protocol):
    """Subset of `ChatService` the API relies on.

    Declared structurally (duck-typed Protocol) so tests can swap in
    fakes without depending on the concrete `ChatService` class.
    """

    async def chat_structured(
        self,
        message: str,
        session_id: UUID | None = None,
        *,
        response_style: str | None = None,
        title: str | None = None,
        icon_name: str | None = None,
    ) -> ChatResult: ...

    async def list_cases(self) -> list[CaseSummary]: ...

    async def get_case(self, case_id: UUID) -> Case | None: ...

    async def update_case_meta(self, case_id: UUID, **fields: Any) -> Case: ...

    async def delete_case(self, case_id: UUID) -> bool: ...

    async def get_history(self, case_id: UUID) -> list[ChatMessage]: ...


def _get_service(request: Request) -> ChatServiceContract:
    service: ChatServiceContract | None = request.app.state.chat_service
    if service is None:
        raise HTTPException(status_code=503, detail="Servico ainda nao esta pronto.")
    return service


ServiceDependency = Annotated[ChatServiceContract, Depends(_get_service)]


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def _to_case_response(case: Case) -> CaseResponse:
    """Convert the internal `Case` to the wire `CaseResponse` shape.

    Hides `model_history` (LLM-bound, NOT exposed on the wire).
    """
    return CaseResponse(
        id=UUID(case.id),
        title=case.title,
        created_at=case.created_at,
        updated_at=case.updated_at,
        icon_name=case.icon_name,
        response_style=case.response_style,
        chat_history=list(case.chat_history),
    )


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(
    *,
    service: ChatServiceContract | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if app.state.chat_service is None:
            app.state.chat_service = await asyncio.to_thread(
                build_chat_service, app.state.settings
            )
        app.state.ready = True
        yield

    app = FastAPI(
        title="Advogado de Bolso API",
        description="API para orientacao sobre direitos do consumidor brasileiro.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.chat_service = service
    app.state.ready = service is not None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    # -----------------------------------------------------------------------
    # Health
    # -----------------------------------------------------------------------

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        if not app.state.ready:
            raise HTTPException(
                status_code=503, detail="Servico ainda nao esta pronto."
            )
        return {"status": "ok"}

    # -----------------------------------------------------------------------
    # Chat (structured)
    # -----------------------------------------------------------------------

    @app.post("/api/chat/structured", response_model=None)
    async def chat_structured(
        payload: StructuredChatRequest,
        chat_service: ServiceDependency,
    ) -> StructuredChatResponse | JSONResponse:
        try:
            result = await chat_service.chat_structured(
                payload.message,
                payload.session_id,
                response_style=payload.response_style,
                title=payload.title,
                icon_name=payload.icon_name,
            )
        except Exception as exc:
            logger.exception("Falha ao processar uma mensagem da API", exc_info=exc)
            raise HTTPException(
                status_code=503,
                detail=(
                    "Nao foi possivel processar a mensagem agora. Tente novamente."
                ),
            ) from exc

        if result.response.blocked:
            return JSONResponse(
                status_code=422,
                content=result.response.model_dump(mode="json"),
            )
        return result.response

    # -----------------------------------------------------------------------
    # Cases
    # -----------------------------------------------------------------------

    @app.get("/api/cases", response_model=list[CaseSummary])
    async def list_cases(
        chat_service: ServiceDependency,
    ) -> list[CaseSummary]:
        return await chat_service.list_cases()

    @app.get("/api/cases/{case_id}", response_model=CaseResponse)
    async def get_case(
        case_id: UUID,
        chat_service: ServiceDependency,
    ) -> CaseResponse:
        case = await chat_service.get_case(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Caso nao encontrado.")
        return _to_case_response(case)

    @app.patch("/api/cases/{case_id}", response_model=CaseResponse)
    async def patch_case(
        case_id: UUID,
        payload: UpdateCaseRequest,
        chat_service: ServiceDependency,
    ) -> CaseResponse:
        fields = payload.model_dump(exclude_unset=True)
        try:
            case = await chat_service.update_case_meta(case_id, **fields)
        except KeyError:
            raise HTTPException(status_code=404, detail="Caso nao encontrado.") from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _to_case_response(case)

    @app.delete("/api/cases/{case_id}", status_code=204)
    async def delete_case_endpoint(
        case_id: UUID,
        chat_service: ServiceDependency,
    ) -> None:
        deleted = await chat_service.delete_case(case_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Caso nao encontrado.")
        return None

    @app.get("/api/cases/{case_id}/history", response_model=list[ChatMessage])
    async def case_history(
        case_id: UUID,
        chat_service: ServiceDependency,
    ) -> list[ChatMessage]:
        # Empty list for a missing case is acceptable here (a brand new
        # case may legitimately have no history yet), but we also accept
        # 404 for explicit missing-case semantics. The plan / tests pin
        # 404, so we return 404 on missing case.
        case = await chat_service.get_case(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Caso nao encontrado.")
        return await chat_service.get_history(case_id)

    # -----------------------------------------------------------------------
    # Static / SPA fallback
    # -----------------------------------------------------------------------

    if REACT_DIST.exists():
        app.mount(
            "/assets",
            StaticFiles(directory=REACT_DIST / "assets"),
            name="react-assets",
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        first_segment = full_path.split("/", 1)[0] if full_path else ""
        if first_segment in {"api", "assets"}:
            raise HTTPException(status_code=404, detail="Not Found")
        index = REACT_DIST / "index.html"
        if not index.exists():
            raise HTTPException(
                status_code=500,
                detail="Frontend bundle not built. Run `make frontend`.",
            )
        return FileResponse(index)

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "advogado_de_bolso.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
