---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-07'
modified: '2026-07-08'
step_id: 'S07'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Add the interrupted-ejercicio marker/provenance to the register enums and the active/inactive history on ProrrataRegisterEntry

## Scope

- `src/aeat/core/_prorrata_register.py`
- `src/aeat/domain/prorrata_register/__init__.py`

## Description

- Add the `INTERRUMPIDA_TRES_ULTIMOS` member to the core `ProrrataProvisionalProvenance` enum for the art-105.Cinco resumption seed.
- Add an `interrupted` (sin operaciones) boolean marker to `ProrrataRegisterEntry`, distinct from the `ninguna` regime (an active 100%-definitive year), so the register carries a truthful active/inactive history.
- Validate that an interrupted ejercicio carries no provisional/definitive percentage, no volume inputs, no authorisation, and no source-observation reference (it had no operations).
- Enroll `INTERRUMPIDA_TRES_ULTIMOS` in the precedence ladder so the resumed year's seed resolves.
- Add tests: an interrupted entry JSON-roundtrips carrying no percentages; an interrupted entry with settlement fields is refused; the INTERRUMPIDA provenance resolves in the ladder.

## Outcome

- Modified files: `src/aeat/core/_prorrata_register.py`, `src/aeat/domain/prorrata_register/__init__.py`, `src/aeat/domain/prorrata_register/tests/test_prorrata_register.py`.
- 36 domain + application prorrata_register tests pass; ruff / ruff-format / ty clean.
- The `interrupted` marker defaults `False`, so previously-stored registers load unchanged (forward-functional default, no migration).
- Committed atomically with this exec record and the plan step check.

## Notes

- The marker is deliberately distinct from `ProrrataRegisterRegime.NINGUNA`: `ninguna` is an ACTIVE year under no prorrata (LIVA art. 94 full deduction), whereas `interrupted` means the taxpayer performed NO operations; conflating them would corrupt the three-active-years walk (S08).
- No exhaustive match on the provenance enum needed updating; the new member is additive.
