# Integration Plan: React Frontend → Python FastAPI Backend

## Executive Summary

Merge the React frontend (`base_frontend/`) into the Python FastAPI backend (`src/advogado_de_bolso/`) so the rich React UI is powered by the superior Python agent (RAG + deadline calculation + document drafting tools).

**Recommended approach:** Adapter endpoint + single-server architecture.

---

## Architecture

### Development Mode
```
┌─────────────────────────────────────────────┐
│  Vite Dev Server (port 5173)                │
│  ┌───────────────┐  ┌──────────────────┐    │
│  │ React SPA     │  │ /api/* proxy ────────►│──► FastAPI (port 8000)
│  │ (HMR enabled) │  └──────────────────┘    │
│  └───────────────┘                          │
└─────────────────────────────────────────────┘
```

### Production Mode
```
┌─────────────────────────────────────────────┐
│  FastAPI (port 8000)                        │
│  ┌───────────────┐  ┌──────────────────┐    │
│  │ React SPA     │  │ /api/chat        │    │
│  │ (static files)│  │ (adapter endpoint)│    │
│  └───────────────┘  └──────────────────┘    │
└─────────────────────────────────────────────┘
```

---

## Approach Analysis

### Why This Approach (Adapter + Single Server)

| Option | Verdict | Reason |
|--------|---------|--------|
| **A. Modify Python agent to return structured JSON** | ❌ Rejected | Breaks Pydantic AI tool calling; requires agent `output_type` change; fragile |
| **B. Adapter endpoint (recommended)** | ✅ Selected | Minimal changes to both codebases; preserves agent behavior; preserves React UI |
| **C. Modify React to accept plain text** | ❌ Rejected | Loses rich UI features; defeats the purpose of integration |
| **D. Keep Express, proxy to Python** | ❌ Rejected | Two servers; Express's /api/chat logic conflicts; unnecessary complexity |

---

## Step-by-Step Implementation Plan

### Phase 1: Python Backend — Structured Response Adapter

**Goal:** Add an endpoint that returns structured JSON matching React's expected format.

#### Step 1.1: Create `src/advogado_de_bolso/adapter.py`

New file that post-processes the agent's response into structured JSON.

```python
# adapter.py — Post-processor that extracts structured data from agent tool calls

@dataclass(frozen=True)
class StructuredReply:
    session_id: str
    step_title: str
    step_content: str
    relevant_title: str
    relevant_content: str
    calc_performed: bool
    deadline: dict | None
    questions: list[str]
    suggestive_text: str
    template_letter: str | None
    quick_replies: list[str]
```

**Key logic:**
1. After the agent runs, inspect `result.all_messages()` for `ToolCallPart` and `ToolReturnPart`
2. When `calcular_prazo_consumidor` tool was called:
   - Parse the return text to extract: start date, end date, days, legal basis
   - Build the `deadline` object
   - Set `calc_performed = True`
3. When `redigir_documento` tool was called:
   - The tool's return value IS the template letter
   - Set `template_letter` to the tool output
4. When `search_knowledge_base` tool was called:
   - Extract the first relevant chunk as `relevant_content`
   - Extract the source as `relevant_title`
5. The agent's `result.output` becomes `step_content`
6. Generate `step_title` from the response (e.g., "Análise do caso" or extract from first sentence)
7. Generate `questions` by asking the agent for follow-up questions (or use a simple heuristic)
8. Generate `quick_replies` based on what tools were used:
   - If deadline calculated → ["Preparar mensagem", "Recalcular prazo", "Continuar orientação"]
   - If document drafted → ["Copiar mensagem", "Refazer com outro tom", "Fazer outra pergunta"]
   - Default → ["Continuar orientação", "Fazer outra pergunta"]

**Tool call extraction pattern (Pydantic AI):**
```python
from pydantic_ai.messages import ModelMessage, ToolCallPart, ToolReturnPart

def extract_tool_data(messages: list[ModelMessage]) -> dict:
    tools_called = {}
    for msg in messages:
        if hasattr(msg, 'parts'):
            for part in msg.parts:
                if isinstance(part, ToolCallPart) and part.tool_name in _TOOL_EXTRACTORS:
                    tools_called[part.tool_name] = part.args
                if isinstance(part, ToolReturnPart) and part.tool_name in _TOOL_EXTRACTORS:
                    tools_called[f"{part.tool_name}_result"] = part.content
    return tools_called
```

