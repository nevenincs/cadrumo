---
tags:
  - '#exec'
  - '#arch-remediation-lazy-import-policy'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:a326d42e6da6004fc9bd63bd0ddb48c1aa8bc9c42866f6f2f3719e29dcfd8ad9'
step_id: 'S01'
related:
  - "[[2026-07-02-arch-remediation-lazy-import-policy-plan]]"
---

# Declare the typed lazy-import allowlist entry model carrying site, sanctioned class, reason, and restructuring disposition co-located with the gate

## Scope

- `src/aeat/tests/test_lazy_import_policy.py`

## Description

- Declare the typed allowlist entry model in `src/aeat/tests/test_lazy_import_policy.py`: an `ImportEdge` NamedTuple (aeat-relative consumer module, imported module) is the site key; a closed `UnsanctionedClass` StrEnum is the class; a `_CLASS_METADATA` mapping fixes each class's reason and `Disposition` (delete-via-ports-inversion, restructure-cycle, keep-bootstrap, pending-review).
- Declare the `SanctionedClass` StrEnum naming the five inherited classes surfaced verbatim in a gate failure.

## Outcome

The typed model carries the four required facets per entry (site, class, reason, disposition). Reason and disposition are attached to the `UnsanctionedClass` member so every edge filed under it inherits a complete, honest classification without hand-authoring 655 individual prose reasons.

## Notes

The two named sites (the core error-registry deferred-bind queue and the `application/overview/_coverage` cycle break) carry their existing ADR citations in their class metadata.
