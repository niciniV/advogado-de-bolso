# Decomposition Proposal: `revised-integration-plan.md`

**Date:** 2026-06-15
**Loop round:** 19 (decomposition stage)
**Author:** decomposer subagent
**Status:** PROPOSAL ONLY — do not apply until reviewed by 3 reviewer subagents and applied by a separate splitter subagent.

---

## 1. Scope and references

- **Source plan:** `.opencode/plans/revised-integration-plan.md` — **1416 lines** (the prompt cited 1365; the file has grown by 51 lines since the round-18 review snapshot recorded in `.opencode/loop/orchestration-state.md`). The 51-line delta is the only material change between round-18 and now, concentrated in the `service.py` "Files to Create" spec (added lock-acquisition commentary around `update_case_meta`).
- **Goal:** split the source plan into multiple smaller files (100–400 lines each) that are self-contained, reviewable units, with no information loss.
- **Navigation target:** the project's DOX root is **`AGENTS.md` at the repo root** (not `.opencode/AGENTS.md`, which does not exist in this repo). The split should be navigable from that root DOX file. The plan files live under `.opencode/plans/`, so the natural navigation is either a new `.opencode/plans/AGENTS.md` child DOX or an entry in the root `AGENTS.md` File Map. See §6 (open question 1) for the recommended convention.
- **Dox convention reference (for the navigation file only):** the project uses a Purpose / Ownership / Local Contracts / File Map / Work Guidance / Verification / Child DOX Index layout (see `src/advogado_de_bolso/AGENTS.md`). The new plan-split child DOX should follow the same File Map + links convention, not the full layout (plans are reference docs, not code-navigators).

---

## 2. Cross-reference policy

All cross-references between the new plan-split files will use **semantic anchors** (file path + section heading), not line numbers. Line numbers will shift after the split and any baked-in numeric anchors would go stale.

- **Each new file** will have a 4–6 line header at the top containing:
  1. `# <NN>-<slug>.md` (heading).
  2. `**Source plan:** revised-integration-plan.md (split round 19)`.
  3. `**In this file:** <one-sentence summary>`.
  4. `**Related files:**` followed by a short bulleted list of the 1–4 most relevant sibling files (using relative links, e.g., `[02-schemas.md](./02-schemas.md)`).
  5. Where the file is a partial spec for a file also covered in "Files to Modify" (e.g., `agent.py`, `service.py`, `api.py`, `cli.py`, `defaults.ts`, several `tests/test_*.py`), a single line `**See also:** [18-backend-modifications.md](./18-backend-modifications.md) — incremental changes from the "Files to Modify" section.`
