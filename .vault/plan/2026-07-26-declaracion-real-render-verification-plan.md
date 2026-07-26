---
tags:
  - '#plan'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
tier: L2
related:
  - '[[2026-07-25-declaracion-profile-printed-box-scope-adr]]'
  - '[[2026-07-25-declaracion-profile-printed-box-scope-real-render-gate-and-naming-honesty-audit]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `declaracion-real-render-verification` plan

### Phase `P01` - Evidence-backed profiles

Verify against real AEAT renders, extend the gate

- [x] `P01.S01` - Verify M390 against its untested real_corpus specimen 2021-0A, covering routes R2 kerning drift and R6 bbox fragility, on a profile with a confirmed R2 defect; `src/cadrumo/_data/registry/aeat/modelos/390, declaracion tests`.
- [x] `P01.S02` - Verify M111 against its four real specimens, 29 bbox targets under a vacuous zero floor, covering routes R3 and R6; `src/cadrumo/_data/registry/aeat/modelos/111, declaracion tests`.
- [x] `P01.S03` - Verify M100 across its five revisions against three real specimens, covering routes R4 over-strict floor and R10 multi-revision blind spot; `src/cadrumo/_data/registry/aeat/modelos/100, declaracion tests`.
- [x] `P01.S04` - Verify M190 against its real specimen, covering route R4; `src/cadrumo/_data/registry/aeat/modelos/190, declaracion tests`.
- [x] `P01.S05` - Fold every verified specimen into the shared real-render gate and prove the gate bites for each; `src/cadrumo/adapters/inbound/declaracion/tests`.

### Phase `P02` - Specimen-less profiles

Static route audit and evidence-gap register

- [x] `P02.S06` - Audit the coverage floors across all 29 profiles, route R3 vacuous zero floors and route R4 over-strict unit floors, reporting which refuse a real filing over one blank optional box; `src/cadrumo/_data/registry/aeat/modelos, .vault/audit`.
- [x] `P02.S07` - Sweep route R8 across all 29 profiles, intersecting profile targets with formula-declaring casillas to find targets the engine refuses as inputs; `src/cadrumo/_data/registry/aeat/modelos, .vault/audit`.
- [x] `P02.S08` - Sweep route R9 across all 29 profiles, checking each profile legal_refs equals the union of its targets own refs; `src/cadrumo/_data/registry/aeat/modelos, .vault/audit`.
- [x] `P02.S09` - Register route R11 for the 22 specimen-less profiles as evidence gaps rather than passes, naming what each would need to become decidable; `.vault/audit`.

### Phase `P03` - Render language exposure

Measure and bound route R12, the filer-chosen render language

- [x] `P03.S10` - Measure route R12 language exposure across all 29 declaracion_pdf profiles, separating targets that depend on Spanish prose from those anchored on box numbers or numerals; `src/cadrumo/_data/registry/aeat/modelos`.
- [ ] `P03.S11` - Widen every label pattern for which a bundled render evidences the wording, inventing none; `src/cadrumo/_data/registry/aeat/modelos/390`.
- [ ] `P03.S12` - Register the fully-exposed profiles as D3 evidence gaps naming the English-render specimen class that would unblock each; `.vault/exec`.
- [ ] `P03.S13` - Assess whether per-profile bilingual alternation is the right shape or merely the reachable one, and record the structural alternative; `.vault/exec`.
- [ ] `P03.S14` - Add the Modelo 100 boundary gate asserting the exclusion and its stated reason, green and not mistakable for a pass; `src/cadrumo/adapters/inbound/declaracion/tests`.

### Phase `P04` - Tracked deferrals

Open defects and decisions this campaign measured but did not close

- [ ] `P04.S15` - Populate form_number on the seventeen remaining inert blank-box guards across nine modelos, M180 and M193 and M349 fichero-BOE targets plus seven decl.ejercicio targets, a live fabrication-producing defect; `src/cadrumo/_data/registry/aeat/modelos`.
- [ ] `P04.S16` - Scope the M100 parser follow-on ADR covering the shared pdfplumber primitive, the estate-wide named_label capture contract, and the M100 floor under D2; `.vault/adr`.
- [ ] `P04.S17` - Decide whether Modelo 202 is enrolled in casilla-level reconcile, now that its profile is confirmed to exist and D5 governs enrolment; `.vault/adr, src/cadrumo/application/modelo`.
- [ ] `P04.S18` - Decide the disposition of verify_declaracion, a modelo-agnostic comparison mechanism with zero callers outside its own tests; `src/cadrumo/application/verification`.
- [ ] `P04.S19` - Correct the Modelo 100 sidecar manifests to declare both sanitiser constants, since the length-preserving sanitiser wrote two forms while the manifests name one; `src/cadrumo/tests/fixtures/justificantes/100`.
- [x] `P04.S20` - Wire D4 so it stays true, by having the real-render gate import the production profile selector rather than hand-copying its logic; `src/cadrumo/adapters/inbound/declaracion/tests`.

## Description

## Steps

## Parallelization

## Verification
