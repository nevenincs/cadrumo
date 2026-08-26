---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:033826858db9b5f1ea5aa9a2f1ce40fd9dff30278dc3c89e5ccc8218af09f461'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---

# `registry-temporal-coverage` audit: `Modelo 200 2024/2025 split coherence`

## Scope

Modelo 200's registry revisions `2024` and `2025-y-siguientes`, and the
generated-export-tree declaration that names them. Opened because
`test_every_official_anchor_reaches_exactly_one_generated_field[m200-2024]`
began failing once the ejercicio-2024 revision was bounded to 2024-12-31,
and the obvious one-line correction would have removed the only signal
covering a registry state nobody adjudicated.

## Findings

### modelo-200-split-half-done | high | the 2024 revision carries the 2025 diseno's content while declaring the 2024 design as its authority

The anchor-reach gate fails inside the authority builder with `parser
intermediate source 'aeat-dr-200-2025' is not an authority of selected revision
'2024'`. The declaration in `dev/registry/tests/test_generated_export_trees.py`
pairs revision `2024` with source `aeat-dr-200-2025`, design epoch `2025` and
filing year 2025 -- every field except the revision says 2025. That pairing read
as coherent only while the revision was the open-ended `2024-y-siguientes`,
which the 2025 diseno legitimately applied to. Bounded to ejercicio 2024, it no
longer does, so the gate is reporting a true inconsistency rather than a
regression in the test.

The defect is upstream of the declaration. Revisions `2024` and
`2025-y-siguientes` each hold 1,025 identical casilla fragments, 3,462 entries.
The split was landed by copy in commits `17eb283313` and `1d1b203114`; the
surgery the campaign-sequencing export-layout backlog audit specifies -- 291
drops, 3,171 export_ref repoints, 185 casillas authored, 60 emptied fragments
deleted -- was never run. Revision `2024` therefore declares
`aeat-dr-200-2024` in its revision-level `source_refs` while its content is the
2025 diseno.

### modelo-200-split-only-signal | high | no other gate covers the incoherence, so the declaration must not be repointed

`test_modelo_200_registry` and `test_registry_legal_grounding` both pass clean,
23 of 23, against the current half-split tree. Repointing the declaration at
`2025-y-siguientes` would make it truthful and turn the suite green while
leaving the content incoherence entirely unobserved. The failing anchor-reach
gate is currently the only alarm, so it is left red deliberately.

### modelo-200-dp200023-date-rules | high | completing the split needs an authority-basis ruling that is the operator's

The backlog audit's final tick sized the remaining job at three render-profile
locator edits plus a decision on two `DP200023` rules governing the 8-byte
AAAAMMDD date fields for the fecha de inscripcion de los acuerdos sociales en
Registro Mercantil and the fecha de comunicacion de la operacion. The 2025
diseno carries an extra column H reading `AAAAMMDD`; the 2024 design has no
counterpart, and the token appears zero times across columns G to I of every
sheet of the 2024 workbook. Those rules declare `authority_kind =
"official_source"`. Downgrading them to `reviewed_policy` so the evidence loader
stops asking would move a filing-grade representation rule from "AEAT states
this" to "we decided this", which is what the evidence gate exists to prevent.

### m200-m184-export-review-stamp | medium | both pending trees remain blocked on an operator review stamp

The reproducibility gate's `m200-2024` and `m184-2023-2024` cases refuse for
their pinned reasons, which are the operator review stamp and the filing-grade
snapshot authority. No committed export tree exists for modelo 200 under either
revision.

### m303-anchor-reach-flake | low | not a defect

The m303 `2026-y-siguientes` case of the same anchor-reach gate failed in a
parallel run and passed on a serialised re-run. It is a concurrency artifact of
peer in-flight work, consistent with the behaviour the backlog audit recorded
for this suite.

## Recommendations

Escalate the `DP200023` authority-basis question to the operator: either the
two date rules stay `official_source` and the 2024 export tree cannot be
completed, or they are downgraded to `reviewed_policy` with the consequence
recorded. This is the decision a follow-on ADR must make; it is not taken here.

Leave the anchor-reach gate red until that ruling lands. Do not repoint the
generated-tree declaration at `2025-y-siguientes` as a green-up: it is the only
gate currently observing the half-split state.

Once the ruling exists, run the already-scripted revision surgery against
revision `2024`, then the three render-profile locator edits, then the publish
cycles. Add a gate asserting that a revision's content routes through the design
its revision-level `source_refs` name, so a split landed by copy cannot pass
unobserved again.
