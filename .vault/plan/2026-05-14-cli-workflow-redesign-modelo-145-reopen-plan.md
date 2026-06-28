---
tags:
  - '#plan'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
tier: L2
related:
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-adr]]'
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-research]]'
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-14-cli-workflow-redesign-w51-modelo-145-deferral-baseline-exec]]'
---


# `cli-workflow-redesign` `modelo-145-local-payer-communication-reopening` plan

### Phase `P01` - source and legal catalogue

This Phase establishes official AEAT and BOE authority before any Modelo 145 registry or behavior is shipped.

- [x] `P01.S01` - Add local corpus copy and catalogue authority for AEAT G603 Modelo 145 payer communication; `corpus/aeat_official registry/aeat/legal`.
- [x] `P01.S02` - Add local corpus copy and catalogue authority for AEAT Modelo 145 non-electronic payer processing obligations; `corpus/aeat_official registry/aeat/legal`.
- [x] `P01.S03` - Add local corpus copy and catalogue authority for the current Modelo 145 form; `corpus/aeat_official registry/aeat/legal`.
- [x] `P01.S04` - Add local corpus copy and catalogue authority for the Modelo 145 record design; `corpus/aeat_official registry/aeat/legal`.
- [x] `P01.S05` - Add current BOE legal authority and relevant amendments for Modelo 145, with derogated historical authority only as historical context if retained; `corpus/aeat_official registry/aeat/legal`.
- [x] `P01.S06` - Verify source catalogue checksums and legal catalogue integrity for all Modelo 145 authority entries; `tests/domain/calculations/registry`.

### Phase `P02` - communication vocabulary

This Phase adds non-filing vocabulary only if current schema vocabulary cannot represent Modelo 145 cleanly without overloading filing constructs.

- [x] `P02.S07` - Evaluate whether existing registry vocabulary can represent payer communication without filing semantics; `src/aeat/domain/calculations/registry`.
- [x] `P02.S08` - Add narrow payer communication vocabulary when existing vocabulary would force filing terminology; `src/aeat/domain/calculations/registry`.
- [x] `P02.S09` - Add non-filing communication validation rules for rejected filing, deadline, live-read, and portal surfaces; `src/aeat/domain/calculations/registry`.
- [x] `P02.S10` - Verify communication vocabulary accepts payer communication semantics and rejects filing-shaped Modelo 145 declarations; `tests/domain/calculations/registry`.

### Phase `P03` - registry TOML

This Phase adds the Modelo 145 registry foundation as a non-filing local payer communication.

- [ ] `P03.S11` - Add Modelo 145 registry TOML using only source-backed communication, validation, and export authority; `registry/aeat/modelos`.
- [ ] `P03.S12` - Model Modelo 145 lifecycle as local payer communication rather than AEAT filing; `registry/aeat/modelos`.
- [ ] `P03.S13` - Add export layout metadata grounded in the official record design; `registry/aeat/modelos`.
- [ ] `P03.S14` - Exclude filing schedules, deadline windows, live cross references, filing application links, and portal read or write links from Modelo 145; `registry/aeat/modelos`.
- [ ] `P03.S15` - Verify Modelo 145 registry load, source grounding, export metadata, and rejected filing surfaces; `tests/domain/calculations/registry`.

### Phase `P04` - backend service

This Phase implements real backend-owned local communication behavior before any CLI exposure.

- [ ] `P04.S16` - Add backend service ownership for Modelo 145 local payer communication; `src/aeat/application/modelo`.
- [ ] `P04.S17` - Add create behavior for bucket-scoped Modelo 145 communication records; `src/aeat/application/modelo`.
- [ ] `P04.S18` - Add validate behavior backed by registry and source authority; `src/aeat/application/modelo`.
- [ ] `P04.S19` - Add export behavior backed by the Modelo 145 registry layout; `src/aeat/application/modelo`.
- [ ] `P04.S20` - Add local delivered-to-payer and completed communication state transitions; `src/aeat/application/modelo`.
- [ ] `P04.S21` - Emit communication-specific bucket events without filing or filed-state terminology; `src/aeat/application/modelo`.
- [ ] `P04.S22` - Add service-level errors and logs using communication vocabulary only; `src/aeat/application/modelo`.

### Phase `P05` - thin CLI

This Phase exposes only thin CLI delegation after backend behavior exists.

- [ ] `P05.S23` - Add Modelo 145 command handlers that delegate to the backend communication service; `src/aeat/entrypoints/cli`.
- [ ] `P05.S24` - Keep Modelo 145 argument parsing separate from business behavior; `src/aeat/entrypoints/cli`.
- [ ] `P05.S25` - Render Modelo 145 command results through centralized output emitters; `src/aeat/entrypoints/cli`.
- [ ] `P05.S26` - Route Modelo 145 command failures through the central command error boundary; `src/aeat/entrypoints/cli`.
- [ ] `P05.S27` - Validate Modelo 145 help text avoids file, filing, deadline, live-read, and AEAT submission vocabulary; `tests/entrypoints/cli`.

### Phase `P06` - real verification and no shims

This Phase proves the successor behavior is real, local, and free of forbidden surfaces.

- [ ] `P06.S28` - Add real service tests for create, validate, export, delivered-to-payer, and locally completed behavior; `tests/application/modelo`.
- [ ] `P06.S29` - Add CLI behavior tests exercising Modelo 145 through real backend services; `tests/entrypoints/cli`.
- [ ] `P06.S30` - Add negative tests proving Modelo 145 has no filing, deadline, live-read, portal, submit, receipt, or AEAT electronic tramite surface; `tests`.
- [ ] `P06.S31` - Add negative tests proving Modelo 145 has no shims, stubs, fake support, deprecated spellings, or compatibility aliases; `tests`.
- [ ] `P06.S32` - Confirm Modelo 036 and Modelo 037 behavior and metadata remain unaffected by Modelo 145 successor work; `tests/domain/calculations/registry`.
- [ ] `P06.S33` - Run the targeted registry, application, and CLI test slices without skips, xfails, mocks, stubs, or tautological assertions; `tests`.
