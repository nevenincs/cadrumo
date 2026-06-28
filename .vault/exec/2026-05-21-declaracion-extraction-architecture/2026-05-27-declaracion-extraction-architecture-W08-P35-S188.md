---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S188'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# `declaracion-extraction-architecture` `W08.P35.S188`

Appended ADR amendment block documenting the M190 revision rename
rationale to the declaracion-extraction-architecture ADR. Plan step
W08.P35.S188 closed.

- Modified: `.vault/adr/2026-05-21-declaracion-extraction-architecture-adr.md`

## Description

Added a `## 2026-05-27 amendment — M190 revision rename` block to the
accepted ADR. The amendment records:

- The original revision id `"2025-y-siguientes"` with `year_from = 2025`
  and why it was chosen at authoring time.
- The rename to `"2024-y-siguientes"` with `year_from = 2024` introduced
  in commit `be12b2c7a` (Task-36 Cluster B).
- The three-fact rationale: the sole corpus fixture PDF is a year=2024
  document; the M100-2025 relation `renta-2025-rel-190-retenciones-anuales`
  uses `source_revision_selector = { year = 2025 }` which the open-ended
  window satisfies; the task-32 audit confirmed AEAT's 2024 and 2025 M190
  EDI specifications (Orden HAC/1432/2024 and Orden HAC/1431/2025) are
  structurally identical, making a single revision correct.
- The forward-looking decision: one revision with `year_from = 2024`
  covers both years; a new revision boundary would only be added if a
  future AEAT Orden diverges from the current Tipo 1/2 record layouts.

The amendment block was placed after the existing round-trip gate
amendment, matching the tense, paragraph length, and heading style of
the two prior amendment blocks.

## Tests

No code was changed. The ADR file was validated by reading it back in
full to confirm: YAML frontmatter is intact and parseable, both prior
amendment blocks (`2026-05-26 amendment` and `2026-05-26 amendment
(round-trip gate)`) are unchanged, and the new block is well-formed.
