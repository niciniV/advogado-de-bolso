# 19-files-to-delete.md

**Source plan:** revised-integration-plan.md (split round 19, lines 1286-1289)
**In this file:** Files to Delete — `base_frontend/server.ts`.
**Related files:** [00-overview-and-architecture.md](./00-overview-and-architecture.md) (the `server.ts` deletion is noted in the Architecture Summary: "No Express, no Gemini direct calls. `server.ts` deleted."), [10-frontend-build-and-config.md](./10-frontend-build-and-config.md) (the `package.json` rewrite that breaks the deleted file's `dev`/`build`/`start`/`clean` scripts).
**See also:** [00-overview-and-architecture.md](./00-overview-and-architecture.md) — the Architecture Summary documents the rationale for the deletion (the FastAPI server is the single backend; the deleted `server.ts` was the legacy Express + direct-Gemini stack that this plan removes).

## Files to Delete

- `base_frontend/server.ts`