**Deadline parsing from tool text:**
```python
# Tool returns: "Pelo CDC art. 26, o prazo estimado para reclamar de vicio em
# produto duravel e de 90 dias. Usando como data inicial 2026-01-15,
# a data limite estimada e 2026-04-15."

# Parse to extract:
# - type: "Reclamacao por Vicio - Art. 26 CDC"
# - start_date: "2026-01-15"
# - end_date: "2026-04-15"
# - base: "CDC Artigo 26 (90 dias para produtos duraveis)"
```

#### Step 1.2: Modify `src/advogado_de_bolso/service.py`

Add a new method to `AgentChatBackend` that returns structured data:

```python
class AgentChatBackend:
    async def run_structured(
        self, message: str, history: list[ModelMessage]
    ) -> tuple[StructuredReply, list[ModelMessage]]:
        result = await self._agent.run(message, deps=self._deps, message_history=history)
        revision = await self._reviewer(message, result.output)
        if not revision.approved_as_is:
            return _blocked_structured_reply(), history
        
        structured = extract_structured_response(result)
        return structured, result.all_messages()
```

Also update `ChatService` to have a `chat_structured()` method that mirrors `chat()` but returns `StructuredReply`.

#### Step 1.3: Modify `src/advogado_de_bolso/api.py`

Add a new endpoint and update request/response models:

**New request model:**
```python
class StructuredChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8_000)
    session_id: str | None = None
    response_style: str | None = Field(default=None)  # 'simples'|'detalhado'|'firme'
```

**New response model:**
```python
class StructuredChatResponse(BaseModel):
    session_id: str
    step_title: str
    step_content: str
    relevant_title: str
    relevant_content: str
    calc_performed: bool
    deadline: dict | None = None
    questions: list[str] = []
    suggestive_text: str = ""
    template_letter: str | None = None
    quick_replies: list[str] = []
```

**New endpoint:**
```python
@app.post("/api/chat/structured", response_model=StructuredChatResponse)
async def chat_structured(payload: StructuredChatRequest, chat_service: ServiceDependency):
    reply = await chat_service.chat_structured(
        payload.message, payload.session_id, payload.response_style
    )
    return StructuredChatResponse(...)
```

**Keep the existing `/api/chat` endpoint** for backward compatibility with the vanilla frontend.

#### Step 1.4: Serve React Static Files

Update `src/advogado_de_bolso/api.py` to serve the built React app:

```python
REACT_DIST_DIR = Path(__file__).parent.parent.parent.parent / "base_frontend" / "dist"

# In create_app():
# Serve React static assets
if REACT_DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=REACT_DIST_DIR / "assets"), name="react-assets")

# Catch-all for SPA routing (must be last)
@app.get("/{path:path}", include_in_schema=False)
async def react_spa(path: str):
    file = REACT_DIST_DIR / path
    if file.is_file():
        return FileResponse(file)
    return FileResponse(REACT_DIST_DIR / "index.html")
```

---

### Phase 2: React Frontend — Adapt to Python Backend

**Goal:** Modify the React frontend to call the Python backend instead of Express/Gemini.

#### Step 2.1: Modify `base_frontend/src/App.tsx`

**Change the API call in `handleSendMessage`:**

```typescript
// BEFORE (calls Express server):
const response = await fetch("/api/chat", {
  method: "POST",
  body: JSON.stringify({
    message: text,
    history: updatedHistory,
    responseStyle: preferences.responseStyle
  })
});
const resData = await response.json();
// Maps: stepTitle, stepContent, relevantTitle, etc.

// AFTER (calls Python backend):
const response = await fetch("/api/chat/structured", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    message: text,
    session_id: sessionId,  // stored in state
    response_style: preferences.responseStyle
  })
});
const resData = await response.json();

// Store session_id for subsequent requests
if (resData.session_id && !sessionId) {
  setSessionId(resData.session_id);
}
```

**Add session_id state:**
```typescript
const [sessionId, setSessionId] = useState<string | null>(null);
```

**Handle new response format** (snake_case from Python → camelCase for React):
```typescript
const botMsg: ChatMessage = {
  id: `bot-msg-${Date.now()}`,
  sender: "assistant",
  text: resData.step_content || resData.stepContent || "Consulta processada.",
  timestamp: Date.now(),
  stepTitle: resData.step_title || resData.stepTitle,
  stepContent: resData.step_content || resData.stepContent,
  relevantTitle: resData.relevant_title || resData.relevantTitle,
  relevantContent: resData.relevant_content || resData.relevantContent,
  deadline: resData.deadline,
  questions: resData.questions,
  suggestiveText: resData.suggestive_text || resData.suggestiveText,
  templateLetter: resData.template_letter || resData.templateLetter,
  quickReplies: resData.quick_replies || resData.quickReplies
};
```

**Update the clear/reset handler:**
```typescript
const handleClearChat = () => {
  if (sessionId) {
    fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
  }
  setSessionId(null);
  setCurrentChatHistory([]);
  setActiveCaseId(null);
};
```

