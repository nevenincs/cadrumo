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
body_hash: 'sha256:2df4a03673a16d6ac0f39ec83ccf67ea90db123d3bd5d0b60c9e1dc2855fc9a2'
---

# `modelo-profile-bindings` plan

## Description

Approved 2026-11-06. Basis: MODELPROFILE dispatch explicitly authorizes this feature, proportionate plan, implementation, scoped helpers, verification and review in this child worktree. CHECKS2 owns integration and cleanup; no push or external publication is authorized.

S01 enumerates supported modelos and authored editions from typed registry authorities, traces identity/contact/address/payment fields and records a compact matrix with source, binding or producer, role, current behavior and disposition. Discovery includes missing bindings, missing or wrong profile facts, stale state, incompleteness, role mismatch, UI projection and intentional manual fields. Semantic code search was attempted but this child has no published index; targeted source inspection is the fallback.

S02 reuses the closed provider union and existing profile, calculation and export owners under 2026-09-11-binding-schema-adr and 2026-08-22-source-casilla-integration-adr. The latter's September amendment forbids shipping a development census. The coverage matrix belongs to the reference record. Profile requirement metadata remains grounded in actual declared bindings under 2026-08-08-profile-requirement-grounding-adr. Ledger-owned bank accounts and charge/refund selections remain governed by 2026-10-04-taxpayer-bank-accounts-adr; IRNR party and address distinctions remain governed by 2026-08-16-m210-export-authority-adr. Routine supported mappings and projection repairs need no new costly decision; uncovered semantic choices are escalated to BOSS before implementation.

S04 corrects the two evidenced M720 contact bindings, enrolls their specific official-source citations, refreshes their generated form layout through the canonical generator, and repairs the existing scalar profile provenance omission discovered by tracing their real encrypted calculation path. It preserves all-tier considered evidence and caller precedence under the existing source-casilla contract. No new persisted shape or decision is introduced.

The generator must retain profile-backed export fields as existing read-only form context rather than dropping them when a manual binding becomes profile-owned. BOSS confirmed this bounded shared generator repair and registry-driven prefilling across existing React, TUI and CLI surfaces on 2026-11-06. A separate editable mapping editor is outside this request. FRONTEND reviews consumption paths; CHECKS2 owns the integrated frontend build. This child owns source behavior and explicit surface coverage, with no GUI-specific defaults.

Normal creation does not calculate before opening the form. S04 therefore admits live values for exact registry-declared profile binding contexts on first open, preserving saved answers and historical guards without write-on-read. BOSS confirmed this required first-open behavior on 2026-11-06. Independent review covers that precedence, with real first-create/form proof in this child and complementary React assertions owned by FRONTEND.

S03 proves real application behavior, absence and override handling, role separation, supported-year selection, saved provenance, and applicable GUI/export parity. No new unresolved-results API is introduced; existing calculate v3 findings remain authoritative.

## Steps

- [x] `S01` - Establish typed revision coverage matrix and reproduce profile sourcing gaps with canonical synthetic fixtures; `dev/registry, src/cadrumo/application/modelo/tests, .vault/reference`.
- [x] `S02` - Project registry-declared taxpayer and contact header fields through shared export producers in the admitted work-form read, preserving absence and historical evidence; `src/cadrumo/application/filing/export_producer.py, src/cadrumo/application/modelo form projection and tests`.
- [x] `S04` - Bind Modelo 720 contact name and phone through the existing saved text channel and preserve profile-tier fingerprint provenance through encrypted calculation persistence and overrides; `profile_binding.py, calculation resolution and actions, modelos/720 contact bindings, owning tests`.
- [x] `S03` - Verify integrated creation, calculation, GUI projection and applicable export behavior, publish final local authority if needed, and resolve independent review findings; `owning scoped tests, .vault/audit, .vault/exec`.

## Parallelization

S01 grounds each S02 mapping before that mapping is edited; completing the full inventory may overlap an already-grounded projection repair. S02 and S04 implementation writes are serialized; S03 follows both. Independent review of stable S02 may overlap disjoint S04 implementation. Luna read-only helpers may inspect disjoint registry and application paths concurrently. One Sol high implementation worker owns a bounded source/test assignment at a time; a separate Sol high reviewer evaluates the stable candidate. Principal owns plan, matrix persistence, execution metadata, commits and coordination. Preserve others' edits. BACKEND/FIXTURES/CHECKS2 alignment precedes overlapping source edits. RESOURCE admits environment setup and tests; CHECKS2 schedules the single heavy host-wide run. Do not duplicate heavy checks.

## Verification

- Enumerate models, revisions and support years through canonical typed APIs, with no handwritten year authority; report coverage limits and source-generation identity.
- Reproduce representative populated and incomplete synthetic profiles through real owning application paths, with explicit overrides and party/payment role distinctions.
- Check every changed mapping against existing official source evidence, consulting AEAT/BOE where meaning is uncertain; do not infer semantic equivalence from names.
- Run focused tests and configured style/type/import gates appropriate to affected paths. Coordinate mandatory check-code, check-registry-gate and test-gate evidence with CHECKS2; distinguish pending verification from actual defects.
- For registry source changes run registry health/bindings/edition minimality and supported-year proofs, publish final local authority only after validation and verify adoption.
- Independent Sol high review passes with material findings resolved. Handoff includes commits, plan/reference/audit locators, matrix scope, evidence and explicit residual limitations.