- **Parent pointer in every header:** the entry file `99-index.md` is the only file that links to all siblings. Every other file lists its 1–4 most-related siblings but does NOT maintain a complete up-to-date list of every other file in the set.
- **No content duplication for cross-referenced items:** the source plan has duplicate specs in "Files to Create" and "Files to Modify" (e.g., `agent.py` is fully spec'd in Create and re-referenced in Modify). The split resolves this by placing the full spec once and using a one-line pointer in the duplicate location. **No information is lost** — the duplicate location is just a "see primary spec" line.
- **No anchors on `IMPLEMENTATION ORDER` items.** The Implementation Order section refers to `tests/test_calculos.py` etc. by file path. Those references survive the split unchanged because the new plan files describe **what** to build, not **when**, and the Implementation Order file uses the same path names that already exist in the source tree.

---

## 3. Parent plan retention policy

**Recommended: (b) — reduce the original to a thin index file that links to all the new files and contains a brief 1-paragraph summary.**

Rationale:

- (a) **Delete the original.** Rejected: the source path is referenced by name from the root `AGENTS.md` File Map (line 29 of repo-root `AGENTS.md`: "`.opencode/plans/revised-integration-plan.md` | Active implementation plan"), from many loop-state files in `.opencode/loop/`, and from the round-18 review notes. Deleting without leaving a stub at the same path would create dead links and would obscure the chain of revisions.
- (b) **Reduce the original to a thin index.** Selected. The file at the original path becomes a ~20-line landing page that:
  1. Identifies itself as the index for the round-19 split.
  2. Lists the new sibling files with one-line summaries and links.
  3. Contains a one-paragraph "what this plan covers" summary so the file remains a valid link target with useful landing content.
  4. Notes that the full content has moved to the sibling files.
- (c) **Keep the original as-is.** Rejected: defeats the purpose. The whole point of the split is to make the plan reviewable in <400-line chunks. Leaving a 1416-line file as the canonical plan makes both copies of "the plan" available and re-introduces the review-burden problem this loop iteration is trying to solve.

The thin-index approach preserves the path (so existing references stay valid) while ensuring the actual plan content lives in reviewable units. If a reviewer believes the original should be deleted outright, (a) is acceptable as an alternative; in that case, the splitter should also update the root `AGENTS.md` File Map to point to `99-index.md` instead.

---

## 4. Proposed target layout (24 files + 1 index = 25 files)

The numbering convention: `00-` is the architectural overview, `01-` through `23-` are concern-grouped plan content, `99-` is the index. Each file's content comes from the source plan; this section maps **source plan line ranges → target file**, gives a one-sentence summary, and the approximate target size after the split (which adds ~5 lines of header per file).

| # | Target file (relative to `.opencode/plans/`) | Source lines (in `revised-integration-plan.md`) | One-sentence summary | Approx. target size |
|---|---|---|---|---|
| 1 | `00-overview-and-architecture.md` | 1–22 | Title, "Replaces" note, and the 10-bullet Architecture Summary. | ~30 lines |
| 2 | `01-contracts.md` | 25–66 | `src/advogado_de_bolso/contracts.py` spec — `DeadlineResult`, `DraftedDocument`, `KnowledgeChunk` Pydantic envelopes. | ~55 lines |
| 3 | `02-schemas.md` | 67–87 | `src/advogado_de_bolso/schemas.py` spec — `StructuredChatRequest`/`Response`, `CaseSummary`, `CaseResponse`, `ChatMessage`, `UpdateCaseRequest`. | ~35 lines |
| 4 | `03-adapter.md` | 88–267 | `src/advogado_de_bolso/adapter.py` spec — `extract_structured_response()` plus the three helpers `_extract_questions`, `_extract_suggestive_text`, `_derive_quick_replies`. | ~190 lines |
| 5 | `04-storage.md` | 269–286 | `src/advogado_de_bolso/storage/cases.py` spec — `Case` model, `load`/`save`/`delete`/`list_all` signatures, path containment, atomic writes, lock retention. | ~30 lines |
| 6 | `05-agent-and-system-prompt.md` | 287–392 | `src/advogado_de_bolso/agent.py` spec — `build_agent`, `STYLE_PROMPTS`, `_current_style` ContextVar, and the full merged `SYSTEM_PROMPT`. | ~115 lines |
| 7 | `06-service-class.md` | 394–805 | `src/advogado_de_bolso/service.py` — `ChatService` class with `__init__`, `_get_case_lock`, `chat_structured`, `list_cases`, `get_case`, `update_case_meta`, `delete_case`, `get_history`; also the `REVIEW_BLOCKED_MESSAGE` constant, `_now`/`_now_ms` helpers, `ChatResult` dataclass, and `ChatBackend`/`ReviewerLike` Protocols. Splits at the natural class-boundary just before `_collect_tool_returns`. | ~420 lines |
| 8 | `07-service-helpers-and-backend.md` | 808–927 | `service.py` module-scope helpers (`_collect_tool_returns`, `_truncate_history_to_turns`), the `_to_model_messages` removal note (ISSUE-IND-003), and `AgentChatBackend` + `build_chat_service` notes. | ~130 lines |
| 9 | `08-api.md` | 929–996 | `src/advogado_de_bolso/api.py` spec — endpoint list, UUID-typed path parameters, CORS, static serving / explicit SPA fallback, blocked-envelope 422 contract, 503 error handler. | ~80 lines |
| 10 | `09-cli-config-deps.md` | 998–1015 | `src/advogado_de_bolso/cli.py` spec (reviewer-gated buffered streaming), `config.py` addition (`cases_path` env alias), and the `deps.py` "no changes" note. | ~30 lines |
| 11 | `10-frontend-build-and-config.md` | 1113–1127, 1204–1238 | Frontend build config — `Makefile` targets, full `package.json` rewrite (ISSUE-M3-004 + `@types/node` retention), `vite.config.ts` `server.proxy` (ISSUE-DS-003 + ISSUE-USR-014). | ~95 lines |
| 12 | `11-frontend-types-and-defaults.md` | 1141–1143, 1270–1282 | Frontend types and seed data — `base_frontend/src/types.ts` (`is_demo` addition) and `base_frontend/src/defaults.ts` (`initialPreferences` + `seedCases` with `is_demo: true`). | ~35 lines |
| 13 | `12-frontend-api-client.md` | 1129–1139 | `base_frontend/src/api.ts` spec — wire interfaces, snake↔camel mappers, `renameCase` thin wrapper. | ~25 lines |
| 14 | `13-frontend-app.md` | 1240–1268, 1276–1277 | `base_frontend/src/App.tsx` spec (full handler rewrite, explicit `seedCases`/`initialPreferences` deletion, `isSendingMessage` rename, `forceNewCase`) and `base_frontend/src/components/ChatInterface.tsx` (rename `isLoading` → `isSendingMessage`). | ~50 lines |
| 15 | `14-frontend-tests.md` | 1100–1111 | `base_frontend/src/api.test.ts` (mapper unit tests) and `base_frontend/src/App.test.tsx` (RTL integration tests for demo/quick-guide/blocked flows). | ~25 lines |
| 16 | `15-backend-tests.md` | 1017–1098 | All backend test-file specs — `test_adapter.py`, `test_storage.py`, `test_calculos.py`, `test_redigir.py`, `test_rag_tool.py`, `test_api.py`, `test_service.py`, `test_agent.py`, `test_cli.py`. Roughly 80 lines of bullet spec plus ~10 lines of section headers. | ~110 lines |
| 17 | `16-tools-modifications.md` | 1153–1160 | "Files to Modify" — `tools/calculos.py`, `tools/redigir.py`, `tools/rag.py` (return-type and prompt changes). | ~25 lines |
| 18 | `17-config-and-docs-modifications.md` | 1011–1012, 1174–1181, 1201–1202 | "Files to Modify" — `config.py` (cases_path env alias + injection), `.env.example` (CASES_PATH), `README.md` (dev/prod/single-worker notes), `tests/test_config.py` (env override test). | ~30 lines |
| 19 | `18-frontend-modifications.md` | 1149–1151, 1162–1199, 1283 | "Files to Modify" — short pointer list (agent.py, service.py, api.py, cli.py, test_*.py — all reference the corresponding "Create" file in items 6–16). The few items with new content beyond the Create file are folded into items 10–14 above. | ~20 lines |
| 20 | `19-files-to-delete.md` | 1286–1289 | Files to Delete — `base_frontend/server.ts`. | ~10 lines |
| 21 | `20-implementation-order.md` | 1293–1305 | The 9-step gated implementation order with per-step pytest/ruff/mypy gates (ISSUE-M3-018). | ~25 lines |
| 22 | `21-functional-checks.md` | 1307–1328 | The 21 functional verification scenarios (dev mode, UI smoke, persistence, CRUD, style switching, reviewer block, demo cases, production, CORS, CLI, SPA typo, retained-lock serialization, empty prose, unknown tool name, UUID case routes, history mapping, demo API isolation, quick-guide isolation). | ~40 lines |
| 23 | `22-resolved-decisions.md` | 1332–1344 | "Resolved Open Decisions" — Decision #1 (`redigir_documento` JSON envelope, kept APENAS prompt) and Decision #2 (PATCH only, `UpdateCaseRequest`). | ~25 lines |
| 24 | `23-issue-tracking-table.md` | 1346–1403 | The full ISSUE-* / REVIEW-* / USR-* fix table from "Resolved Open Decisions #3" (round-3 plan-level fixes). | ~70 lines |
| 25 | `24-out-of-scope.md` | 1405–1416 | Out-of-Scope Notes — multi-worker uvicorn, `_index.json`, auth, API streaming, cross-process writes, lock-registry lifetime, single-task ContextVar scoping, sub-agent LRU cache. | ~25 lines |
| 26 | `99-index.md` | (synthesized) | Index/landing file. Replaces the original plan as the canonical entry point. Lists all 25 sibling files with one-line summaries and links. See §5 for the proposed content. | ~70 lines |

**Total:** 25 new files. Plus the **thin-index replacement** of `.opencode/plans/revised-integration-plan.md` (§3, option b) and **optionally** a new `.opencode/plans/AGENTS.md` child DOX that follows the project's File Map convention (§6 open question 1).

**File-size sanity check:**

- All files are 10–420 lines. The only file over 400 lines is `06-service-class.md` (~420), which is unavoidable because `ChatService` is the single largest concern in the plan and the class definition (including `chat_structured`'s 100+ line body) is one logical unit. Reviewers can read this file in a single sitting, but the threshold is intentionally tight. If the splitter needs to break it further, the natural sub-split is: (a) `__init__` + `_get_case_lock` + small methods (~80 lines, lines 511–632), (b) `chat_structured` body (~170 lines, lines 548–701), (c) `update_case_meta` / `delete_case` / `get_history` (~90 lines, lines 722–805). I'd prefer not to split unless the splitter's tooling requires it.
- No file under 10 lines except `19-files-to-delete.md` (~10 lines, single-bullet section). Acceptable because the "delete" content is intrinsically tiny and grouping it into another file would dilute the modularity.

---

## 5. Concrete file list (recommended split)

This is the canonical list. Reviewers should compare against §4; differences are noted inline.

```
.opencode/plans/
├── 00-overview-and-architecture.md          (30 lines)
├── 01-contracts.md                          (55 lines)
├── 02-schemas.md                            (35 lines)
├── 03-adapter.md                            (190 lines)
├── 04-storage.md                            (30 lines)
├── 05-agent-and-system-prompt.md            (115 lines)
├── 06-service-class.md                      (420 lines)
├── 07-service-helpers-and-backend.md        (130 lines)
├── 08-api.md                                (80 lines)
├── 09-cli-config-deps.md                    (30 lines)
├── 10-frontend-build-and-config.md          (95 lines)
├── 11-frontend-types-and-defaults.md        (35 lines)
├── 12-frontend-api-client.md                (25 lines)
├── 13-frontend-app.md                       (50 lines)
├── 14-frontend-tests.md                     (25 lines)
├── 15-backend-tests.md                      (110 lines)
├── 16-tools-modifications.md                (25 lines)
├── 17-config-and-docs-modifications.md      (30 lines)
├── 18-frontend-modifications.md             (20 lines)
├── 19-files-to-delete.md                    (10 lines)
├── 20-implementation-order.md               (25 lines)
├── 21-functional-checks.md                  (40 lines)
├── 22-resolved-decisions.md                 (25 lines)
├── 23-issue-tracking-table.md               (70 lines)
├── 24-out-of-scope.md                       (25 lines)
├── 99-index.md                              (70 lines)
└── revised-integration-plan.md              (REPLACED with thin index, ~20 lines)
```

Optional navigation helper:

```
.opencode/plans/
└── AGENTS.md                                (NEW, ~40 lines, child-DOX File Map)
```

---

## 6. Risks and open questions for the reviewers

1. **The prompt's "navigable from `.opencode/AGENTS.md`" instruction refers to a file that does not exist.** The actual DOX root is `AGENTS.md` at the repo root. Two options for the splitter:
   - **(A) Create a new `.opencode/plans/AGENTS.md`** following the project's child-DOX File Map convention. This mirrors `src/advogado_de_bolso/AGENTS.md` and `tests/AGENTS.md`, which are existing child DOX files. This is the most idiomatic option.
   - **(B) Update the repo-root `AGENTS.md` File Map** to add a row pointing to `99-index.md` (and optionally to the individual split files, though that bloats the root map).
   - **Recommended: (A).** A `.opencode/plans/AGENTS.md` is local to the plans directory, is the right scope for a plans-child DOX, and does not bloat the repo-root `AGENTS.md`. The root `AGENTS.md` File Map entry for the plan can stay as a one-line pointer to the new child DOX.

2. **The source plan is 1416 lines, not 1365 as stated in the prompt.** Difference is +51 lines, all in `service.py` "Files to Create" (the lock-acquisition commentary added around `update_case_meta`, which the round-18 reviewer verified). The line ranges in §4 use the actual file. This is informational; the splitter should use the actual content, not the line numbers, when extracting sections.

3. **`06-service-class.md` is ~420 lines**, slightly over the 400-line target. The `ChatService` class is intrinsically large (a single method, `chat_structured`, is ~150 lines). Sub-splitting it would scatter related state (e.g., the `try/finally` for `_current_style` reset is part of `chat_structured`). If reviewers demand a strict 400-line cap, the sub-split point is documented in §4 (just before line 632 — after `chat_structured`'s early blocked-turn return). The default recommendation is to keep the class in one file because it is one logical unit; the sub-split is the fallback.

4. **The "Files to Modify" section (source lines 1149–1283) re-references items also in "Files to Create".** Most are bare pointers ("See Files to Create section above"). The proposed split resolves this by:
   - Putting the **full spec** in the concern-grouped file (items 6–16 in §4).
   - Putting a **pointer-only stub** in `18-frontend-modifications.md` and `17-config-and-docs-modifications.md`.
   - The few "Modify" entries with **incremental new content** beyond the "Create" file are folded into the concern file (e.g., `package.json` is in `10-frontend-build-and-config.md` because that's where its full content lives, with the "Files to Modify" reference in `18-frontend-modifications.md` becoming a single line). **No information is lost**, but the splitter must take care to copy the **full** content of items that appear in both "Create" and "Modify" sections, not just the "Modify" reference.

5. **The `22-resolved-decisions.md` and `23-issue-tracking-table.md` split** separates the high-level decisions (#1, #2) from the granular ISSUE-* / REVIEW-* / USR-* fix table (#3). This is a judgement call. An alternative is to merge them into a single `22-resolved-decisions-and-fixes.md` file (~95 lines). I split them because the decisions are reading material for new implementers and the table is reference material for reviewers — different audiences, different reading patterns. Reviewers may merge them if they prefer.

6. **`18-frontend-modifications.md` is mostly pointer content** (~20 lines, no full code). This is intentional. The full frontend-modification content lives in `10-frontend-build-and-config.md`, `11-frontend-types-and-defaults.md`, `12-frontend-api-client.md`, `13-frontend-app.md`, and `14-frontend-tests.md`. If reviewers prefer a single "all frontend changes" file, the recommended alternative is to fold `18-frontend-modifications.md` into a comment header on each of those five files and skip the separate file. The current split is the more-granular option.

7. **Information-loss verification:** the splitter should diff-verify that no source-plan content is dropped. The highest-risk areas are:
   - The `SYSTEM_PROMPT` block (lines 341–392) — long code block, easy to clip.
   - The `chat_structured` body (lines 548–700) — long method, has nested `try/finally` and `if/else` blocks.
   - The `_truncate_history_to_turns` helper (lines 828–877) — algorithmic logic.
   - The ISSUE-* tracking table (lines 1349–1403) — many rows, each with two columns.

   The splitter should preserve code-block fences, bullet indentation, and the exact wording of the ISSUE-* fix descriptions (which the round-18 reviewer validated verbatim).

8. **Out-of-Scope Notes (lines 1405–1416) are intentionally a separate file** rather than merged into the index or the architecture overview. Rationale: these are operational constraints (multi-worker, auth, streaming) that implementers need to surface during code review, not during initial plan reading. Keeping them in their own file makes "did we forget a constraint?" a quick file-open.

9. **The implementation order (lines 1293–1305) is its own file** rather than folded into the index. Rationale: the implementer reads the order in a single pass before starting, and the file's existence lets the orchestrator (or a code-review agent) check that each batch gate ran before the next started.

10. **The splitter is not asked to fix any content.** No ISSUE-* table updates, no new ISSUE-* entries, no editorial changes. This proposal is a pure structural split. If reviewers find content issues during the split-review, those should be reported back to the planning loop, not patched in the split.

---

## 7. Summary for the orchestrator

- **Source:** `.opencode/plans/revised-integration-plan.md`, 1416 lines.
- **Output:** 25 new files under `.opencode/plans/`, each 10–420 lines, plus a thin-index replacement of the original (option b in §3), plus optionally a new `.opencode/plans/AGENTS.md` child DOX (§6 Q1).
- **Cross-references:** semantic anchors only (no line numbers). Each file has a 4–6 line header with related-sibling links.
- **No information loss:** the source plan is fully preserved; the only structural change is resolving the "Create" / "Modify" duplication by giving each item exactly one primary location with a pointer in the other.
- **Risks called out:** the `06-service-class.md` size (~420 lines), the `Create`/`Modify` duplication resolution, the line-count discrepancy (1416 vs. 1365), and the splitter's responsibility to verify content preservation in long code blocks.