#### Step 2.2: Update `base_frontend/vite.config.ts`

Add proxy for development:

```typescript
export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: { alias: { '@': path.resolve(__dirname, '.') } },
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
      hmr: process.env.DISABLE_HMR !== 'true',
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
    },
  };
});
```

#### Step 2.3: Remove Express Server Dependency (Optional)

The `server.ts` file can be kept for standalone development but is no longer needed for the integrated version. For the integrated build:

- Update `package.json` scripts to just use Vite:
  ```json
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }
  ```

- Remove `@google/genai`, `express`, `dotenv` from dependencies (if not needed for standalone mode)

---

### Phase 3: Integration Wiring

#### Step 3.1: Update Build Process

**Add build script to root `pyproject.toml` or `Makefile`:**
```makefile
build-frontend:
    cd base_frontend && npm install && npm run build
    cp -r dist/* src/advogado_de_bolso/frontend_react/

run:
    python -m advogado_de_bolso api
```

Or add to `package.json`:
```json
"scripts": {
  "build:integration": "vite build && cp -r dist ../src/advogado_de_bolso/frontend_react/"
}
```

#### Step 3.2: Update `src/advogado_de_bolso/api.py` Static File Serving

```python
REACT_DIST = Path(__file__).parent / "frontend_react"

# Mount React assets
if REACT_DIST.exists():
    app.mount("/react-assets", StaticFiles(directory=REACT_DIST), name="react")
```

#### Step 3.3: Route Priority

The existing vanilla frontend is served at `/`. For the React integration:
- Serve React at `/` (replaces vanilla frontend)
- Keep `/api/chat` (plain text) for backward compatibility
- Add `/api/chat/structured` for React
- Keep `/api/health` and `/api/sessions/{id}`

---

## Files to Modify

### Python Backend
| File | Action | Changes |
|------|--------|---------|
| `src/advogado_de_bolso/adapter.py` | **CREATE** | Structured response extractor |
| `src/advogado_de_bolso/service.py` | MODIFY | Add `chat_structured()` method, `run_structured()` to `AgentChatBackend` |
| `src/advogado_de_bolso/api.py` | MODIFY | Add `/api/chat/structured` endpoint, React static file serving, new request/response models |

### React Frontend
| File | Action | Changes |
|------|--------|---------|
| `base_frontend/src/App.tsx` | MODIFY | Change API endpoint, add session_id state, handle snake_case response |
| `base_frontend/vite.config.ts` | MODIFY | Add dev proxy to Python backend |
| `base_frontend/package.json` | MODIFY | Update scripts for integration build |

### New Files
| File | Purpose |
|------|---------|
| `src/advogado_de_bolso/adapter.py` | Extracts structured data from agent tool calls |

---

## Detailed Adapter Design (`adapter.py`)

The adapter is the critical bridge. Here's the detailed design:

