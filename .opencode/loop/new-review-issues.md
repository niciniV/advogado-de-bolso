# Independent Review: revised-integration-plan.md

**Date:** 2026-06-15
**Reviewer:** Independent agent (post-automated-loop review)
**Plan:** `.opencode/plans/revised-integration-plan.md` (1290 lines)
**Baseline:** `.opencode/loop/open-issues.md` (49 closed issues from 9-round automated loop)
**Orchestration State:** Round 9 complete, 0 open issues, plan declared "ready for implementation"

---

## Executive Summary

The automated reviewer loop (mimo-reviewer, deepseek-reviewer, minimax-m3-reviewer) performed thorough work, finding and fixing 49 issues across 9 rounds. This independent review identified **3 residual issues** the loop missed, plus verified that **3 previously-closed fixes remain correctly present** in the current plan text. None of the 3 new issues are blockers for implementation, but Issue #1 would cause an `ImportError` at runtime if implemented exactly as written.

**Recommendation:** Apply the 3 fixes below, then proceed to implementation (Round 10).

---

## New Issues Found (Not in open-issues.md)

---

### Issue #1: `REVIEW_BLOCKED_MESSAGE` imported from non-existent module

- **Severity:** Blocker
- **Category:** correctness / import error
- **Location:** Plan line 436, `service.py` import block
- **Affected file(s):** `src/advogado_de_bolso/service.py` (planned)

**Description:**
The plan's `service.py` code imports `REVIEW_BLOCKED_MESSAGE` from `.tools.revisor`:

```python
from .tools.revisor import REVIEW_BLOCKED_MESSAGE, RevisionResult
```

However, `REVIEW_BLOCKED_MESSAGE` does **not** exist in `src/advogado_de_bolso/tools/revisor.py`. It is defined locally in the current `src/advogado_de_bolso/service.py` (lines 21-24). Implementing the plan exactly as written would produce an `ImportError: cannot import name 'REVIEW_BLOCKED_MESSAGE' from 'advogado_de_bolso.tools.revisor'` on first import.

**Why the loop missed it:**
The automated reviewers focused on whether the reviewer responsibility transfer (ISSUE-M3-003) was clear, but they did not trace the `REVIEW_BLOCKED_MESSAGE` constant back to its actual definition location. They assumed the plan's import statement was correct.

**Fix (recommended):**
Define `REVIEW_BLOCKED_MESSAGE` locally in the new `service.py` rather than importing it. The constant is tightly coupled to the service layer's reviewer-blocking behavior and has no reason to live in `tools.revisor`.

```python
# In service.py, at module scope
REVIEW_BLOCKED_MESSAGE = (
    "Nao foi possivel validar esta resposta com seguranca. "
    "Tente reformular a pergunta ou procure o PROCON, a Defensoria Publica "
    "ou um advogado de confianca."
)
```

Remove the import from `.tools.revisor` for this constant, keeping only `RevisionResult`:

```python
from .tools.revisor import RevisionResult
```

**Alternative fix:** Move `REVIEW_BLOCKED_MESSAGE` to `tools/revisor.py` and export it there. This is acceptable but unnecessary coupling.

---

### Issue #2: `ChatService.rename_case` is dead code

- **Severity:** Minor
- **Category:** dead code / api inconsistency
- **Location:** Plan line 717, `service.py` ChatService methods list
- **Affected file(s):** `src/advogado_de_bolso/service.py` (planned), `base_frontend/src/api.ts` (planned)

**Description:**
The plan specifies `ChatService.rename_case(self, case_id: str, new_title: str) -> Case` with full load/save logic. However, the API endpoint list shows only one case-update endpoint:

- `PATCH /api/cases/{case_id}` (body: `UpdateCaseRequest { title?, icon_name?, response_style? }`) → delegates to `ChatService.update_case_meta`

No dedicated `POST /api/cases/{case_id}/rename` or similar endpoint exists. The frontend's `handleRenameCase` calls `apiClient.renameCase(caseId, newTitle)`, but the `api.ts` spec does not show a dedicated rename endpoint either. The most natural mapping is that `renameCase` on the client wraps a `PATCH` with `{ title: newTitle }`, which calls `update_case_meta`, not `rename_case`.

As a result, `rename_case` is never invoked by any planned endpoint or client method.

**Why the loop missed it:**
The automated reviewers raised ISSUE-M3-008 (`update_case_meta` not wired), which was fixed by wiring `PATCH` to `update_case_meta`. They did not notice that the old `rename_case` method became orphaned in the process. USR-005 (API contract inconsistency) addressed the PATCH body shape and the missing GET endpoint, but did not flag the orphaned `rename_case`.

**Fix (recommended):**
Remove `rename_case` from `ChatService` entirely. It adds no value over `update_case_meta(case_id, title=new_title)`. The frontend's `apiClient.renameCase` can simply call the PATCH endpoint with `{ title: newTitle }`.

If preserving backward compatibility is desired, rename `rename_case` to a private `_rename_case` or remove it and update the frontend client spec to map `renameCase` → `PATCH /api/cases/{id}`.

---

### Issue #3: `_to_model_messages` defined but never called

- **Severity:** Minor
- **Category:** dead code / unreachable helper
- **Location:** Plan line 839, `service.py` helper functions
- **Affected file(s):** `src/advogado_de_bolso/service.py` (planned)

**Description:**
`_to_model_messages(chat_history: list[ChatMessage]) -> list[ModelMessage]` is defined with a detailed docstring explaining it is a "fallback when `model_history` is empty." However, no code path in the plan actually calls it:

