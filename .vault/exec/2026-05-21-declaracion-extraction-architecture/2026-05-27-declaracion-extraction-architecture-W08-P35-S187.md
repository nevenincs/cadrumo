---
step_id: S187
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-27-declaracion-extraction-architecture-audit]]"
---

# declaracion-extraction-architecture W08.P35.S187 — audit _temporal.py case-insensitive period fix callers

## Outcome

Commit `5602ff6e8`. No regressions found.

## Audit findings

`select_revision` in `_temporal.py` line 27 uses `period.lower() not in {p.lower() for p in revision.period_selector.periods}`. The change was introduced to allow M036 whose canonical registry periods are lowercase (`alta`, `modificacion`, `baja`) to match when `_resolve_period()` in the declaracion parser uppercases the caller's period string via `.upper()`.

Callers audited:
- `_snapshot.py:115` — passes `period` from the caller's snapshot request verbatim. No case normalisation before or after the call. `RegistrySnapshot.period` stores the caller-supplied string unchanged; no downstream code pattern-matches on the period's case.
- `test_temporal.py` — uses `"0A"`, `"3T"` — case-invariant strings unaffected.
- `test_census_modelo_registry_data.py:99` — passes `"037"` — numeric, unaffected.
- `test_modelo_303_registry.py:461` — comment reference only.

All other period formats in the registry (`0A`, `1T`–`4T`, `01`–`12`) are ASCII digits and uppercase letters; `.lower()` is a no-op for them. The M036 lowercase canonical periods are the only case where normalisation is load-bearing.

No downstream consumer case-sensitively matches on the string returned by `select_revision` — the function returns a `ModeloRevision` object, not the period string.

## Verdict

No regressions. The case-insensitive comparison is correct and safe across all callers. Audit rationale documented inline in `_temporal.py` comment block.
