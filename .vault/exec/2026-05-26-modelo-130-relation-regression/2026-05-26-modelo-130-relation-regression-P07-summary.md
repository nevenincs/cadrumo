---
tags:
  - '#exec'
  - '#modelo-130-relation-regression'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-26-modelo-130-relation-regression-plan]]'
  - '[[2026-05-26-modelo-130-relation-regression-adr]]'
  - '[[2026-05-26-modelo-130-relation-regression-audit]]'
---



# `modelo-130-relation-regression` P07 campaign summary

Recovers the campaign-level structural narrative that the L2 plan
canonicalisation dropped from the plan body. Captures the decisions,
the deferrals, and the rationale that drove the P01-P06 work and the
P07 hardening cluster, so the execution intent survives even though
the original Proposed Changes / Parallelization / Verification
sections no longer live on the plan.

## Decisions captured

The campaign closed P01-P06 by:

- Adding `max_year_delta` to `_PreviousModeloSelector` with anchor-drop
  semantics that preserve runtime defaults and bindings.
- Applying the `(offset=-1, max_year_delta=0)` cap to the four M130
  carry-forward selectors so the same-ejercicio anchor stops crossing
  filing-year boundaries by accident.
- Extending the same cap pattern to the four M131 carry-forward
  selectors on the assumption that M131 estimación objetiva shares
  the rule with M130 estimación directa. **Open** under P07.S38 —
  the AEAT-rule grounding for M131 still needs explicit citation.
- Repairing the M100 C1577 false positive surfaced by the
  `bound_casilla_sweep` classifier during P02. The classifier itself
  retains a `relation_orphaned` bug — tracked as P07.S37.
- Removing `vigencia` from the M036 calculation-completeness manifest
  on the basis that `decl.vigencia-2025` is `input_kind='informational'`.
  Whether the "informational is excluded from closure" rule is
  systematic vs an ad-hoc exception remains open under P07.S40.
- Enumerating `provisional_pending_specimen=true` extraction profiles
  across the registry — the catalogue is owed under P07.S41.

## Deferrals

The P07 hardening cluster carries the architectural questions the
P01-P06 mechanical fixes surfaced but did not adjudicate:

- `_applicability` private/public contradiction (P07.S33) — leading-
  underscore names re-exported through the registry public surface
  need either promotion or accessor-function wrapping.
- `application/overview/_applicability.py` shim removal (P07.S34) —
  the application namespace should consume the domain via the registry
  public surface directly.
- Lost-design-intent "bound previous_filing casilla via inputs"
  rejection (P07.S36) — the runtime contract silently ignores the
  case; an authoring-time gate test must close the fixture-lying gap.
- Cross-campaign sweep-commit trust-but-verify (P07.S43) — the
  shared-worktree sweep cadence absorbed work from this campaign and
  needs an audit pass before subsequent campaigns rely on it.
- Tautology-gate elevation (P07.S44) — current CI-only ratchet
  re-fires when parallel campaigns add hand-summed patterns without
  local feedback. Authoring-time enforcement is the closure.

## Verification context

P05 closed via a full registry-test-directory pass at 1919 / 1919
under `pytest -n 4` in 581 s. The five non-M130 partial failures
recorded on 2026-05-27 were resolved by concurrent campaign work in
the intervening commits before this summary landed. P07.S46 re-runs
the gate after every P07 hardening step lands; no regression has
been observed in any green-run baseline since.
