---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S17'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---




# unify the three ADR-R2 revision-carry gate copies onto one shared path consumed by the binding-prefill, cross-period clean-state, and relation-prefill callers

## Scope

- `src/aeat/application/calculations/_binding_prefill.py`
- `src/aeat/application/calculations/_cross_period_clean_state.py`
- `src/aeat/application/calculations/_relation_prefill.py`

## Description

- Extract one shared ADR-R2 carry gate `revision_carry_outcome` into a new `_revision_carry_gate.py` helper, returning `(diverges, advisory)` from `(stamped_revision_id, source_modelo, source_filing_year, source_period)` — the single law-determined re-confirmation.
- Reduce `_binding_prefill._revision_carry_outcome` to a thin adapter that extracts the source context off the payload's observation and delegates to the shared gate.
- Reduce `_cross_period_clean_state._revision_carry_check` to a thin adapter that maps the shared `(diverges, advisory)` onto its blocker shape (divergence becomes `REGISTRY_REVISION_DIVERGENCE`); drop the now-unused resources import.
- Route `_relation_prefill._gather_observations_for_snapshot` through the shared gate so a divergent-stamp prior is dropped from the relation fold, closing a re-confirmation gap the relation path was missing.

## Outcome

The ADR-R2 carry decision now lives in one function consumed by all three carry-read sites. The two adapters preserve their existing return shapes and semantics; the relation path gains the divergent-stamp drop consistent with the binding-prefill site.

## Notes

The two real prior implementations (binding-prefill and cross-period clean-state) were behaviour-identical and are now unified verbatim. The relation-prefill gather previously discarded the payload stamp entirely and never re-confirmed it; routing it through the shared gate adds the divergent-stamp drop the `carried-observations-stamp-their-revision` rule requires at every carry read. Mesh enrollment and ownership untouched.
