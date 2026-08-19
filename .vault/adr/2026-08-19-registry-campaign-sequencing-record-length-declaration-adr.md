---
tags:
  - '#adr'
  - '#registry-campaign-sequencing'
date: '2026-08-19'
modified: '2026-08-19'
body_schema: 'body-v1'
body_hash: 'sha256:73a1cbee563751755956d822c5ebddf81a96712defba49b509d3e41ffb613560'
related:
  - "[[2026-08-16-registry-campaign-sequencing-export-layout-authoring-backlog-audit]]"
---

# `registry-campaign-sequencing` adr: `Fixed-width record length must be declared, not inferred from field extent` | (**status:** `proposed`)

## Problem Statement

A fixed-width export record is exactly as long as its longest field reaches. The
sole record-byte producer sizes its buffer from `max(offset + length - 1)` over
the record's fields and pads nothing beyond that, so a layout whose fields stop
before the official record length emits a SHORT record. AEAT's fichero readers
are position-based over fixed-length records; a record short of its declared
length does not near-miss, it fails to parse or shifts every subsequent field.

Two revisions demonstrably do this today, each verified against its own bundled
diseño rather than inferred from a sweep, and both are recorded with their
measurements in `2026-08-16-registry-campaign-sequencing-export-layout-authoring-backlog-audit`.

The gate that exists to catch exactly this refuses a layout that writes "only N
of M positions its official record design requires" -- but it runs inside the
generated-tree pipeline, and neither affected revision enters that pipeline. The
gate and its blind spot came from one design decision, so no amount of running
the existing suite surfaces the defect.

## Considerations

- The record length AEAT declares is a fact of the official design, and the
  design states it: each affected record's diseño ends with an explicit trailing
  BLANCOS run to the declared total.
- Generated trees already emit full-length records, because their semantic maps
  author `filler` entries over that trailing run. The capability exists; what is
  missing is a rule that every layout must reach the declared length.
- A detector for this class needs a declared length to compare against.
  Attempting the sweep without one failed twice: neither the record id nor
  `line_ending` separates an envelope prefix record from a modelo data record,
  and the tidier of the two attempts was the one that hid a true positive.
- Nothing in the current schema carries a record length, so today the defect is
  unrepresentable as an assertion, not merely unasserted.

## Considered options

- **Declare the record length on the layout record, and refuse a field extent
  that disagrees.** Makes the official fact explicit and the class gate-checkable
  for every layout mechanism at once. Costs one authored field per record.
- **Require authored trailing filler on every layout, as generated trees already
  produce.** Fixes the emitted bytes without introducing a new schema field, but
  states the length only implicitly, so a future short layout is still
  representable and the detector still has nothing to compare against.
- **Pad to a length derived from the bundled design at render time.** Removes
  authoring effort, but makes the emitted record depend on a design lookup at
  write time and silently changes output when a design is re-fetched; it also
  cannot help a revision whose design is not resolvable.
- **Leave as is and rely on review.** Rejected: the two known cases survived
  every existing gate and were found only by a hand comparison during a stamp
  review, which does not scale and did not happen for years.

## Constraints

- The change touches the one record-byte producer and the export layout schema,
  both of which every fixed-width modelo depends on; a regression there is a
  filing-correctness regression across the registry.
- Adding a required field to the layout schema forces every existing layout to
  declare it in the same change, including generated trees, whose emitters must
  then carry it through render and publication.
- No parent feature is unstable; the affected surfaces are long-established.

## Implementation

Carry an explicit record length on the export layout record. Registry validation
compares each record's field extent against it and refuses a disagreement in
either direction -- short, which is the defect here, and over-long, which would
be a field running past the record. The generated-tree emitter populates it from
the design's declared total, which it already reads; hand-authored layouts state
it from the same source. The completeness check that currently lives inside the
generated-tree pipeline moves to registry validation, where it governs every
layout mechanism rather than one of them.

The two known revisions are then corrected to reach their declared length, by
authoring the trailing fill their designs describe.

## Rationale

The knockout criterion is detectability. Every other option can produce correct
bytes for the two known cases, and none of them lets a gate state the rule, so
the third occurrence is found the same way the first two were -- by someone
reading a diseño next to a layout. A declared length turns an invisible
filing-correctness defect into a refusal at registry build, which is where this
registry puts its other structural facts.
