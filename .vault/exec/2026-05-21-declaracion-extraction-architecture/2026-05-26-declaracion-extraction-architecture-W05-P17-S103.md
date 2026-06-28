---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S103'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-auth-gated-acquisition-status-audit]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-plan]]'
---

# `declaracion-extraction-architecture` `W05.P17.S103`

Synchronized the declaration-extraction progress ledger after closing the
no-synthetic-Sede follow-up.

- Modified: `.vault/plan/2026-05-21-declaracion-extraction-architecture-plan.md`
- Modified: `.vault/audit/2026-05-26-declaracion-extraction-auth-gated-acquisition-status.md`
- Referenced: `.vault/plan/2026-05-26-no-synthetic-sede-live-surfaces-plan.md`

## Description

The progress ledger now reflects that `W05.P18.S124` is closed and that Modelo
100, Modelo 349 GROI/IXVI, and direct GROI/NIF-IVA Sede guard policies no
longer permit AEAT-hosted synthetic input. The acquisition audit was updated so
it no longer reports the previous Modelo 100/349 synthetic-live-surface conflict
as open.

Remaining acquisition rows for modelos 180, 036, 369, 720, and 840 stay open
because they require authorised real fixtures or authenticated read-only filed
artifacts. Synthetic preview/download through Sede or AEAT-hosted form surfaces
remains prohibited.

## Tests

No live Sede call was made. Validation is covered by the no-synthetic-Sede
focused gates and the plan checks run after this ledger update.
