# 10-frontend-build-and-config.md

**Source plan:** revised-integration-plan.md (split round 19, lines 1113-1127 + 1145-1147 + 1204-1238)
**In this file:** Frontend build config — `Makefile` targets, full `package.json` rewrite (ISSUE-M3-004 + `@types/node` retention per ISSUE-USR-014), `vite.config.ts` `server.proxy` (ISSUE-DS-003 + ISSUE-USR-014), and the `package-lock.json` generation note.
**Related files:** [13-frontend-app.md](./13-frontend-app.md) (the `App.tsx` rewrite that the build config compiles), [14-frontend-tests.md](./14-frontend-tests.md) (Vitest test scripts added in `package.json`), [17-config-and-docs-modifications.md](./17-config-and-docs-modifications.md) (the `.env.example` and `README.md` updates that pair with the build config).

### `Makefile`
```makefile
frontend:
	cd base_frontend && npm ci && npm run build

dev-api:
	uv run advogado-api

dev-frontend:
	cd base_frontend && npm run dev

dev:
	$(MAKE) -j2 dev-api dev-frontend
```

### `base_frontend/package-lock.json` (generated)
- Generate with `cd base_frontend && npm install` only after the final `package.json` rewrite.
- Commit it because the Makefile and final verification intentionally use reproducible `npm ci` installs.

### `base_frontend/package.json`
ISSUE-M3-004: full rewrite. The current `package.json` references `server.ts` in FOUR scripts (`dev`, `build`, `start`, `clean`). After the file deletion, every one of these breaks. The full set of changes:

- `"dev"`: `"vite"` (was `"tsx server.ts"`)
- `"build"`: `"vite build"` (was `"vite build && esbuild server.ts --bundle --platform=node --format=cjs --packages=external --sourcemap --outfile=dist/server.cjs"`)
- `"start"`: **REMOVED** (the FastAPI server now serves the build in prod; a separate Node `start` is redundant)
- `"clean"`: `"rimraf dist"` or `"rm -rf dist"` (was `"rm -rf dist server.js"`)
- `"preview"`: `"vite preview"` (kept; useful for testing the prod build)
- `"lint"`: `"tsc --noEmit"` (kept)
- `"test"`: `"vitest run"` (new; runs mapper and App integration tests)
- Remove `dependencies`: `@google/genai`, `express`, `dotenv`, `motion` (all consumed only by the deleted `server.ts`)
- Remove `devDependencies`: `tsx`, `esbuild`, `@types/express` (consumed only by the deleted `server.ts`)
- Add `devDependencies`: `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`.
- **KEEP** `devDependencies: @types/node` (ISSUE-USR-014): the rewritten `vite.config.ts` (and the kept `lint` script which runs `tsc --noEmit`, see line 1134 below) still consumes Node ambient types. `vite.config.ts` imports `path` from `'path'` (line 3), uses `__dirname` (line 11) for `path.resolve(__dirname, '.')`, and reads `process.env.DISABLE_HMR` (lines 17, 19) for the HMR toggle. None of these compile under `tsc` without `@types/node`. Removing `@types/node` would break `npm run lint` (the `tsc --noEmit` gate, kept on line 1134). The only reason `@types/node` would have been removable is if `vite.config.ts` were rewritten to use `import.meta.url` + `fileURLToPath(new URL('.', import.meta.url))` (still requires `@types/node` for `URL` ambient types in many TS configs) or a pure-browser `URL`/`import.meta` style without `path`/`__dirname`/`process.env` (which the current `vite.config.ts` does not satisfy). We pick the simpler path: keep `@types/node` in `devDependencies`. The earlier claim that `@types/node` is "consumed only by the deleted `server.ts`" is incorrect; `vite.config.ts` and the `tsc --noEmit` lint script are also consumers.
- Run `npm install` once after rewriting `package.json` to generate and commit `base_frontend/package-lock.json`. The committed lockfile is required because the Makefile's reproducible production target intentionally uses `npm ci`.
- Environment variables `GEMINI_API_KEY` and the Express-specific `PORT` are no longer used; the FastAPI server reads its own env (`GOOGLE_API_KEY`, `ADVOGADO_API_HOST`, `ADVOGADO_API_PORT`).

### `base_frontend/vite.config.ts`
ISSUE-DS-003: add `server.proxy = { "/api": "http://localhost:8000" }` so dev mode (Vite on :5173) can reach the FastAPI server on :8000. Also tighten the `server` block:
```ts
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
    hmr: { /* existing settings */ },
    watch: { /* existing settings */ },
  },
});
```
ISSUE-USR-014: this spec keeps the existing `path`/`__dirname`/`process.env` usage in the file (the rewrite is a `server` block addition, not a full Node-API removal). The kept Node APIs require `@types/node` to be retained in `devDependencies`; see the `package.json` section above for the cross-reference. The `server.proxy` config from ISSUE-DS-003 is preserved unchanged.