```python
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)

# Tool names used by the agent
TOOL_CALCULAR_PRAZO = "calcular_prazo_consumidor"
TOOL_REDIGIR_DOCUMENTO = "redigir_documento"
TOOL_SEARCH_KB = "search_knowledge_base"


@dataclass(frozen=True)
class StructuredReply:
    session_id: str
    step_title: str
    step_content: str
    relevant_title: str
    relevant_content: str
    calc_performed: bool
    deadline: dict | None
    questions: list[str]
    suggestive_text: str
    template_letter: str | None
    quick_replies: list[str]


def _extract_tool_calls(messages: list[ModelMessage]) -> dict[str, str]:
    """Extract tool names and their return values from message history."""
    tools = {}
    for msg in messages:
        if not hasattr(msg, "parts"):
            continue
        for part in msg.parts:
            if isinstance(part, ToolReturnPart):
                tools[part.tool_name] = part.content
            elif isinstance(part, ToolCallPart):
                tools[f"{part.tool_name}_args"] = str(part.args)
    return tools


def _parse_deadline_from_tool(tool_text: str) -> dict | None:
    """Parse deadline data from calcular_prazo_consumidor output."""
    # Extract dates: "data inicial 2026-01-15" and "data limite estimada e 2026-04-15"
    start_match = re.search(r"data inicial (\d{4}-\d{2}-\d{2})", tool_text)
    end_match = re.search(r"data limite estimada e (\d{4}-\d{2}-\d{2})", tool_text)
    
    if not start_match or not end_match:
        return None
    
    start_date = start_match.group(1)
    end_date = end_match.group(1)
    
    # Extract legal basis
    art_match = re.search(r"CDC art\. (\d+)", tool_text)
    days_match = re.search(r"de (\d+) dias", tool_text)
    
    artigo = art_match.group(1) if art_match else "?"
    dias = days_match.group(1) if days_match else "?"
    
    return {
        "title": f"Prazo calculado (Art. {artigo} CDC)",
        "type": f"Reclamacao - Art. {artigo} CDC",
        "startDate": f"{start_date} (data informada)",
        "endDate": end_date,
        "base": f"CDC Artigo {artigo} ({dias} dias)",
        "note": "Confirme a data inicial correta conforme os fatos."
    }


def build_structured_reply(
    *,
    session_id: str,
    agent_output: str,
    messages: list[ModelMessage],
) -> StructuredReply:
    """Build a StructuredReply from agent output and message history."""
    tools = _extract_tool_calls(messages)
    
    # Deadline
    deadline = None
    calc_performed = False
    if TOOL_CALCULAR_PRAZO in tools:
        deadline = _parse_deadline_from_tool(tools[TOOL_CALCULAR_PRAZO])
        calc_performed = deadline is not None
    
    # Template letter
    template_letter = tools.get(TOOL_REDIGIR_DOCUMENTO)
    
    # Relevant content from KB
    relevant_title = "Fundamentacao Legal"
    relevant_content = ""
    if TOOL_SEARCH_KB in tools:
        kb_text = tools[TOOL_SEARCH_KB]
        # Extract first chunk
        chunks = kb_text.split("---")
        if chunks:
            first_chunk = chunks[0].strip()
            # Remove "[1] Fonte: ..." prefix
            source_match = re.search(r"Fonte: (.+)", first_chunk)
            if source_match:
                relevant_title = f"Fonte: {source_match.group(1)}"
            relevant_content = re.sub(r"\[\d+\]\s*Fonte: .+\n?", "", first_chunk).strip()
    
    # Step title from agent output
    step_title = "Analise do Caso"
    first_line = agent_output.split("\n")[0]
    if len(first_line) < 80:
        step_title = first_line.strip()
    
    # Questions (extract from agent output or generate defaults)
    questions = []
    q_patterns = re.findall(r"\d+[\.\)]\s*(.+\?)", agent_output)
    if q_patterns:
        questions = q_patterns[:3]
    else:
        questions = [
            "A compra foi feita presencialmente ou online?",
            "Voce possui nota fiscal ou comprovante?",
            "Qual a empresa envolvida no caso?"
        ]
    
    # Quick replies based on tools used
    quick_replies = ["Continuar orientacao", "Fazer outra pergunta"]
    if template_letter:
        quick_replies = ["Copiar mensagem", "Refazer com outro tom", "Fazer outra pergunta"]
    elif deadline:
        quick_replies = ["Preparar mensagem", "Recalcular prazo", "Continuar orientacao"]
    
    return StructuredReply(
        session_id=session_id,
        step_title=step_title,
        step_content=agent_output,
        relevant_title=relevant_title,
        relevant_content=relevant_content,
        calc_performed=calc_performed,
        deadline=deadline,
        questions=questions,
        suggestive_text=f"Com base na analise, posso ajudar com proximos passos.",
        template_letter=template_letter,
        quick_replies=quick_replies,
    )
```

---

## Implementation Order

1. **Phase 1** (Python backend): Create adapter, add structured endpoint
2. **Phase 2** (React frontend): Update API calls, add proxy config
3. **Phase 3** (Integration): Build process, static file serving, testing

---

## Risk Mitigation

1. **Tool output parsing fragility:** The adapter parses tool output text with regex. If the LLM changes output format, parsing may break. Mitigation: Add fallback handling; if parsing fails, return agent output as plain `step_content` with no structured fields.

2. **Pydantic AI message structure changes:** The adapter inspects `ToolCallPart` and `ToolReturnPart`. If Pydantic AI changes its internal message format, the adapter breaks. Mitigation: Pin Pydantic AI version; add try/except around extraction.

3. **Session management mismatch:** React sends `session_id`, Python manages sessions server-side. If React loses `session_id` (page refresh), a new session is created. Mitigation: Store `session_id` in `localStorage` in addition to state.

4. **responseStyle not fully supported:** The Python agent doesn't have a concept of response style. Mitigation: Prepend style instruction to the user message before sending to the agent.

---

## Testing Strategy

1. **Unit tests for adapter:** Test `_parse_deadline_from_tool`, `build_structured_reply`, `_extract_tool_calls`
2. **Integration test:** POST to `/api/chat/structured` and verify response shape
3. **E2E test:** Open React UI, send a message, verify deadline cards render
4. **Fallback test:** Send a message that doesn't trigger any tools, verify graceful degradation
