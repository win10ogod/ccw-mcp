# Repository Guidelines

## Project Structure & Modules
- `ccw_mcp/` — core package
  - `server.py` entrypoint (`ccw-mcp --stdio`)
  - `cel/` platform CEL implementations (`linux.py`, `windows.py`, `portable.py`)
  - `tools/` MCP tool handlers (e.g., `capsule.py`, `witness.py`, `promote.py`)
  - `policy/` policy engine
  - `util/` hashing, diff, tracing helpers
- `tests/` — pytest suite (`test_basic.py`, `test_windows.py`)
- `docs/` — install and architecture docs
- `example_workflow.py` — minimal usage example
- `pyproject.toml` — Python 3.11+, hatchling, `uv` workflow

## Build, Test, and Dev
- Install deps: `uv sync` (add `--dev` for tests)
- Run server locally: `uv run ccw-mcp --stdio`
- Run tests (all): `uv run pytest -q`
- Windows-only tests: `uv run pytest -k windows -v`
- Quick subsets: `uv run pytest tests/test_basic.py -q`

## Coding Style & Naming
- Python: PEP 8, 4‑space indentation, type hints where helpful.
- Names: modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_CASE`.
- Keep public APIs small and explicit; prefer dataclasses/typed dicts to loose dicts.
- Docstrings: triple‑quoted summaries with short examples when non‑obvious.
- No enforced formatter/linter; match existing style. If using one locally, prefer `ruff`/`black` defaults but do not reformat unrelated code in PRs.

## Testing Guidelines
- Frameworks: `pytest`, `pytest-asyncio`.
- Structure: place tests under `tests/`, name files `test_*.py`, keep fixtures local when possible.
- Platform: Windows suite auto‑skips on non‑Windows; verify Linux/macOS paths with `portable` CEL and Windows paths with `windows` CEL when available.
- Add tests for new tools/policies and edge cases (timeouts, path deny rules, resource limits).

## Commit & Pull Requests
- Commits: concise, imperative subject; group by logical change. Example: `feat(cel): add portable copy strategy` or `fix(windows): normalize backslashes in mount`.
- PRs must include: purpose, summary of changes, test plan (commands run), platform notes (Linux/Windows), and docs updates when user‑facing.
- Keep diffs minimal; avoid drive‑by refactors. Link issues where applicable and include before/after output when affecting CLI or JSON‑RPC.

## Security & Configuration
- Never run with elevated privileges during development.
- Default storage: `CCW_STORAGE` (e.g., `~/.ccw-mcp`). Do not commit witness artifacts or local temp data.
- Validate policy changes with tests and a dry‑run: `capsule/promote` with `dry_run=true`.

