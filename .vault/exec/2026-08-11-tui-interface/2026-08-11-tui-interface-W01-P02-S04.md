---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:234906de2f79cf60a7a295a5350eed18d717caebb1a70cdbd7981cd5a7a1e89a'
step_id: 'S04'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Define typed profile presentation states for static requiredness conditional applicability filing preflight readiness relevance source provenance conflicts and explicit unknowns

## Scope

- `src/cadrumo/application/user_profile/presentation.py`

## Changes

- `A` `src/cadrumo/application/user_profile/presentation.py`
- `verify:` `pytest src/cadrumo/application/user_profile/tests/test_presentation.py -m integration` -> `pass` (9 passed)

## Notes

Landed as `presentation.py`, not `_overview.py` as the Step row names: that
path collides with the already-existing PUBLIC `overview.py` (a distinct,
narrower schema-completeness/masking projection with no
requiredness/applicability/provenance/conflict concepts). `_overview.py`
would also violate `aeat-naming`'s instruction that two concepts sharing a
name get the non-canonical one renamed. Reported and confirmed before
implementing.

Scope for this pass, stated in the module docstring: conditional-applicability
resolution covers only the named trigger paths in `_CONDITIONAL_TRIGGERS`
(`auth.clave_movil_route`, the legal-entity fields, the IRNR
fiscal-representative fields) and non-repeatable sections; the IVA-regime
conditional block and repeatable sections present as `OPTIONAL` rather than
being assessed for applicability, since their trigger conditions are
multi-field. The `Review` stage's unresolved-proposal/conflict row is not
built here -- it is produced by whichever registered acquisition/reconciliation
operation proposes the divergence, not by this static per-field projection;
`ADVISORY_NOTICE` and `UNRESOLVED_CONFLICT` are declared absent from
`ProfileFieldClassification` for the same reason, documented on the enum.
