---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S600'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# `codebase-solidification` `W13.P45.S600-S606`

P45 W13-finding closure: 7 rationale-marker and structural-hygiene Steps.

- Modified: `src/aeat/domain/deadlines/_plazo.py` (S600)
- Modified: `src/aeat/adapters/inbound/financial/providers/_xlsx.py` (S601)
- Modified: `src/aeat/core/observability/_sink.py` (S602)
- Modified: `src/aeat/entrypoints/cli/_ledger.py` (S603)
- Modified: `src/aeat/adapters/outbound/llm/_cache.py` (S604)
- Modified: `src/aeat/domain/calculations/registry/_schedules.py` (S605)
- Created: `src/aeat/test_w13_p45_closure.py` (S606)

## S600 — _plazo.py exception narrowing

Removed redundant `except (RegistryError, Exception):  # noqa: BLE001`.
Narrowed to `except RegistryError:`. The `Exception` catch was a superset
of `RegistryError` and masked all non-registry failures silently via
`continue`. Post-condition: bare `except (RegistryError, Exception)` absent.

## S601 — _xlsx.py second BROAD-EXCEPT-RATIONALE-XLSX-TEARDOWN site

Added `BROAD-EXCEPT-RATIONALE-XLSX-TEARDOWN` marker to the
`validate_source` workbook close teardown at line 96 (sibling of the
`_locate_sheet` site at line 189 from W09). W09 ratchet
`test_financial_provider_teardown_broad_except_carry_rationale` still
passes (single-token scan covers both sites).

## S602 — _sink.py LOGGING-STDLIB-RATIONALE-SINK-HANDLER

Added inline marker on `import logging` explaining that `JsonlRunSink`
subclasses `logging.Handler` and accepts `logging.LogRecord`; stdlib
import is required by the ABC contract. `_sink.py` enrolled as a
logging-survivor alongside `_stdio.py`.

## S603 — _ledger.py MACHINE-FORMAT-RATIONALE-LEDGER-BULK-CLASSIFY-FAILURE

Added inline rationale marker to the bulk-classify failure tab-record
line, mirroring the W12 `MACHINE-FORMAT-RATIONALE-SECURE-OBJECTS-ROW`
precedent.

## S604 — _cache.py JSON-LOADS-RATIONALE-LLM-CACHE-SECURE-OBJECT

Design choice: marker over thin pydantic envelope. `_entry_from_payload`
already re-validates through `CachedEntry.model_validate_json`; the type
is guarded at storage boundary. Wrapping the intermediate dict in a second
pydantic model adds overhead with no safety gain here.

## S605 — _schedules.py Final path constants

Extracted `_IVA_REGIME_PATH: Final[str] = "iva.regime"` and
`_TAXPAYER_ENTITY_TYPE_PATH: Final[str] = "taxpayer.entity_type"` as
module-level constants. Migrated both usages in `_resolve_profile_fact`.
`from typing import Final` added to stdlib import block.

## S606 — Aggregate closure test

`src/aeat/test_w13_p45_closure.py` — 9 assertions covering all 7 Steps.
All pass. W09 ratchet and W12 finisher suites still green.
