---
tags:
  - '#plan'
  - '#fixture-canonicalization'
date: '2026-11-04'
tier: L2
related:
  - '[[2026-11-04-fixture-canonicalization-canonical-test-personas-adr]]'
  - '[[2026-11-04-fixture-canonicalization-generated-fixture-projections-adr]]'
  - '[[2026-07-13-docs-cli-sequences-adr]]'
  - '[[2026-10-23-desktop-modelo-workspace-adr]]'
modified: '2026-11-06'
body_schema: body-v2
body_hash: 'sha256:148dd7f0988ae805ef80b0b137a15153e5f25eee3a93aa0c3b94496dca42a62b'
---

# `fixture-canonicalization` plan

## Description

Approved 2026-11-04. The operator approved the fixture-canonicalization design, both ADRs and this plan in the 2026-11-04 design session, with agent routing: Haiku read-only context agents, Sonnet agents for scoped and repetitive coding, Opus agents for generators, the materialiser, review and authoring the personas.

Scope: one canonical persona and flow catalogue under `dev/fixtures/personas/`, replayed through production operations into Python tests, docs sequences, window projections, the TUI harness and Rust tests; generated projections leave git and are seeded by just recipes with digest freshness; seeding and testing are separate controls. Governed by `2026-11-04-fixture-canonicalization-canonical-test-personas-adr` and `2026-11-04-fixture-canonicalization-generated-fixture-projections-adr`, with amendments to `2026-07-13-docs-cli-sequences-adr` and `2026-10-23-desktop-modelo-workspace-adr`. Evidence: `2026-11-04-fixture-canonicalization-research`.

Work runs in the worktree `.claude/worktrees/fixture-canonicalization` on branch `feature/fixture-canonicalization`, isolated from concurrent edits in the main checkout. Operator direction: run focused tests sparingly while code and text move; drive the refactor to a completely clean state and prove it with the full gates at the end.

## Steps

### Phase `P01` - Repairs and scenario clock

Make existing generators deterministic and remove known stale or orphan fixture data before anything builds on them.

- [x] `P01.S01` - Thread one scenario as-of instant through the Modelo envelope generator so admitted baselines and observations are byte-identical across runs; `native/desktop/frontend/scripts/modelo_fixtures.py`.
- [x] `P01.S02` - Delete the hand-copied Modelo 303 admitted baseline and read the baseline from its generated envelope; `native/application/tests/data and native/application/src/runtime_client/live_tests.rs`.
- [x] `P01.S03` - Add recorders for the five writerless ledger fixtures and a reader for the invoice preview fixture; `native/desktop/frontend/src/dev/fixtures ledger JSON and src/cadrumo/application/ledger/tests`.
- [x] `P01.S04` - Review possibly real identifiers and evidence for private data, replace any non-synthetic value with unbound convention identities, and keep catalogue role identities out of unrelated uses; `native/desktop/frontend/src/dev/fixtures, src/cadrumo/tests/fixtures/aeat-sede, the ledger evidence corpus and native/manager/tests`.

### Phase `P02` - Seeding and test controls

Separate fixture seeding from testing in the justfile and CI with digest-based freshness.

- [x] `P02.S05` - Add the fixture projection registry with digest stamps and the seed, force, status, check and clean recipes; `dev/fixtures, justfile and .importlinter`.
- [x] `P02.S06` - Make frontend and native test recipes seed first, seed on setup, and run the fixture check in the local and merge gates with a per-PR frontend and Rust job; `justfile and .github/workflows`.

### Phase `P03` - Persona catalogue

Define every canonical taxpayer and flow once and seed it through production operations into every consumer.

- [x] `P03.S07` - Author the identity catalogue and the canonical personas with ledger rows, document references and expected obligations; `dev/fixtures/personas`.
- [x] `P03.S08` - Add the persona reader and the materialiser that replays a persona through the profile patch, ledger import and evidence operations; `src/cadrumo/tests and src/cadrumo/entrypoints/tests`.
- [x] `P03.S09` - Generate the window envelopes and desktop fixtures from personas; `native/desktop/frontend/scripts and dev desktop fixture producers`.
- [x] `P03.S10` - Generate docs seed recipes and sandbox facts from personas and refresh the goldens; `dev/docs/sequences and docs/_sequences`.
- [x] `P03.S11` - Seed the TUI harness from personas; `dev/tui/harness`.
- [x] `P03.S21` - Close the persona expressiveness gaps: fix the reverse-charge category missing from the self-assessed projection, express recargo and withholding certificates through their operations, and adjust catalogue rows that use categories or counterparties the operations refuse; `registry category projection, ledger classification and invoice operations, dev/fixtures/personas`.
- [x] `P03.S22` - Add a profile-only replay mode and a digest-keyed materialised-persona cache so consumers that need only profile facts or repeat a persona do not replay the full ledger; `src/cadrumo/entrypoints/tests persona materialisation`.
- [x] `P03.S23` - Resolve the annual IVA simplified-regime summary only when the revision declares a binding of that source kind, so a taxpayer with no IVA composition calculates a Modelo 100; `src/cadrumo/application/modelo/calculation_source_mesh_actions.py and its tests`.
- [x] `P03.S24` - Seed the docs ledger, invoice, evidence and work-unit frames from a persona whose activity genuinely starts in the horizon year, so docs stop overriding persona facts and show the same flows the tests and window exercise; `dev/fixtures/personas, dev/docs/sequences, docs/_sequences`.
- [x] `P03.S25` - Resolve a Modelo relation whose source periods all precede the activity start as a not-applicable source rather than an unresolved requirement, so a Renta filer without earlier activity exports; `src/cadrumo/application/calculations/relation_prefill.py`.
- [x] `P03.S26` - Keep received operations outside IVA scope out of Modelo 303 routing and verification, so a business row such as a RETA contribution passes the 303 calculation and verification; `src/cadrumo/application/aggregation, src/cadrumo/application/modelo`.
- [x] `P03.S27` - Replay each window filer's activity and withholding from its persona ledger and documents instead of seeding synthetic income amounts in the envelope producer, so window figures equal the persona's tested figures; `native/desktop/frontend/scripts/modelo_fixtures.py, dev/fixtures/personas`.

