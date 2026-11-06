---
tags:
  - '#plan'
  - '#modelo-profile-bindings'
date: '2026-11-06'
tier: L1
related:
  - '[[2026-09-11-binding-schema-adr]]'
  - '[[2026-08-22-source-casilla-integration-adr]]'
  - '[[2026-08-08-profile-requirement-grounding-adr]]'
  - '[[2026-10-04-taxpayer-bank-accounts-adr]]'
  - '[[2026-08-16-m210-export-authority-adr]]'
modified: '2026-11-06'
body_schema: body-v2
body_hash: 'sha256:7400803363662ccb0a85fa118642f974b0f59e02aa10dc2827983e865e918b6b'
---

# `modelo-profile-bindings` plan

## Description

Approved 2026-11-06. Basis: MODELPROFILE dispatch explicitly authorizes this feature, proportionate plan, implementation, scoped helpers, verification and review in this child worktree. CHECKS2 owns integration and cleanup; no push or external publication is authorized.

S01 enumerates supported modelos and authored editions from typed registry authorities, traces identity/contact/address/payment fields and records a compact matrix with source, binding or producer, role, current behavior and disposition. Discovery includes missing bindings, missing or wrong profile facts, stale state, incompleteness, role mismatch, UI projection and intentional manual fields. Semantic code search was attempted but this child has no published index; targeted source inspection is the fallback.

S02 reuses the closed provider union and existing profile, calculation and export owners under 2026-09-11-binding-schema-adr and 2026-08-22-source-casilla-integration-adr. The latter's September amendment forbids shipping a development census. The coverage matrix belongs to the reference record. Profile requirement metadata remains grounded in actual declared bindings under 2026-08-08-profile-requirement-grounding-adr. Ledger-owned bank accounts and charge/refund selections remain governed by 2026-10-04-taxpayer-bank-accounts-adr; IRNR party and address distinctions remain governed by 2026-08-16-m210-export-authority-adr. Routine supported mappings and projection repairs need no new costly decision; uncovered semantic choices are escalated to BOSS before implementation.

S03 proves real application behavior, absence and override handling, role separation, supported-year selection, saved provenance, and applicable GUI/export parity. No new unresolved-results API is introduced; existing calculate v3 findings remain authoritative.

## Steps

- [x] `S01` - Establish typed revision coverage matrix and reproduce profile sourcing gaps with canonical synthetic fixtures; `dev/registry, src/cadrumo/application/modelo/tests, .vault/reference`.
- [x] `S02` - Project registry-declared taxpayer and contact header fields through shared export producers in the admitted work-form read, preserving absence and historical evidence; `src/cadrumo/application/filing/export_producer.py, src/cadrumo/application/modelo form projection and tests`.
- [ ] `S04` - Bind Modelo 720 contact-person name and phone to canonical profile facts through the existing saved text channel, preserving declaration overrides and optional absence; `profile_binding.py, modelos/720 contact bindings, owning tests`.
- [ ] `S03` - Verify integrated creation, calculation, GUI projection and applicable export behavior, publish final local authority if needed, and resolve independent review findings; `owning scoped tests, .vault/audit, .vault/exec`.

## Parallelization

S01 grounds each S02 mapping before that mapping is edited; completing the full inventory may overlap an already-grounded projection repair. S03 follows implementation. Luna read-only helpers may inspect disjoint registry and application paths concurrently. One Sol high implementation worker owns a bounded source/test assignment at a time; a separate Sol high reviewer evaluates the stable candidate. Principal owns plan, matrix persistence, execution metadata, commits and coordination. Preserve others' edits. BACKEND/FIXTURES/CHECKS2 alignment precedes overlapping source edits. RESOURCE admits environment setup and tests; CHECKS2 schedules the single heavy host-wide run. Do not duplicate heavy checks.

## Verification

- Enumerate models, revisions and support years through canonical typed APIs, with no handwritten year authority; report coverage limits and source-generation identity.
- Reproduce representative populated and incomplete synthetic profiles through real owning application paths, with explicit overrides and party/payment role distinctions.
- Check every changed mapping against existing official source evidence, consulting AEAT/BOE where meaning is uncertain; do not infer semantic equivalence from names.
- Run focused tests and configured style/type/import gates appropriate to affected paths. Coordinate mandatory check-code, check-registry-gate and test-gate evidence with CHECKS2; distinguish pending verification from actual defects.
- For registry source changes run registry health/bindings/edition minimality and supported-year proofs, publish final local authority only after validation and verify adoption.
- Independent Sol high review passes with material findings resolved. Handoff includes commits, plan/reference/audit locators, matrix scope, evidence and explicit residual limitations.
