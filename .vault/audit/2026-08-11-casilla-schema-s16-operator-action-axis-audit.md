---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:ea80c896b5b17128429b2a8bf7c8c2bb143249fd7de0f73bc44837009b59b673'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-blocker-spine-adr]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S16 operator action axis`

## Scope

Reviewed W02.P06.S16 against the accepted blocker-spine decision, campaign plan, research, and repository quality constraints. Scope was limited to `_operator_action_enums.py`, the core facade, and `test_operator_action_axis.py`. The required contract is one core-owned `OperatorActionAxis` `StrEnum` seeded with exactly the twelve accepted action classes and wire values, directly exported through the core facade, with no alias, duplicate declaration, projection mapping, or consumer introduced in this step.

## Findings

No actionable findings.

`OperatorActionAxis` is declared once beside the existing operator-action contract enums and contains the accepted twelve-member seed in decision order: manual input, ledger import, profile fact, prior-period filing, external evidence capture, value-divergence resolution, re-verification, revision-mismatch resolution, group-membership confirmation, identity resolution, document-evidence completion, and advisory review. Every member value is the exact snake-case wire token accepted by the ADR. The twelve values are unique.

The owner module exposes the enum in its `__all__`; the core facade imports that owner directly and exposes the same class identity in its public `__all__`. Exact reference inspection found no production occurrence beyond the declaration and facade, so S16 does not prematurely introduce any mapping table, projection, compatibility alias, or consumer that belongs to later steps.

The structural test asserts facade identity, exact ordered `__members__` names, exact ordered values, and sole AST declaration across the package. Using `__members__` makes an added same-valued alias observable. The supplied bite proof removed `REVIEW_ADVISORY`, made the exact membership test fail, restored the member, and returned the focused test to green. No scoped test uses a fake, stub, mock, patch, monkeypatch, skip, or expected-failure construct.

## Verification

- Fresh semantic discovery located the core owner and accepted blocker-spine decision before exact inspection. The code index disclosed eight missing sections; the subsequent exact package-wide symbol sweep supplied the negative-evidence check for duplicates and consumers.
- Focused core test: 1 passed.
- Scoped Ruff: passed.
- Scoped BasedPyright: 0 errors, 0 warnings, 0 notes.
- Scoped `git diff --check`: passed, with only the existing facade line-ending warning.
- Runtime facade identity, exact names, and twelve unique values: passed.
- Exact symbol sweep: one declaration, one owner export, one facade import, one facade export, and the scoped test references only.
- AST sole-declaration gate: passed.
- Mutation bite: removing `REVIEW_ADVISORY` failed exact membership; restoration passed.
- Prohibited test-construct scan: no hits.

## Recommendations

No corrective action is required for S16. Keep projection mappings out of this landing; later steps must add each mapping beside its native vocabulary with totality asserted at import, as the accepted decision requires.

Verdict: **PASS.** W02.P06.S16 establishes the sole public core action-axis identity with exactly the accepted twelve seed members and no alias, duplicate authority, mapping, or compatibility surface.
