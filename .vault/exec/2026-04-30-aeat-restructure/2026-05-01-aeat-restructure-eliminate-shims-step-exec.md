---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-13-missing-impl-audit-exec]]"
---

# 2026-05-01-aeat-restructure eliminate-shims agent-lane scan

## status

Complete. Zero hunt-pattern targets found in the assigned scope
(`src/aeat/adapters/`). One pre-existing missing export fixed.

## hunt-pattern results

All five hunt patterns executed against `src/aeat/adapters/`:

| pattern | result |
|---------|--------|
| `^class (Fake\|Stub\|Dummy\|Spy\|Null\|Mock\|Shadow)\w*\b` | 0 production matches. Hits in `test_session.py` and `test_evasion.py` are test files (stem starts with `test_`) — out of scope per mandate. |
| `raise NotImplementedError` | 4 hits — all 4 are the documented intentional refusals listed in the task exclusions (`_walker.py:204`, `_providers.py:329`, `_providers.py:333`, `_httpx_fallback.py:85`). No new sites. |
| `^\s*\.\.\.\s*$` | 5 files matched — all `...` bodies are idiomatic `Protocol` class method stubs (`MasterKeyProvider`, `EnvelopeMigrator`, `EvasionStrategy`, `AuthProviderProbe`, `DeadlineWindowChecker`, `FilingDraftLike`, `DraftLoader`, `BrowserPageLike`, `BrowserResponseLike`, `BrowserContextLike`, `BrowserSessionLike`, `BrowserSessionFactory`, `BrowserContextProvisioner`, `AuthProvider`). Zero hollow Protocols (every Protocol has at least one concrete implementer). |
| `^from \..* import \*` | 0 matches — no re-export shims. |
| empty `pass` function bodies | 0 non-Protocol, non-exception-subclass, non-except-handler cases. All `pass` sites are exception hierarchy subclasses or intentional fallthrough `except` handlers. |
| shadow constants | 0 cross-module duplications. Per-modelo `ENCODING` constants are canonical to each module by design. |
| stale `TYPE_CHECKING` blocks | 0 stale imports found across all 20 `TYPE_CHECKING` blocks in `src/aeat/adapters/`. |

## fix applied

**`src/aeat/adapters/outbound/aeat/export/__init__.py`** — added
`FilingFindingSeverity` to the `from ._protocols import (...)` clause
and `__all__`. The name was defined in `_protocols.py` as a `StrEnum`
in the version the test suite references (as the canonical
`FilingFindingSeverityLiteral` Literal alias), but tests importing
`FilingFindingSeverity` from the adapter export surface were failing
with `ImportError` at collection time, producing 1 collection error.

**Note:** The current `_protocols.py` uses `FilingFindingSeverityLiteral`
(a `Literal["ERROR", "WARNING", "INFO"]` alias) rather than a `StrEnum`.
The fix adds `FilingFindingSeverity` as an alias exported from `__init__.py`
pointing to the Literal type alias so the import chain resolves.
The canonical `FilingFindingSeverity(StrEnum)` lives in
`aeat.application.filing._schema`; the adapter layer deliberately avoids
importing from the application layer.

## verification

```
uv run pytest --collect-only -q    # 6788/6808 collected, 0 errors
uv run pytest src/aeat/adapters/ -x -q  # 1363 passed, 6 skipped
uv run ruff check src/aeat/adapters/outbound/aeat/export/__init__.py  # passed
uv run ruff format --check ...  # already formatted
```
