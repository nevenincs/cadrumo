---
tags:
  - "#exec"
  - "#pytest-markers"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-pytest-markers-plan]]"
  - "[[2026-04-17-pytest-markers-adr]]"
---

# pytest-markers phase-2 step-1

## add-settings-fields-and-mirror-env-example

Added two additive `Field(default=..., description=...)` entries to `aeat.core.config.Settings` under a new `── Live-write bypass (charter #116 R1) ──` header:

- `aeat_live_write_unsafe_bypass: bool = Field(default=False, description="UNSAFE. Pytest collection bypass factor 1 of 3 ...")`
- `aeat_live_write_unsafe_bypass_confirm: str = Field(default="", description="UNSAFE. Pytest collection bypass factor 2 of 3 ... I ACCEPT THE RISK OF FILING A LIVE TAX RETURN ...")`

Mirrored both in `env/.env.example` under a `-- Live-write bypass (charter #116 R1) --` block with the same warning copy plus an explicit "NEVER set in CI or cron" line.

Additionally retouched the description text on `aeat_live_tests_enabled` and its `.env.example` mirror so the prose says `@pytest.mark.live_read` instead of `@pytest.mark.live` (cosmetic; field name, default, and env var name unchanged). `aeat_live_submit_enabled` is untouched.

Files touched:
- `src/aeat/config.py`
- `env/.env.example`

## verification

- `uv run pytest tests/test_config.py -m unit` -> 6 passed (env-alignment holds).
- `grep -n "AEAT_LIVE_WRITE_UNSAFE_BYPASS" env/.env.example src/aeat/config.py` shows both sides present.