### Phase `P04` - Projections out of git

Generate window and Rust fixture projections into the build tree and stop committing them.

- [x] `P04.S12` - Generate projections into the build tree and resolve them through a Vite and TypeScript alias; `native/desktop/frontend and CMakeLists.txt`.
- [x] `P04.S13` - Pass projection paths to Rust tests through CMake environment variables instead of include_str; `native/desktop/src-tauri/src/shell/modelo/tests.rs, native/desktop/src-tauri/src/agent/person/native.rs, native/application/src/runtime_client/live_tests.rs and CMakeLists.txt`.
- [x] `P04.S14` - Ignore and delete the tracked projections; `.gitignore and native/desktop/frontend/src/dev/fixtures`.

### Phase `P05` - Python builder migration

Move the backend test profile builders onto the persona catalogue and remove restated facts.

- [x] `P05.S15` - Migrate the shared profile builders and their consumers onto personas and remove the duplicate ready-profile seeder and string boolean placeholders; `src/cadrumo user_profile, profile_persistence and profile persistence test support`.
- [x] `P05.S16` - Migrate private profile helpers package by package onto personas; `src and dev test packages`.
- [x] `P05.S17` - Stop seeding personas through direct test storage writes; `src test support`.
- [x] `P05.S20` - Extend the identity gate's blocking scope to tests and fixtures, accept a match only by the catalogue convention, flag any catalogue value used outside its bound persona role, and replace the remaining hand-made identifiers; `dev/identity and test and fixture identifiers`.
- [x] `P05.S28` - Close the persona gaps the builder migration found: author an estimación directa normal autónomo, state the fontanero household and Renta attestations and the sociedad-limitada tributación al Estado percentage truthfully, and an established filer with prior-year activity start and Modelo 130 history, then repoint the remaining local builders and remove the interim fact overlays; `dev/fixtures/personas and src test support`.

### Phase `P06` - Obligation simulation

Assert hand-grounded expected obligations per persona and period through the real application, then verify the whole change.

- [x] `P06.S18` - Add the persona by year by period obligation suite asserting expected obligations through the real overview, calendar and calculation; `src/cadrumo/application/overview/tests and dev/fixtures/personas`.
- [x] `P06.S19` - Run the full gates once and close the plan; `justfile`.
- [x] `P06.S29` - Fix the product defects the persona obligation suite found: three-state payer facts for 111, 115 and 349; Modelo 347 excluding issued invoices with retención; the RIRPF art. 109.1 exception in the 130 applicability rule; a pure recargo retailer's deadline profile; Modelo 130 expenses resolved through the linked invoice; reverse-charge deduction evidence from the supplier's invoice; casilla 0168 derived from the estimation regime; and the casilla 1384 observation reaching 1380; `src/cadrumo/application, src/cadrumo/domain and src/cadrumo/_data/registry`.

## Parallelization

P01 Steps are independent and may run in parallel. P02 follows P01.S01. P03.S07 (persona authoring) may run alongside P01 and P02; P03.S08 needs S07; P03.S09 to S11 need S08 and run in parallel with disjoint write scopes. P04 needs P02 and P03.S09. P05 needs P03.S08; its Steps run in parallel by package with disjoint ownership. P06.S18 needs P03.S07 and S08; P06.S19 is last. Agents commit serially in the worktree.

## Verification

- Every generator output is byte-identical across two consecutive runs (`fixtures-check-determinism`, run at plan close); `fixtures-check` stays the fast check.
- No tracked file under `native/desktop/frontend/src/dev/fixtures/modelo/` or other declared projection paths; no hand copy of a projection anywhere.
- One identity per role: no persona identity appears in a second role across `dev/fixtures/personas/`, tests, docs or window fixtures.
- No persona is seeded by a direct storage write: seeding goes through production operations or the production repository writers, while storage-layer subject tests and fault-injection tests keep their deliberate direct writes; no year literal in persona files.
- `just fixtures-status` reports fresh after `just setup`; `just test-frontend` and `just test-native` seed on a cold tree.
- Final gates green once at the end: import boundaries, style, format, types, `test-unit`, integration lanes, registry gate, docs sequence check, frontend check and native host tests. Regressions are reported separately from evidenced pre-existing failures.
- Final integrated review passes.
