---
tags:
  - "#exec"
  - "#pytest-markers"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-pytest-markers-plan]]"
  - "[[2026-04-17-pytest-markers-adr]]"
  - "[[2026-04-17-pytest-markers-research]]"
---

# pytest-markers phase-6 summary

## verification-matrix

| Command                                                          | Expectation                    | Result                                                  |
| :--------------------------------------------------------------- | :----------------------------- | :------------------------------------------------------ |
| `uv run pytest -m unit`                                          | green                          | 1158 passed, 1 skipped, 24 deselected                   |
| `uv run pytest -m live_write --collect-only -q`                  | 0 items collected              | 0 selected (1183 deselected)                            |
| `uv run pytest -m live_read --collect-only -q`                   | positive count                 | 24 selected (1159 deselected)                           |
| `uv run pytest tests/test_marker_integrity.py`                   | green                          | 148 passed                                              |
| `uv run pytest tests/test_config.py`                             | green                          | 6 passed                                                |
| `uv run pytest tests/test_release_config.py`                     | green                          | 5 passed                                                |
| `uv run pytest --collect-only 2>&1 \| grep PytestUnknownMarkWarning` | zero output                    | 0 matches                                               |
| `uv run ruff check src tests conftest.py`                        | clean                          | All checks passed                                       |
| `uv run ty check src tests`                                      | clean                          | All checks passed                                       |
| `git grep -n "@pytest.mark.live\b" -- src tests`                 | empty (decorator audit)        | 0 decorator hits; 2 historical docstring annotations (plan-permitted) |
| `grep -n '"live"' pyproject.toml`                                | empty                          | 0 matches                                               |

## three-factor-bypass-isolation

| Sub-check | Env state                                          | Command                                                                                  | Expected | Result |
| :-------- | :------------------------------------------------- | :--------------------------------------------------------------------------------------- | :------- | :----- |
| 6.1a      | no env, non-TTY                                    | `uv run pytest --collect-only src/aeat/adapters/outbound/aeat/export/ -m live_write -q`                    | 0        | 0      |
| 6.1b      | both env set, non-TTY                              | `AEAT_LIVE_WRITE_UNSAFE_BYPASS=1 AEAT_LIVE_WRITE_UNSAFE_BYPASS_CONFIRM="..." uv run ...` | 0        | 0      |
| 6.1c      | both env set + interactive TTY (manual-only)       | (documented in tests/README.md for human execution)                                       | positive | deferred to operator |
| 6.1d      | confirm phrase alone, non-TTY                      | `AEAT_LIVE_WRITE_UNSAFE_BYPASS_CONFIRM="..." uv run ...`                                  | 0        | 0      |
| 6.1e      | bypass env alone, non-TTY                          | `AEAT_LIVE_WRITE_UNSAFE_BYPASS=1 uv run ...`                                              | 0        | 0      |

6.1c is out of automated scope; the positive-path collection requires a human operator in an interactive terminal.

## charter-invariants-preserved

- `git diff src/aeat/adapters/outbound/aeat/export/_engine.py` -> empty. Charter R5 runtime refusal byte-identical.
- `git diff src/aeat/config.py` shows only: two additive new fields, plus a cosmetic description text change on `aeat_live_tests_enabled` replacing `@pytest.mark.live` with `@pytest.mark.live_read` (no default/name/type changes, no touching of `aeat_live_submit_enabled`). Charter R3 invariants preserved.
- `grep -n "aeat_live_submit_enabled" src/aeat/config.py env/.env.example` returns identical lines to pre-refactor: the env gate is untouched.

## scope-summary

Test-infrastructure refactor only. Production-code touch is strictly:
- two additive Settings fields in `src/aeat/config.py` (mandated by plan for env alignment)
- cosmetic marker-name update in one description string + one .env.example comment + three docstring/prompt references (plan-permitted historical annotations)

Every other file change is either:
- `pyproject.toml` marker table
- test module `pytestmark` header
- new test infrastructure (`conftest.py`, `tests/_marker_hook.py`, `tests/test_marker_integrity.py`, `tests/README.md`)
- `justfile` recipes
- `CLAUDE.md` paragraph

Zero test function bodies were modified.
