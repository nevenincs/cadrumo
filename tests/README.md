# aeat tests

Operator reference for the nine-marker pytest taxonomy and the
three-factor live-write bypass. See charter `#116` (live-AEAT-write
safety charter) and `.vault/adr/2026-04-17-pytest-markers-adr.md` for
the authoritative specification; this file is the operator-facing
summary.

## Marker taxonomy

Every test module declares module-level markers via a single
`pytestmark = [...]` assignment placed immediately after the module
docstring and imports:

```python
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]
```

Per-function access or domain markers are forbidden. Mixed-access
modules (for example one `unit` function next to one `live_read`
function) must be split into two files rather than overridden per
function.

### Axis A - access level (mutually exclusive; exactly one per test)

| Marker       | Semantics                                                                 | Selection example                        |
| :----------- | :------------------------------------------------------------------------ | :--------------------------------------- |
| `unit`       | Deterministic, no external I/O. Mocks and stubs are permitted.            | `uv run pytest -m unit` (default)        |
| `live_read`  | Talks to a real external service with read-shaped operations only.        | `uv run pytest -m live_read`             |
| `live_write` | Talks to a real external service with write-shaped operations. **Banned.** | `uv run pytest -m live_write` (see below) |

### Axis B - domain (at least one per test)

| Marker                   | Covers                                                                            | Selection example                                |
| :----------------------- | :-------------------------------------------------------------------------------- | :----------------------------------------------- |
| `domain_aeat_remote`     | `auth`, `browser`, `casillas`, `inbox`, `justificante`, `portals`, `status`, `sync` | `uv run pytest -m "unit and domain_aeat_remote"` |
| `domain_submission`      | `filing`, `submission` (the AEAT-write-capable boundary)                           | `uv run pytest -m "unit and domain_submission"`  |
| `domain_financial_input` | `financial`, `cli/financial`                                                       | `just test-domain financial_input`               |
| `domain_local_state`     | `storage`, `models`, `normatives`, `manuals`, `corpus`, `schema`, `deadlines`     | `just test-domain local_state`                   |
| `domain_mediation`       | `workflow`, `llm`, `i18n`, `testing`                                              | `just test-domain mediation`                     |
| `domain_infra`           | root modules, non-domain `cli`, `setup`, top-level `tests/*.py`                    | `just test-domain infra`                         |

## Module-level mandate

`tests/test_marker_integrity.py` walks every `test_*.py` and
`_test_*.py` module under `src/aeat/` and `tests/` via `ast` and fails
CI if any module lacks a compliant `pytestmark` assignment. The
collection hook in the repo-root `conftest.py` additionally raises
`pytest.UsageError` at collection time if an item surfaces with zero
or more than one access marker or with no domain marker. Both guards
are in place because module-level declarations are the only shape
that yields predictable marker inheritance under pytest.

## live_write ban

`@pytest.mark.live_write` items are **dropped** (not skipped) from the
collection by default. Drop-not-skip is intentional: skipped items
surface in pytest reports as "would have run if unskipped" and are a
single env-var flip away from executing. Dropped items are invisible
downstream of collection and cannot be reinstated by any marker-
expression flag.

Zero `live_write` tests exist in the repository today. The marker,
the collection ban, and this documentation are dormant infrastructure
shipped so any future write-shaped probe is required to carry the
marker and is collection-banned by default. Charter `#116` R1 is
absolute: no automated test may ever produce a legally binding AEAT
filing.

### Three-factor bypass

All three factors must hold simultaneously for `live_write` items to
survive collection. Missing any one factor drops the item silently:

1. `AEAT_LIVE_WRITE_UNSAFE_BYPASS=1` in the process environment.
2. `AEAT_LIVE_WRITE_UNSAFE_BYPASS_CONFIRM` in the environment, equal
   byte-for-byte to the phrase:

   `I ACCEPT THE RISK OF FILING A LIVE TAX RETURN`

3. `sys.stdin.isatty()` returns truthy (attached to an interactive
   terminal).

Setting the bypass does **NOT** enable a live submission. Charter
`#116` R3 (`AEAT_LIVE_SUBMIT_ENABLED` env gate) and R5
(`SubmissionEngine.__init__` runtime refusal under
`PYTEST_CURRENT_TEST`) remain the canonical write-prevention guards;
the collection ban is additive defence in depth. A `live_write` item
that survives collection still has to satisfy both R3 and R5 before
any write-shaped call can execute.

### Bypass incantation (DO NOT RUN unless you are about to file a legally binding tax return)

Run only from an interactive terminal, only when you genuinely intend
to exercise a live-write test against real AEAT infrastructure:

```bash
AEAT_LIVE_WRITE_UNSAFE_BYPASS=1 \
AEAT_LIVE_WRITE_UNSAFE_BYPASS_CONFIRM="I ACCEPT THE RISK OF FILING A LIVE TAX RETURN" \
uv run pytest -m live_write
```

PowerShell equivalent:

```powershell
$env:AEAT_LIVE_WRITE_UNSAFE_BYPASS = "1"
$env:AEAT_LIVE_WRITE_UNSAFE_BYPASS_CONFIRM = "I ACCEPT THE RISK OF FILING A LIVE TAX RETURN"
uv run pytest -m live_write
```

**DO NOT RUN** this command unless you are about to file a legally
binding tax return. The bypass env vars must never appear in CI
configuration, cron jobs, shared `.env` files, or any non-interactive
automation.

## Cross-references

- Charter `#116` - rules R1..R6 governing the live-write path.
- `.vault/adr/2026-04-17-pytest-markers-adr.md` - the marker taxonomy decision.
- `scripts/README.md` - Google Workspace fixture provisioning for `live_read` tests.
- `CLAUDE.md` - trilingual testing contract and module-layout mandate.
