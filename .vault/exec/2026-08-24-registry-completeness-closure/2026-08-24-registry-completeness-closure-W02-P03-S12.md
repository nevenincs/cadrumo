---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:d08492a69165ff482b1d59c213e6e845c61068319a217dfd9487604dcbccc8d3'
step_id: 'S12'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Adjudicate Modelo 036 revision 2025-02-03-y-siguientes producer vocabulary and official filing authority

## Scope

- `.vault/reference/`

## Description

- Re-fetch AEAT's live Modelo 036 procedure page, the 2025 record-design index, and BOE-A-2025-410.
- Compare that authority with the selected revision, producer vocabulary, censo portal category, and local M036 lifecycle boundary.
- Record the exact supported/fileable distinction, responsible existing-plan route, and evidence threshold for reconsideration.

## Outcome

AEAT authority confirms a live 2025 Modelo 036 and both electronic and competent-AEAT-office presentation routes, but does not override Cadrumo's narrower product boundary. The revision remains applicability-grade censo support: Cadrumo records an operator-declared filing made through Sede or in person at an AEAT office and does not produce an M036 filing artifact. `sede_justificante` is optional electronic-receipt evidence, so its absence does not prevent recording an office filing. There is no `m036.*` `FilingProducerKey` member and no real aggregate behind one, so inventing producer vocabulary or a layout would be an unsupported declaration.

The source-connectivity question is distinct from filing scope and now begins with W02.P04.S73: real source evidence or an ADR-authorized disposition must enter the existing source-casilla plan, and an empty candidate set cannot satisfy it. A future filing artifact remains routed through W02.P04.S28 into the existing export-authority plan after an accepted ADR and the documented producer, map, grade, generation, and byte-proof prerequisites.

## Notes

No production files changed. W02.P04.S74 corrected this record and the canonical authority reference after independent review found the original Sede-only wording and omitted source-participation owner. The expected-failing all-registry filing worklist remains outside this Step's claimed green gate; its old unscoped treatment of below-filing revisions is being addressed separately by W01.P02.S72.
