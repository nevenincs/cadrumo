---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-06'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:c78e3e151324a28d476e93fe53e3aceebafa93cf07340767e4248915199d67c9'
step_id: 'S19'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# State in the filing-period consistency validator's own docstring which coordinates it no longer covers and why, a test enforces the fact but the explanation belongs at the validator

## Scope

- `src/cadrumo/domain/calculations/registry`

## Description

- Name the third coordinate class the filing-period consistency check skips, in the validator's own docstring.
- Enumerate the complete skipped set against the live registry rather than reasoning about it.

## Outcome

Landed as `8986d07d7a` ("docs(registry): name the third coordinate class the filing-period
check skips"), 10 insertions and no deletions to
`src/cadrumo/domain/calculations/registry/_schema.py`. Executed by the campaign's driving
agent; this record is written from the artefact by the reviewer, because the row had landed
work, no exec record, and an unchecked box — the reconciliation gap this campaign's honesty
review was commissioned to find.

The docstring previously named the administrative censo tokens as the coordinates whose
snapshots carry no filing period. It omitted Modelo 210's symbolic `EVENT-N`, which skips the
check for a different reason: it is not an event name but a token standing for a SET of
periods, expanded by the revision matcher to the concrete `EVENT-1` / `EVENT-2` operator
scopes. Those concrete scopes DO carry a filing period and reconcile normally; only the
symbolic form is skipped, because a set has no single period to check against.

The complete skipped set is now stated: M036 `alta` / `modificacion` / `baja`, M145
`comunicacion` / `variacion`, and M210's symbolic `EVENT-N` — six tokens across three modelos.

## Verification

    git show 8986d07d7a --numstat
    10      0       src/cadrumo/domain/calculations/registry/_schema.py

    git cat-file -e HEAD:src/cadrumo/domain/calculations/registry/_schema.py   -> present

Verified by file presence at HEAD and by reading the landed diff, **not** by resolving the sha
from its subject. That convention failed earlier in this campaign by matching a peer's commit
body, so existence is confirmed against the object store rather than against message text.

No test selection to state: the change is documentation of an existing behaviour and adds no
assertion. The behaviour it documents is separately pinned by the snapshot filing-period
coverage gate.

## Notes

**The near-miss in this row is worth more than the row.** The executor first tested
`EVENT-1` and `EVENT-2`, found they DO carry a filing period, and was one step from concluding
the docstring's prose was wrong. The prose named `EVENT-N` — the symbolic selector, a
different token, which does produce a null filing period.

**Testing the exact token the prose named is what separated a correct docstring from an
incorrect one.** Testing a plausible instance of the family it belongs to would have produced
a confident, wrong correction to text that was right. That is the same substitution this
campaign has hit repeatedly: the instrument answered a neighbouring question, and the
neighbouring question had a different answer.

The complete set was enumerated against the live registry rather than derived, which is the
reason it can be stated as complete at all. A set assembled by reasoning about which tokens
"should" be administrative would have missed the symbolic selector for exactly the reason the
near-miss illustrates — it is not administrative, and it skips for an unrelated cause.
