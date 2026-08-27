---
tags:
  - '#adr'
  - '#registry-temporal-coverage'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:a62e2a71ab61abd7290f77af970ec3682e7f5d0dc040893f1c5f3dfb2006a6ca'
related:
  - "[[2026-08-26-registry-temporal-coverage-bundled-not-authority-declaration-audit]]"
---

# `registry-temporal-coverage` adr: `Declare whether a bundled record design is an authority` | (**status:** `accepted`)

## Problem Statement

Two adjudicated contracts were mutually exclusive, and neither could yield.

Modelo 184's regression pins five raw BOE ordenes to REFUSE parsing: they are the
orden approving the modelo, carrying its diseno as an annex, so the parse lands
partway down the document and the first field it finds sits at position 160
rather than 1. Its docstring states the ruling -- a raw BOE design is provenance,
not a surrogate for a later AEAT map, and the refusal is intentional and
load-bearing.

Against that, three sweeps required EVERY source of kind `record_design` to
parse. Nine failures stood on the contradiction, and the same missing concept
kept modelo 036's correctly-unregistered provisional draft permanently on the
bundled-design worklist and left modelo 165's layout gap without vocabulary.

## Considerations

The registry could express that a design exists, that it has an epoch, and that
a revision cites it. It could not express that a design is corpus evidence which
must never be read as a layout map. That absence, not either gate, was the
defect.

## Considered options

**Reclassify the `kind`** away from `record_design`, for which the 2026-08-15
schema-conformance sweep set precedent. Rejected: the modelo 184 contract pins
`kind == "record_design"`, so this breaks the very contract being honoured.

**Skip designs whose `record_design_epoch` is None.** Rejected: it over-skips.
That field is also None for designs whose selection window is merely unassigned,
and those parse fine -- `aeat-dr-303-2014` among them.

**Infer from the parse failure itself.** Rejected: a failure cannot distinguish
provenance from a broken design, so inferring would silence real breakage.

**Allowlist the five in test source.** Rejected: it re-introduces the honor
system that `aeat-quality-gates` removes, and it would need repeating in each of
the three sweeps.

## Constraints

Neither gate may be weakened; the modelo 184 pin carries the refusal assertion.
No new exemption may be untestable. And nothing here may touch `review_status`:
that is the operator's signature, on a different axis entirely.

## Implementation

`DesignAuthority = Literal["authoritative", "provenance_only"]` in `schema_base`,
and `design_authority` on `SourceReference` defaulting to `authoritative`, so all
499 existing sources are untouched. The five modelo 184 raw BOE ordenes carry the
stamp; the three parseability sweeps filter on it; the modelo 184 pin GAINS an
assertion for it; a new inverse gate asserts every stamped design still actually
refuses; and registry validation refuses an export layout naming a stamped
source.

## Rationale

This is the shape the project already mandates for the analogous problem.
`aeat-quality-gates` says fixture provenance is declared, never allowlisted: a
declaration on the artefact, gates that read it, and a cross-check against
physical evidence that keeps a mis-stamp red -- with no per-item exception list
in test source. The same three parts appear here.

The cross-check is what makes the field safe rather than convenient. Without it,
`design_authority` would be a way to quiet an inconvenient gate. With it, a stamp
must stay earned: the day a stamped design parses cleanly, the gate reds and
forces the promotion reconsideration the modelo 184 regression already asks for.

## Consequences

The contradiction is resolved with both sides green together for the first time,
and neither gate weakened -- the sweeps gained a condition, the pin lost nothing.
Provenance designs leave the PARSE set but stay in DISCOVERY, so a rename or
deletion still trips the gate.

The count was five, not the four the escalation named: each was tested through
`extract_record_design` directly and `boe-dr-184-2023-2024` refuses too.

Two limits are deliberate. Modelo 036's provisional draft is NOT stamped, because
it is unregistered and re-registering it to carry a stamp would assert the
operator `review_status` agents may not; its worklist entry stands until the
operator enrols it. And only the must-still-refuse arm of the inverse gate is
authored -- the must-be-unconsumed arm, for a parseable-but-unadopted draft, has
no subject while that draft is unregistered, and a gate arm with no member passes
vacuously.

The risk is mis-stamping a genuinely authoritative design, which would drop it
from parse coverage silently. The inverse gate and the snapshot-build refusal are
what detect it.
