---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:ad343fce03fa64a77865a45608dbb340f7cdb09b7745f5054a65440c42271cf1'
step_id: 'S06'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# declare `AeatExpedienteId` at the sede-schema bound and `AeatClaveLiquidacion` and `AeatPresentationId` at their current field bounds

## Scope

- `src/cadrumo/core/identity/__init__.py`
- `src/cadrumo/core/identity/_namespace.py`
- `src/cadrumo/core/identity/tests/test_namespace.py`
- `src/cadrumo/domain/justificante/_schema.py`

## Description

- Declare `AeatExpedienteId` carrying the 12-32 window and the AEAT shape pattern, taken verbatim from the sede boundary rather than tightened toward the observed range.
- Declare `AeatClaveLiquidacion` at its length bound only, with no pattern asserted.
- Declare `AeatPresentationId` at the receipt boundary's existing bound, with no minimum.
- Promote all three plus the enum through the identity facade and its `__all__`, and cross-link the new surface from the module docstring.
- Retype the sole production `presentation_id` field onto `AeatPresentationId`.
- Add real-behaviour coverage for all three aliases and for the enum's group partition.

## Outcome

Landed in `c272504f9d`.

The expediente window is deliberately wider than every capture on both sides, because the bound is an observed range on external behaviour AEAT has never published. A narrower bound would refuse a real expediente, and the artefact it refused would be filing evidence.

Coverage pins the alias against a captured value rather than a synthetic one, and asserts that a fifteen-character value inside the length window still refuses. That single assertion is what separates "the alias carries a pattern" from "the alias carries a length", and an independent re-derivation found five such pattern-only refusals rather than the one originally claimed.

The enum test asserts a partition property rather than a member count, so adding a namespace does not require editing it while a member belonging to neither group fails.

## Notes

**A dormant alias is a shadow of the declaration it was meant to replace.** `AeatPresentationId` was initially declared with zero consumers while the real bare-`str` declaration remained live, which is the fragmentation this campaign exists to close, newly created by this campaign. It was closed in the same commit: identical bound, sole site tree-wide, no literal exceeding it. The general lesson is to land an alias and its first consumer together, or not to declare it yet.

**Both `AeatClaveLiquidacion` and `AeatPresentationId` admit values their surfaces should refuse** — a whitespace-only clave and an empty presentation id respectively. Both gaps are documented in the aliases' own docstrings and asserted by tests, so that a later reader sees them as measured rather than overlooked, and so that deleting the separate boundary guard that really refuses them fails a test. Closing the gaps in the alias would have tightened beyond the bound each surface carries today, which this campaign refuses to do without evidence.
