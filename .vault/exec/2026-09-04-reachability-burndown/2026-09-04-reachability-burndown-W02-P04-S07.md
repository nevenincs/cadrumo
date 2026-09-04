---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:2621324ef8780403571163297eadca5f6dbdba33c7b8d9afdf4bacaf8df00ff6'
step_id: 'S07'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Adjudicate the staged-capability modules against their authorising decisions and classify or wire each

## Scope

- `src/cadrumo/application`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_reachability_classification.py` -> `pass`

## Notes

Adjudicating the staged-capability population against its authorising decisions moved two
entries out of it and surfaced one defect in a different gate.

The seven that remain stay in the ratchet's `allowed` backlog rather than becoming
`[[intentional]]`, and that is the honest placement. The ratchet's intentional vocabulary
is a closed enum whose sole member is `design_time_authority`, and a module awaiting a
dependency is not one: it is debt that resolves when the dependency lands. Widening the
enum to admit them would be exactly the instrument-weakening this campaign forbids. Each
stays anchored to its accepted decision -- the fincas titularidad record, the modelo edit
contract, the compatibility lifecycle -- so the backlog states what each is waiting for.

`cadrumo.core.address_components` was reclassified to `design-time-authority`. The evidence
recorded against it already said so: it carries that exact kind in the module ratchet, and
the class was assigned before the taxonomy separated the two.

`cadrumo.domain.portals.drift` was reclassified to `should-be-live`, and it is the finding
of this Step. `application.preflight.probe_portal_registry_health` accepts `drift_events`
and grades a divergence by the URL stability tier it was promised, treating a drift on a
BOE-referenced stable-protocol URL as an error. No production caller ever passes them:
`evaluate_portal_drift`, the only producer, is reached solely by tests. The
`portal-registry:health` row therefore always receives the offline default and always
reports OK.

The row's own docstring is honest about the default, so nothing here is a lie. The concern
is that the row cannot distinguish no drift from drift never evaluated, which is the
distinction `no-silent-under-declaration` exists to protect. Reachability found a false
green inside a different gate, which is the strongest argument yet that this signal is
worth burning down rather than baselining.

The remedy is a product behaviour change -- wiring the producer under the live-read access
gate -- so the entry is flagged `remedy_requires_decision` rather than actioned here.
