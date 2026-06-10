from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import patch

from fastapi.testclient import TestClient

from advogado_de_bolso.api import create_app
from advogado_de_bolso.service import ChatReply


@dataclass
class FakeService:
    should_fail: bool = False

    async def chat(self, message: str, session_id: str | None = None) -> ChatReply:
        if self.should_fail:
            raise RuntimeError("secret upstream failure")
        return ChatReply(
            session_id=session_id or "new-session",
            response=f"Resposta para: {message}",
        )

    def clear_session(self, session_id: str) -> bool:
        return session_id == "known-session"


def test_health_endpoint() -> None:
    with TestClient(create_app(service=FakeService())) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_endpoint_returns_response_and_session() -> None:
    with TestClient(create_app(service=FakeService())) as client:
        response = client.post("/api/chat", json={"message": "Quais sao meus direitos?"})

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "new-session",
        "response": "Resposta para: Quais sao meus direitos?",
    }


def test_chat_rejects_blank_message() -> None:
    with TestClient(create_app(service=FakeService())) as client:
        response = client.post("/api/chat", json={"message": "   "})

    assert response.status_code == 422


def test_chat_hides_runtime_error_details() -> None:
    with TestClient(create_app(service=FakeService(should_fail=True))) as client:
        response = client.post("/api/chat", json={"message": "Pergunta"})

    assert response.status_code == 503
    assert "secret upstream failure" not in response.text


def test_clear_session_reports_if_it_existed() -> None:
    with TestClient(create_app(service=FakeService())) as client:
        known = client.delete("/api/sessions/known-session")
        unknown = client.delete("/api/sessions/unknown-session")

    assert known.json() == {"cleared": True}
    assert unknown.json() == {"cleared": False}


def test_reference_frontend_and_assets_are_served() -> None:
    with TestClient(create_app(service=FakeService())) as client:
        page = client.get("/")
        styles = client.get("/assets/styles.css")
        script = client.get("/assets/app.js")

    assert page.status_code == 200
    assert "Advogado de Bolso" in page.text
    assert "text/html" in page.headers["content-type"]
    assert styles.status_code == 200
    assert "text/css" in styles.headers["content-type"]
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]


def test_default_app_initializes_service_once_at_startup() -> None:
    built_service = FakeService()

    with (
        patch(
            "advogado_de_bolso.api.build_chat_service",
            side_effect=lambda settings: built_service,
        ) as build,
        TestClient(create_app()) as client,
    ):
        responses = asyncio.run(_parallel_health_requests(client))

    assert all(response.status_code == 200 for response in responses)
    build.assert_called_once()


async def _parallel_health_requests(client: TestClient):
    return await asyncio.gather(
        *[asyncio.to_thread(client.get, "/api/health") for _ in range(4)]
    )
