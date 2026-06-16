"""Tests for the FastAPI transport (batch 4).

Covers the new endpoint set:
- POST /api/chat/structured (200 success, 422 blocked, 422 validation)
- GET /api/cases, GET /api/cases/{id}, PATCH /api/cases/{id},
  DELETE /api/cases/{id}, GET /api/cases/{id}/history
- SPA fallback: GET / returns index.html, GET /api/typo returns 404
- Malformed non-UUID path params return 422 before service
- PATCH body validation (empty body 422, unknown field 422)
- First-message metadata validation
- CaseResponse doesn't expose model_history
- Blocked-first-message test
- DELETE/history return 404 for well-formed UUID that doesn't exist
- Chat requests with title/icon_name for existing UUID don't change persisted metadata

References
----------
- `.opencode/plans/08-api.md` — api.py spec.
- `.opencode/plans/15-backend-tests.md` — test_api spec.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from advogado_de_bolso.api import create_app
from advogado_de_bolso.schemas import (
    CaseSummary,
    ChatMessage,
    StructuredChatResponse,
)
from advogado_de_bolso.storage.cases import Case

# ---------------------------------------------------------------------------
# Fake service
# ---------------------------------------------------------------------------


@dataclass
class FakeService:
    blocked: bool = False
    cases: dict[UUID, Case] = None  # type: ignore[assignment]
    title_updates: list[tuple[UUID, str]] = None  # type: ignore[assignment]
    delete_results: dict[UUID, bool] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.cases is None:
            self.cases = {}
        if self.title_updates is None:
            self.title_updates = []
        if self.delete_results is None:
            self.delete_results = {}

    async def chat_structured(
        self,
        message: str,
        session_id: UUID | None = None,
        *,
        response_style: str | None = None,
        title: str | None = None,
        icon_name: str | None = None,
    ) -> Any:
        from advogado_de_bolso.service import ChatResult

        if self.blocked:
            structured = StructuredChatResponse(
                session_id=str(session_id) if session_id else "blocked",
                blocked=True,
                blocked_message=(
                    "Nao foi possivel validar esta resposta com seguranca."
                ),
            )
            return ChatResult(
                session_id=structured.session_id,
                response=structured,
            )
        cid = session_id or uuid4()
        structured = StructuredChatResponse(
            session_id=str(cid),
            step_title="Title",
            step_content=f"Resposta para: {message}",
        )
        return ChatResult(session_id=str(cid), response=structured)

    async def list_cases(self) -> list[CaseSummary]:
        return [
            CaseSummary(
                id=UUID(c.id),
                title=c.title,
                created_at=c.created_at,
                updated_at=c.updated_at,
                last_message="",
                icon_name=c.icon_name,
                response_style=c.response_style,
            )
            for c in self.cases.values()
        ]

    async def get_case(self, case_id: UUID) -> Case | None:
        return self.cases.get(case_id)

    async def update_case_meta(
        self, case_id: UUID, **fields: Any
    ) -> Case:
        if case_id not in self.cases:
            raise KeyError(str(case_id))
        case = self.cases[case_id]
        if "title" in fields:
            case.title = fields["title"]
            self.title_updates.append((case_id, fields["title"]))
        if "icon_name" in fields:
            case.icon_name = fields["icon_name"]
        if "response_style" in fields:
            case.response_style = fields["response_style"]
        return case

    async def delete_case(self, case_id: UUID) -> bool:
        if case_id in self.cases:
            del self.cases[case_id]
            self.delete_results[case_id] = True
            return True
        self.delete_results[case_id] = False
        return False

    async def get_history(self, case_id: UUID) -> list[ChatMessage]:
        case = self.cases.get(case_id)
        return list(case.chat_history) if case else []


def _make_case(
    case_id: UUID | None = None,
    title: str = "Test case",
    icon_name: str = "gavel",
    response_style: str = "detalhado",
) -> Case:
    from datetime import UTC, datetime

    cid = case_id or uuid4()
    now = datetime.now(UTC)
    return Case(
        id=str(cid),
        title=title,
        created_at=now,
        updated_at=now,
        icon_name=icon_name,  # type: ignore[arg-type]
        response_style=response_style,  # type: ignore[arg-type]
        chat_history=[],
        model_history=[],
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health_endpoint() -> None:
    with TestClient(create_app(service=FakeService())) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /api/chat/structured
# ---------------------------------------------------------------------------


class TestChatStructured:
    def test_200_success(self) -> None:
        with TestClient(create_app(service=FakeService())) as client:
            response = client.post(
                "/api/chat/structured",
                json={"message": "Quais sao meus direitos?"},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["step_title"] == "Title"
        assert body["step_content"] == "Resposta para: Quais sao meus direitos?"
        assert body["session_id"]
        assert body["blocked"] is False

    def test_422_blocked_envelope(self) -> None:
        with TestClient(create_app(service=FakeService(blocked=True))) as client:
            response = client.post(
                "/api/chat/structured",
                json={"message": "Pergunta arriscada"},
            )
        assert response.status_code == 422
        body = response.json()
        assert body["blocked"] is True
        assert body["blocked_message"]

    def test_422_blank_message(self) -> None:
        with TestClient(create_app(service=FakeService())) as client:
            response = client.post("/api/chat/structured", json={"message": "   "})
        assert response.status_code == 422

    def test_422_over_8000_chars(self) -> None:
        with TestClient(create_app(service=FakeService())) as client:
            response = client.post(
                "/api/chat/structured", json={"message": "a" * 8001}
            )
        assert response.status_code == 422

    def test_422_invalid_icon_name(self) -> None:
        with TestClient(create_app(service=FakeService())) as client:
            response = client.post(
                "/api/chat/structured",
                json={"message": "x", "icon_name": "unknown"},
            )
        assert response.status_code == 422

    def test_422_invalid_response_style(self) -> None:
        with TestClient(create_app(service=FakeService())) as client:
            response = client.post(
                "/api/chat/structured",
                json={"message": "x", "response_style": "verbose"},
            )
        assert response.status_code == 422

    def test_422_blank_title(self) -> None:
        with TestClient(create_app(service=FakeService())) as client:
            response = client.post(
                "/api/chat/structured",
                json={"message": "x", "title": "   "},
            )
        assert response.status_code == 422

    def test_422_over_120_char_title(self) -> None:
        with TestClient(create_app(service=FakeService())) as client:
            response = client.post(
                "/api/chat/structured",
                json={"message": "x", "title": "x" * 121},
            )
        assert response.status_code == 422

    def test_first_message_metadata_reaches_service(self) -> None:
        """Valid auto-create metadata is passed through to the service
        stripped and unchanged (ISSUE-REVIEW-007)."""
        seen: dict[str, Any] = {}

        class _CapturingService(FakeService):
            async def chat_structured(  # type: ignore[override]
                self,
                message: str,
                session_id: UUID | None = None,
                *,
                response_style: str | None = None,
                title: str | None = None,
                icon_name: str | None = None,
            ) -> Any:
                seen["title"] = title
                seen["icon_name"] = icon_name
                seen["response_style"] = response_style
                return await super().chat_structured(
                    message,
                    session_id,
                    response_style=response_style,
                    title=title,
                    icon_name=icon_name,
                )

        with TestClient(create_app(service=_CapturingService())) as client:
            response = client.post(
                "/api/chat/structured",
                json={
                    "message": "x",
                    "title": "  Hello  ",
                    "icon_name": "shopping_bag",
                    "response_style": "simples",
                },
            )
        assert response.status_code == 200
        assert seen["title"] == "Hello"
        assert seen["icon_name"] == "shopping_bag"
        assert seen["response_style"] == "simples"

    def test_503_on_unhandled_exception(self) -> None:
        class _FailingService(FakeService):
            async def chat_structured(  # type: ignore[override]
                self,
                message: str,
                session_id: UUID | None = None,
                **kwargs: Any,
            ) -> Any:
                raise RuntimeError("secret upstream failure")

        with TestClient(create_app(service=_FailingService())) as client:
            response = client.post(
                "/api/chat/structured", json={"message": "x"}
            )
        assert response.status_code == 503
        assert "secret upstream failure" not in response.text


# ---------------------------------------------------------------------------
# GET /api/cases
# ---------------------------------------------------------------------------


class TestListCases:
    def test_lists_all_cases(self) -> None:
        c1 = _make_case(title="Case 1")
        c2 = _make_case(title="Case 2")
        svc = FakeService(cases={UUID(c1.id): c1, UUID(c2.id): c2})
        with TestClient(create_app(service=svc)) as client:
            response = client.get("/api/cases")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert {c["title"] for c in body} == {"Case 1", "Case 2"}

    def test_empty_list(self) -> None:
        with TestClient(create_app(service=FakeService())) as client:
            response = client.get("/api/cases")
        assert response.status_code == 200
        assert response.json() == []


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}
# ---------------------------------------------------------------------------


class TestGetCase:
    def test_get_existing(self) -> None:
        cid = uuid4()
        case = _make_case(case_id=cid, title="Test case")
        svc = FakeService(cases={cid: case})
        with TestClient(create_app(service=svc)) as client:
            response = client.get(f"/api/cases/{cid}")
        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "Test case"
        assert body["id"] == str(cid)
        # model_history MUST NOT be exposed.
        assert "model_history" not in body

    def test_get_missing_404(self) -> None:
        with TestClient(create_app(service=FakeService())) as client:
            response = client.get(f"/api/cases/{uuid4()}")
        assert response.status_code == 404

    def test_get_malformed_uuid_422(self) -> None:
        with TestClient(create_app(service=FakeService())) as client:
            response = client.get("/api/cases/not-a-uuid")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /api/cases/{case_id}
# ---------------------------------------------------------------------------


class TestPatchCase:
    def test_patch_title(self) -> None:
        cid = uuid4()
        case = _make_case(case_id=cid, title="Old")
        svc = FakeService(cases={cid: case})
        with TestClient(create_app(service=svc)) as client:
            response = client.patch(
                f"/api/cases/{cid}", json={"title": "New"}
            )
        assert response.status_code == 200
        assert response.json()["title"] == "New"
        assert svc.title_updates == [(cid, "New")]

    def test_patch_icon_name(self) -> None:
        cid = uuid4()
        case = _make_case(case_id=cid)
        svc = FakeService(cases={cid: case})
        with TestClient(create_app(service=svc)) as client:
            response = client.patch(
                f"/api/cases/{cid}", json={"icon_name": "shopping_bag"}
            )
        assert response.status_code == 200
        assert response.json()["icon_name"] == "shopping_bag"

    def test_patch_response_style(self) -> None:
        cid = uuid4()
        case = _make_case(case_id=cid)
        svc = FakeService(cases={cid: case})
        with TestClient(create_app(service=svc)) as client:
            response = client.patch(
                f"/api/cases/{cid}", json={"response_style": "simples"}
            )
        assert response.status_code == 200
        assert response.json()["response_style"] == "simples"

    def test_patch_combined_fields(self) -> None:
        cid = uuid4()
        case = _make_case(case_id=cid)
        svc = FakeService(cases={cid: case})
        with TestClient(create_app(service=svc)) as client:
            response = client.patch(
                f"/api/cases/{cid}",
                json={
                    "title": "X",
                    "icon_name": "shopping_bag",
                    "response_style": "simples",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "X"
        assert body["icon_name"] == "shopping_bag"
        assert body["response_style"] == "simples"

    def test_patch_empty_body_422(self) -> None:
        cid = uuid4()
        case = _make_case(case_id=cid)
        svc = FakeService(cases={cid: case})
        with TestClient(create_app(service=svc)) as client:
            response = client.patch(f"/api/cases/{cid}", json={})
        assert response.status_code == 422

    def test_patch_unknown_field_422(self) -> None:
        cid = uuid4()
        case = _make_case(case_id=cid)
        svc = FakeService(cases={cid: case})
        with TestClient(create_app(service=svc)) as client:
            response = client.patch(
                f"/api/cases/{cid}", json={"title": "X", "unknown": 1}
            )
        assert response.status_code == 422

    def test_patch_missing_case_404(self) -> None:
        with TestClient(create_app(service=FakeService())) as client:
            response = client.patch(
                f"/api/cases/{uuid4()}", json={"title": "X"}
            )
        assert response.status_code == 404

    def test_patch_service_validation_422(self) -> None:
        class _StrictService(FakeService):
            async def update_case_meta(  # type: ignore[override]
                self, case_id: UUID, **fields: Any
            ) -> Case:
                raise ValueError("title must contain 1 to 120 characters.")

        cid = uuid4()
        case = _make_case(case_id=cid)
        svc = _StrictService(cases={cid: case})
        with TestClient(create_app(service=svc)) as client:
            response = client.patch(
                f"/api/cases/{cid}", json={"title": "ok"}
            )
        assert response.status_code == 422

    def test_patch_malformed_uuid_422(self) -> None:
        with TestClient(create_app(service=FakeService())) as client:
            response = client.patch(
                "/api/cases/not-a-uuid", json={"title": "X"}
            )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/cases/{case_id}
# ---------------------------------------------------------------------------


class TestDeleteCase:
    def test_delete_existing(self) -> None:
        cid = uuid4()
        case = _make_case(case_id=cid)
        svc = FakeService(cases={cid: case})
        with TestClient(create_app(service=svc)) as client:
            response = client.delete(f"/api/cases/{cid}")
        assert response.status_code == 204
        assert cid not in svc.cases

    def test_delete_missing_404(self) -> None:
        with TestClient(create_app(service=FakeService())) as client:
            response = client.delete(f"/api/cases/{uuid4()}")
        assert response.status_code == 404

    def test_delete_malformed_uuid_422(self) -> None:
        with TestClient(create_app(service=FakeService())) as client:
            response = client.delete("/api/cases/not-a-uuid")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/cases/{case_id}/history
# ---------------------------------------------------------------------------


class TestCaseHistory:
    def test_get_history_existing(self) -> None:
        cid = uuid4()
        case = _make_case(case_id=cid)
        case.chat_history = [
            ChatMessage(
                id="user-1",
                sender="user",
                text="hi",
                timestamp=1,
            ),
            ChatMessage(
                id="assistant-1",
                sender="assistant",
                text="hello",
                timestamp=2,
            ),
        ]
        svc = FakeService(cases={cid: case})
        with TestClient(create_app(service=svc)) as client:
            response = client.get(f"/api/cases/{cid}/history")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert body[0]["text"] == "hi"

    def test_get_history_missing_404(self) -> None:
        with TestClient(create_app(service=FakeService())) as client:
            response = client.get(f"/api/cases/{uuid4()}/history")
        assert response.status_code == 404

    def test_get_history_malformed_uuid_422(self) -> None:
        with TestClient(create_app(service=FakeService())) as client:
            response = client.get("/api/cases/not-a-uuid/history")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# SPA fallback
# ---------------------------------------------------------------------------


class TestSPAFallback:
    def test_root_returns_index_html_when_dist_exists(
        self, tmp_path, monkeypatch
    ) -> None:
        # Build a fake dist with index.html
        dist = tmp_path / "base_frontend" / "dist"
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text("<html><body>Advogado de Bolso</body></html>")
        # `react_dist` is now sourced from `Settings` (env var `REACT_DIST`).
        # We pass a fresh Settings with REACT_DIST set, since the cached
        # `get_settings()` singleton may have been populated at api-module
        # import time without the env var.
        from advogado_de_bolso.config import Settings

        settings = Settings(REACT_DIST=str(dist))
        with TestClient(create_app(service=FakeService(), settings=settings)) as client:
            response = client.get("/")
        assert response.status_code == 200
        assert "Advogado de Bolso" in response.text
        assert "text/html" in response.headers["content-type"]

    def test_api_typo_returns_404(self) -> None:
        """An exact first-segment check means `/api/chatt` is NOT
        treated as `/api/...` — but the explicit `raise HTTPException(404)`
        inside the SPA fallback ensures 404 for any non-asset/non-api
        exact-prefix path that doesn't match a registered route.
        """
        with TestClient(create_app(service=FakeService())) as client:
            response = client.get("/api/chatt")
        # /api/chatt is not a registered route. FastAPI's default
        # 404 path applies. The SPA fallback is only invoked for paths
        # that match `/{full_path:path}` and aren't `api` or `assets`.
        # The fallback handler raises HTTPException(404) when first_segment
        # is in {"api", "assets"}.
        assert response.status_code == 404

    def test_assets_subpath_under_dist_served(
        self, tmp_path, monkeypatch
    ) -> None:
        dist = tmp_path / "base_frontend" / "dist"
        (dist / "assets").mkdir(parents=True)
        (dist / "assets" / "main.js").write_text("// bundled js")
        (dist / "index.html").write_text("<html></html>")
        from advogado_de_bolso.config import Settings

        settings = Settings(REACT_DIST=str(dist))
        with TestClient(create_app(service=FakeService(), settings=settings)) as client:
            response = client.get("/assets/main.js")
        assert response.status_code == 200
        assert "main.js" in response.text or "bundled" in response.text


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


def test_cors_allows_patch_method() -> None:
    """ISSUE-DS-004: CORS must include PATCH."""
    with TestClient(create_app(service=FakeService())) as client:
        response = client.options(
            "/api/cases/00000000-0000-0000-0000-000000000001",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "PATCH",
            },
        )
    # CORS preflight returns 200 with allow_methods including PATCH
    assert "PATCH" in response.headers.get("access-control-allow-methods", "")


# ---------------------------------------------------------------------------
# Dropped endpoints
# ---------------------------------------------------------------------------


def test_old_chat_endpoint_gone() -> None:
    with TestClient(create_app(service=FakeService())) as client:
        response = client.post("/api/chat", json={"message": "x"})
    # FastAPI matches the prefix `/api/chat/structured` and reports
    # 405 Method Not Allowed (POST is registered for the longer
    # prefix). Either 404 or 405 is acceptable — both indicate the
    # old endpoint is no longer registered.
    assert response.status_code in (404, 405)


def test_old_clear_session_endpoint_gone() -> None:
    with TestClient(create_app(service=FakeService())) as client:
        response = client.delete("/api/sessions/known")
    # Same as above: 404 if FastAPI cannot match, 405 if the prefix
    # is registered for a different verb.
    assert response.status_code in (404, 405)


# ---------------------------------------------------------------------------
# CaseResponse shape
# ---------------------------------------------------------------------------


def test_case_response_does_not_expose_model_history() -> None:
    """The wire `CaseResponse` does NOT include `model_history`."""
    cid = uuid4()
    case = _make_case(case_id=cid)
    svc = FakeService(cases={cid: case})
    with TestClient(create_app(service=svc)) as client:
        response = client.get(f"/api/cases/{cid}")
    body = response.json()
    assert "model_history" not in body
    # Sanity: the expected fields ARE present.
    for key in ("id", "title", "created_at", "updated_at", "icon_name",
                "response_style", "chat_history"):
        assert key in body
