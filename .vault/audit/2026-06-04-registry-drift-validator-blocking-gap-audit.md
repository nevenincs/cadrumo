---
tags:
  - '#audit'
  - '#registry-drift-validator-blocking-gap'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-registry-drift-validator-blocking-gap-plan]]'
  - '[[2026-06-04-registry-remaining-hardening-wireframe-audit]]'
---

# `registry-drift-validator-blocking-gap` audit: `S01 advisory gate inventory`

## Scope

Audit registry drift validators that still expose advisory or warning-only
signals and select one candidate where the next slice should make drift block
snapshot validation.

## Inventory

### Cross-revision non-overlap drift

- Surface: `_validate_cross_revision_advisory.py`.
- Entry point:
  `summarize_non_overlapping_cross_revision_casilla_drift`.
- Current gate:
  `_validate_cross_revision_casilla_consistency` hard-fails overlapping
  revision windows, while `_validate_strict_cross_revision_casilla_continuity`
  hard-fails non-overlapping continuity surfaces only when
  `continuidad_validation = "strict"` and the casilla has an authored
  continuity surface.
- Status: keep advisory for this slice. The code has an explicit policy
  comment that unannotated repeated-id non-overlap drift remains advisory
  until a corpus-wide continuity completeness gate exists. Tests already cover
  advisory inventory, strict continuity failures, strict covered drift, and
  committed M100 continuity surfaces.

### Semantic-role typo twins

- Surface: `_validate_semantic_role_typos.py`.
- Entry point:
  `emit_grouped_semantic_role_typo_twin_warnings`, called by
  `_emit_semantic_role_typo_twin_warnings` from `validate_registry_scope`.
- Current gate: emits `UserWarning` for a singleton role that looks like a typo
  of another role, unless the casilla declares
  `semantic_role_cardinality = "intentional_singleton"`.
- Existing guard: `test_singleton_semantic_role_warning_count_does_not_regress`
  asserts the committed corpus emits zero singleton typo warnings.
- Status: selected blocking-gap candidate. The corpus baseline is already zero,
  explicit singleton metadata exists for legally reviewed one-off roles, and a
  future typo-like singleton role would be an authoring error. Warning-only
  behavior means production registry validation can succeed while emitting a
  warning the caller may not treat as fatal.

## Candidate

Convert semantic-role typo-twin findings from warning-only behavior into
registry validation failures while preserving the public warning helper for
tests or diagnostic callers.

## Regression approach

No real-corpus drift is currently present; use a synthetic mutation built from
real schema objects. The focused regression should create two similar semantic
roles, one singleton typo-like role and one canonical sibling role, then assert
`RegistryValidator.validate_registry` raises `RegistryValidationError` for the
typo-like role instead of only warning.

## Subagent note

An explorer subagent was attempted for sidecar discovery, but the active
subagent pool was at the thread limit. The audit proceeded locally and should
receive the normal S05 code-review pass before closure.
