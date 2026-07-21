---
tags:
  - '#exec'
  - '#arch-remediation-source-kind-deferrals'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-07-02-arch-remediation-source-kind-deferrals-plan]]"
---

# Add the structured owner-and-trigger annotation type on the deferred source-kind declaration carrying the owning ADR stem and the promotion trigger condition, annotations only per the Wave 1 freeze

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Add the typed `DeferredSourceTarget` NamedTuple (owning_adr, trigger, optional structured `promotion_depends_on`) on the deferral declaration in `_source_mesh.py`.

## Outcome

The deferral set gains a typed governance carrier; `DEFERRED_SOURCE_KINDS` is now derived from the annotated `DEFERRED_SOURCE_KIND_TARGETS` mapping so membership and governance cannot diverge.

## Notes
