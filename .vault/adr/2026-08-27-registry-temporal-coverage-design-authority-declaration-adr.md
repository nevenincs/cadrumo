---
tags:
  - '#adr'
  - '#registry-temporal-coverage'
date: '2026-08-27'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:f2a66844c41c64d286889d4300fc44c1d6ae2c3968341cd603d7132391e6cf4a'
related:
  - '[[2026-08-26-registry-temporal-coverage-bundled-not-authority-declaration-audit]]'
  - '[[2026-08-31-registry-temporal-coverage-modelo-165-2023-layout-composite-research]]'
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

The declaration distinguishes an enrolled source design that is executable from
one that is provenance only. It did not decide whether a layout mechanically
derived from a pinned executable predecessor and a separately pinned official
amendment may itself become executable without reclassifying that amendment.
`2026-08-31-registry-temporal-coverage-modelo-165-2023-layout-composite-research`
presents that decision for the bounded Modelo 165 interval.

## Considerations

The registry could express that a design exists, that it has an epoch, and that
a revision cites it. It could not express that a design is corpus evidence which
must never be read as a layout map. That absence, not either gate, was the
defect.

- The source-authority distinction remains binding: a provenance-only BOE
  artefact cannot become an export-layout source merely because its content
  supplies a needed amendment.
- The research establishes a finite, exact successor relation for the Modelo 165
  2023--2025 interval, but no immutable historical AEAT binary; the decision
  must preserve that distinction rather than backdate the mutable later document.
- A composite that does not retain both pinned inputs, their identities, and a
  reproducible derivation would be an unreviewable substitute source.

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

**Retain applicability-only treatment pending an immutable historical AEAT
binary.** Rejected for the Modelo 165 interval: it preserves caution but leaves
an evidenced, finite layout transition unusable despite a reproducible provenance
chain.

**Reclassify the BOE amendment as authoritative.** Rejected: it reverses this
record's accepted provenance-only declaration and would turn raw BOE material
into a general executable-layout substitute.

**Backdate the currently served AEAT document.** Rejected: a mutable later
artefact cannot establish the earlier interval.

**Admit one restricted, derived composite layout (chosen).** Authorize a
distinct executable layout for Modelo 165 revision `2023-2025`, only when it is
reproduced from the existing hash-pinned 2016 AEAT layout and the hash-pinned
`BOE-A-2023-24412` Article 13 amendment, with the order's stated applicability
boundary also pinned. The composite, not either input alone, is the source
selected by the export layout.

## Constraints

Neither gate may be weakened; the modelo 184 pin carries the refusal assertion.
No new exemption may be untestable. And nothing here may touch `review_status`:
that is the operator's signature, on a different axis entirely.

- This is a one-modelo, one-revision exception; it creates no general inference
  rule, successor inheritance rule, or automatic BOE-to-layout promotion.
- The composite must carry immutable identities and content hashes for both
  inputs, retain the exact transformation provenance, and refuse validation when
  either input, hash, or declared interval differs.
- Only the explicit legislative delta may differ from the 2016 base. The current
  AEAT document is forbidden as a historical input and remains confined to the
  interval its own heading supports.
- The BOE input remains `provenance_only`; ordinary export-layout source
  membership must name the derived composite, not the raw BOE source.
- The composite must be independently tested for complete record coverage and
  emitted-byte geometry before the 2023--2025 revision may claim filing
  authority. Legal and operator-review gates remain independent and unchanged.

## Implementation

`DesignAuthority = Literal["authoritative", "provenance_only"]` in `schema_base`,
and `design_authority` on `SourceReference` defaulting to `authoritative`, so all
499 existing sources are untouched. The five modelo 184 raw BOE ordenes carry the
stamp; the three parseability sweeps filter on it; the modelo 184 pin GAINS an
assertion for it; a new inverse gate asserts every stamped design still actually
refuses; and registry validation refuses an export layout naming a stamped
source.

The registry admits one explicitly identified derived-layout representation for
Modelo 165 `2023-2025`. It records the 2016 executable base, the pinned BOE
amendment and applicability evidence as immutable provenance inputs, and
materializes an export layout whose own source identity is the composite.
Registry validation verifies the input identities, hashes, interval, and
restricted transformation; it refuses direct use of the BOE source by an export
layout and any composite outside this declared scope. The existing
historical-layout proof changes from asserting absence of a 2023--2025 layout to
proving the composite's exact geometry, its two-input provenance, its rejection
on either altered input, and continued refusal to backdate the later AEAT
document.

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

The chosen representation admits exactly the authority the research establishes
while retaining the earlier decision's protective distinction. The executable
claim belongs to a reproducible, validator-checked composite with a closed
provenance chain, not to a raw BOE document or to a filename that no longer
matches the document served. Its scope and invariant checks make a future
composite a new decision rather than an unnoticed precedent.

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

Modelo 165 `2023-2025` can become layout- and filing-capable only after the
composite and its refusal proofs validate. The raw BOE amendment remains
discoverable provenance, not a parseable or directly selected layout source. The
2013--2015 and 2026-and-later boundaries remain unchanged; the mutable later
AEAT artefact gains no historical reach. Any future composite, altered
predecessor, different amendment, or interval expansion needs fresh research and
an ADR amendment.
