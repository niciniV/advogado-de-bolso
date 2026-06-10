"""FastAPI transport and reference frontend for Advogado de Bolso."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Protocol

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from advogado_de_bolso.config import Settings, get_settings
from advogado_de_bolso.service import ChatReply, build_chat_service

logger = logging.getLogger(__name__)
FRONTEND_DIR = Path(__file__).with_name("frontend")


class ChatServiceContract(Protocol):
    async def chat(self, message: str, session_id: str | None = None) -> ChatReply: ...

    def clear_session(self, session_id: str) -> bool: ...


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8_000)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("message")
    @classmethod
    def _message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A mensagem nao pode estar vazia.")
        return value


class ChatResponse(BaseModel):
    session_id: str
    response: str


class ClearSessionResponse(BaseModel):
    cleared: bool


def _get_service(request: Request) -> ChatServiceContract:
    service: ChatServiceContract | None = request.app.state.chat_service
    if service is None:
        raise HTTPException(status_code=503, detail="Servico ainda nao esta pronto.")
    return service


ServiceDependency = Annotated[ChatServiceContract, Depends(_get_service)]


def create_app(
    *,
    service: ChatServiceContract | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if app.state.chat_service is None:
            app.state.chat_service = await asyncio.to_thread(build_chat_service, app.state.settings)
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
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        if not app.state.ready:
            raise HTTPException(status_code=503, detail="Servico ainda nao esta pronto.")
        return {"status": "ok"}

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest, chat_service: ServiceDependency) -> ChatResponse:
        try:
            reply = await chat_service.chat(payload.message, payload.session_id)
        except Exception as exc:
            logger.exception("Falha ao processar uma mensagem da API", exc_info=exc)
            raise HTTPException(
                status_code=503,
                detail="Nao foi possivel processar a mensagem agora. Tente novamente.",
            ) from exc
        return ChatResponse(session_id=reply.session_id, response=reply.response)

    @app.delete("/api/sessions/{session_id}", response_model=ClearSessionResponse)
    async def clear_session(session_id: str, chat_service: ServiceDependency) -> ClearSessionResponse:
        return ClearSessionResponse(cleared=chat_service.clear_session(session_id))

    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")

    @app.get("/", include_in_schema=False)
    async def frontend() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

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
