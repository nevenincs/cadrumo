---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:c1f20edeae425c7639fa1cf9902d502248a0c570debfdc0eee6c6f49159976cc'
step_id: 'S92'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Author the closed M303 rectificativa-motive enum and immutable amendment identity/evidence lifecycle: persist one typed motive, include amendment kind and amended filing-record identity in calculation-revision identity, validate revision, WorkUnit, exact reviewed record-design evidence, amended ModeloRecord, ExternalEvidence and Justificante as one context-bound aggregate, require exactly one motive for the closed 2024-late, 2025 and 2026 M303 rectificativa capability set and prohibit it elsewhere, derive export evidence only from persisted authority, add two exhaustive FilingProducerKey projections, and prove persistence, reload, identity divergence, cross-context and command-substitution refusal, full truth tables, and no free-text, casilla, result, year, epoch-order or default inference

## Scope

- `src/cadrumo/domain/modelos/`
- `src/cadrumo/application/modelo/`
- `src/cadrumo/application/filing/`
- `src/cadrumo/core/`
- `src/cadrumo/adapters/persistence/profile/`
- `src/cadrumo/**/tests/`

## Description

- Implement the accepted dual-keying decision from `2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr.md` as a closed `M303RectificativaMotive` authority.
- Bind amendment kind, amended filing-record identity, and typed motive into calculation-revision identity and encrypted persistence.
- Validate the revision, WorkUnit, reviewed M303 record design, amended ModeloRecord, ExternalEvidence, taxpayer identity, and Justificante as one context-bound aggregate.
- Derive immutable export amendment evidence from persisted authority before filing-grade snapshot validation and project the two exhaustive producer keys.
- Route the typed motive through both public amend CLI paths without free-text inference or defaults.
- Isolate the reviewed S92 payload across 27 staged paths while excluding concurrent S91 work and all human legal-review metadata.

## Outcome

The closed motive lifecycle is implemented for the reviewed 2024-late, 2025, and 2026 M303 rectificativa capability set and prohibited elsewhere. Amendment identity changes alter the content-addressed revision identity. Encrypted persistence reloads and revalidates the full aggregate. Public export constructs the concrete Justificante repository, resolves persisted amendment evidence once, carries it immutably to the producer snapshot, and refuses command substitution.

Real lifecycle coverage completed with 22 passing tests. The public default-repository route passed its dedicated test and reached the next expected filing gate after the receipt-authority join. Ruff and ty/type checks passed on the owned surface. Independent Terra xhigh review finished with critical/high/medium/low findings of 0/0/0/0.

## Notes

The implementation adopted the stable peer extraction of the canonical M303 evidence and handoff modules, the one-line `StrEnum` import repair, and coherent Justificante/application joins after hash and mtime stability windows plus combined review. Same-file S91 filing-envelope refactors were preserved but excluded from the 27-path S92 staged isolation.

Broader filing-grade and wizard lanes encountered pre-existing operator-review and profile-storage setup blockers. Those failures were recorded as external evidence only: no human legal-review metadata, snapshot bypass, fake repository, compatibility wrapper, skip, or xfail was introduced. The plan row was not closed and no commit was created by this lifecycle-record operation.
