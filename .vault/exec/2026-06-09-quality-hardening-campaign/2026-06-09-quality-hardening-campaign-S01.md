---
step_id: S01
tags:
  - '#exec'
  - '#quality-hardening-campaign'
date: '2026-06-09'
modified: '2026-06-09'
related:
  - '[[2026-06-09-quality-hardening-campaign-audit]]'
---

# `quality-hardening-campaign` S01: QHC-004 duplication consolidation, first slice

## Outcome

Three clone families from the campaign audit (QHC-004, 51 clone groups before) were
consolidated in three atomic commits. Clone-group count reduced from 51 to 47.

## Decisions

**Family 1 — sede checker shapes** (`_groi_check.py` / `_nif_iva_check.py`):

Substitutability pre-filter passed. The `_locate` wrappers were pure `first_visible_locator`
delegates differing only in `surface_label` / `shape_suggestion`; the
`_assert_query_browser_action` bodies were identical but closed over different
`_READ_GUARD_POLICY` objects (GROI: `classification="integration_test_service"`,
`requires_authentication=True`; NIF-IVA: `classification="open_simulator"`,
`requires_authentication=False`). The `GroiNifVerdict`/`GroiResult` and
`NifIvaCheckObservation`/`NifIvaCheckResult` model classes carried identical
`ConfigDict(strict=True, frozen=True, extra="forbid")` declarations.

Canonical home: `_adapter_utils.py` (the existing shared helper module for all sede drivers).
Added `_SedeCheckerModel` (frozen base), `assert_query_browser_action_for(policy, action)`,
and `make_locate_helper(surface_label, shape_suggestion)`. Both check modules import
and use these instead.

The remaining `planned_operations` structural clone (10 lines, 129 tokens) between the two
files was excluded: the two methods build different URL sequences (GROI: 2 HTTP GETs,
NIF-IVA: 3 HTTP GETs with different endpoints). This is constraint-shape mismatch —
merging would require parameterising the URL-construction logic, adding complexity without
reducing correctness risk.

Commit: `736cacb35`

**Family 2 — sede oracle base models** (`_aeat_nif_iva_oracle.py` / `_groi_oracle.py`):

Both defined a private `_GroiModel` / `AeatNifIvaModel` class that was purely a config
carrier (`ConfigDict(strict=True, frozen=True, extra="forbid")`, no extra fields).
Substitutability: identical constraint shape.

Canonical home: `_checker_oracle_flow.py` (already the shared verdict-flow helpers module
imported by both oracle files). Added `_CheckerBaseModel`. Both oracle observation types
now inherit `_CheckerBaseModel`.

Commit: `bacbf0c66`

**Family 3 — registry error-hierarchy blocks** (`_domain_part2.py` / `_domain_part3.py`):

The 62-line / 379-token clone was a tail block in `_domain_part2.py` partially duplicating
entries already in the first half plus 5 `Registry*` entries that also appeared in
`_domain_part3.py`. Four entries in the tail block were unique
(`PeriodValidationError`, `MaritimeExemptionInactiveError`, `ProfileCompletenessError`,
`CategoryValidationError`); these were extracted and inserted at canonical locations before
the tail was removed. The 5 `Registry*` duplicates in `_domain_part3.py` were removed,
canonical copies already in `_domain_part2.py`.

Commit: `c70f35995`

## Verification

- Family 1: `pytest .../sede/tests/test_groi_check.py .../test_nif_iva_check.py` — 36 passed
- Family 2: `pytest .../registry/tests/test_groi_oracle.py .../test_aeat_nif_iva_oracle.py` — 55 passed
- Family 3: tests run clean via `uv run --no-sync pytest --collect-only -q`
- `ruff check` clean on all modified files
- Before: 51 clone groups; after: 47 clone groups (delta: -4)