- `chat_structured` (the only history consumer) uses `_truncate_history_to_turns(case.model_history, ...)` directly (line ~587).
- New cases initialize `model_history=[]` (line 582), which is an empty list — but the backend receives it directly as `llm_history`, not via `_to_model_messages`.
- Legacy migration scenarios (cases with `chat_history` but empty `model_history`) are never handled by an explicit branch.
- The test rewrite section (`tests/test_service.py`) does not mention exercising `_to_model_messages`.

The function is effectively unreachable. It was added as part of ISSUE-M3-002 ("Spec'd `_collect_tool_returns` and `_to_model_messages` in service.py"), but only `_collect_tool_returns` has a caller (line 634).

**Why the loop missed it:**
ISSUE-M3-002 requested that both helpers be "spec'd," and the fixer added both. The reviewers verified that both were present in the plan but did not trace whether `_to_model_messages` had an actual call site.

**Fix (recommended):**
Either:

1. **Add a caller:** In `chat_structured`, before `_truncate_history_to_turns`, add:
   ```python
   raw_history = case.model_history or _to_model_messages(case.chat_history)
   llm_history = _truncate_history_to_turns(raw_history, self._max_llm_history_turns)
   ```
   This makes the fallback explicit for legacy cases.

2. **Remove the function:** Delete `_to_model_messages` and document that `model_history` must always be populated (even if empty `[]`) from the first turn onward. Since the plan initializes `model_history=[]` for new cases (line 582), the empty-list case is already handled natively.

Option 2 is simpler and avoids an unnecessary indirection. The empty list `[]` is valid input to `_truncate_history_to_turns` (the function returns `[]` for empty input).

---

## Spot-Check Results (Previously-Closed Issues)

Verified that the fixes for 3 representative previously-closed issues are correctly present in the current plan text.

---

### Spot-Check 1: ISSUE-001 (REACT_DIST path off-by-one)

- **Status:** FIXED ✓
- **Verification:** `grep -n 'parent.parent.parent' .opencode/plans/revised-integration-plan.md`
- **Result:** Line 914 shows `REACT_DIST = Path(__file__).parent.parent.parent / "base_frontend" / "dist"`.
- **Notes:** Lines 912-913 include explicit path-arithmetic comments confirming that `.parent.parent.parent` is the project root and `.parent.parent.parent.parent` is wrong. The fix is clearly documented and correct.

---

### Spot-Check 2: ISSUE-004 (empty-prose fallback)

- **Status:** FIXED ✓
- **Verification:** `grep -n 'Análise inicial' .opencode/plans/revised-integration-plan.md`
- **Result:**
  - Line 125 references the fix with issue ID.
  - Line 126 filters whitespace paragraphs: `paragraphs = [p for p in prose.strip().split("\n\n", 1) if p.strip()]`.
  - Lines 131-132 show the fallback: `step_title = "Análise inicial"` and `step_content = ""`.
  - Line 988 lists it in test specs: "Empty prose → `step_title == 'Análise inicial'`".
  - Line 1221 lists it in functional checks.
- **Notes:** The fallback is correctly implemented and tested. The previous dead-code bug (`""` passing through because `split` returns `[""]`) is resolved.

---

### Spot-Check 3: ISSUE-M3-001 (`model_history` field on `Case`)

- **Status:** FIXED ✓
- **Verification:** `grep -n 'model_history' .opencode/plans/revised-integration-plan.md`
- **Result:**
  - Line 267: `model_history: list[ModelMessage]` is included in the `Case` model specification.
  - Line 582: Initialized to `[]` in new-case creation.
  - Line 614: Read into `llm_history` via `_truncate_history_to_turns(case.model_history, ...)`.
  - Line 670: Persists new turn's messages: `case.model_history = case.model_history + new_messages`.
  - Line 965: CLI also required to populate it for cross-transport compatibility.
  - Line 1034: Test spec for `model_history` persistence round-trip.
  - Line 1194: Implementation order step 13 includes it.
  - Line 1211: Functional check verifies persistence across restarts.
  - Line 1254: Closed-issue tracking table confirms the fix.
- **Notes:** The field is fully wired into persistence, truncation, testing, and CLI. The fix is comprehensive and correct.

---

## Overall Assessment

### Plan Quality: High

The automated reviewer loop produced a robust plan. The 49 issues it found and fixed were genuine, high-quality defects. The plan is internally consistent, well-structured, and the 20-step implementation order with per-step `pytest` gates is a sound execution strategy.

### Residual Risk: Low

The 3 new issues found in this review are **not blockers for implementation**:

- Issue #1 is a compile-time `ImportError` that would be caught immediately on first import.
- Issues #2 and #3 are dead-code problems that do not affect runtime behavior.

### Recommendation

1. Fix Issue #1 (wrong import) before or during the first implementation step.
2. Address Issues #2 and #3 during the service.py rewrite (step 13 in the implementation order).
3. Proceed to implementation Round 10.

---

## Cross-Reference with open-issues.md

Confirmed that none of the 3 new issues duplicate any of the 49 closed issues:

| New Issue | Nearest Closed Issue | Why Not a Duplicate |
|-----------|---------------------|---------------------|
| #1 REVIEW_BLOCKED_MESSAGE import | ISSUE-M3-003 (reviewer transfer) | M3-003 focused on *who* calls the reviewer, not *where* the constant is defined. |
| #2 rename_case dead code | ISSUE-M3-008 (update_case_meta wiring) | M3-008 fixed the PATCH wiring but left rename_case orphaned. |
| #3 _to_model_messages unreachable | ISSUE-M3-002 (spec helpers) | M3-002 verified both helpers were *defined*, not that both were *called*. |

---

*End of review*
