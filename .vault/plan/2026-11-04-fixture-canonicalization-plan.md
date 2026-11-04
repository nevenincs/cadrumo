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
modified: '2026-11-04'
body_schema: body-v2
body_hash: 'sha256:e2c497420229ad0eb7a36ffd2d38f2208eb5f4e9618387767daef94eee7b85c2'
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
- [x] `P01.S04` - Review possibly real identifiers and evidence for private data and replace any non-synthetic value; `native/desktop/frontend/src/dev/fixtures, src/cadrumo/tests/fixtures/aeat-sede, the ledger evidence corpus and native/manager/tests`.

### Phase `P02` - Seeding and test controls

Separate fixture seeding from testing in the justfile and CI with digest-based freshness.

- [ ] `P02.S05` - Add the fixture projection registry with digest stamps and the seed, force, status, check and clean recipes; `dev/fixtures, justfile and .importlinter`.
- [ ] `P02.S06` - Make frontend and native test recipes seed first, seed on setup, and run the fixture check in the local and merge gates with a per-PR frontend and Rust job; `justfile and .github/workflows`.

### Phase `P03` - Persona catalogue

Define every canonical taxpayer and flow once and seed it through production operations into every consumer.

- [x] `P03.S07` - Author the identity catalogue and the canonical personas with ledger rows, document references and expected obligations; `dev/fixtures/personas`.
- [x] `P03.S08` - Add the persona reader and the materialiser that replays a persona through the profile patch, ledger import and evidence operations; `src/cadrumo/tests and src/cadrumo/entrypoints/tests`.
- [ ] `P03.S09` - Generate the window envelopes and desktop fixtures from personas; `native/desktop/frontend/scripts and dev desktop fixture producers`.
- [ ] `P03.S10` - Generate docs seed recipes and sandbox facts from personas and refresh the goldens; `dev/docs/sequences and docs/_sequences`.
- [ ] `P03.S11` - Seed the TUI harness from personas; `dev/tui/harness`.
- [ ] `P03.S21` - Close the persona expressiveness gaps: fix the reverse-charge category missing from the self-assessed projection, express recargo and withholding certificates through their operations, and adjust catalogue rows that use categories or counterparties the operations refuse; `registry category projection, ledger classification and invoice operations, dev/fixtures/personas`.

### Phase `P04` - Projections out of git

Generate window and Rust fixture projections into the build tree and stop committing them.

- [ ] `P04.S12` - Generate projections into the build tree and resolve them through a Vite and TypeScript alias; `native/desktop/frontend and CMakeLists.txt`.
- [ ] `P04.S13` - Pass projection paths to Rust tests through CMake environment variables instead of include_str; `native/desktop/src-tauri/src/modelo/tests.rs and CMakeLists.txt`.
- [ ] `P04.S14` - Ignore and delete the tracked projections; `.gitignore and native/desktop/frontend/src/dev/fixtures`.

### Phase `P05` - Python builder migration

Move the backend test profile builders onto the persona catalogue and remove restated facts.

- [ ] `P05.S15` - Migrate the shared profile builders and their consumers onto personas and remove the duplicate ready-profile seeder and string boolean placeholders; `src/cadrumo user_profile, profile_persistence and profile persistence test support`.
- [ ] `P05.S16` - Migrate private profile helpers package by package onto personas; `src and dev test packages`.
- [ ] `P05.S17` - Stop seeding personas through direct test storage writes; `src test support`.
- [ ] `P05.S20` - Extend the identity gate's blocking scope to tests and fixtures by checking every match against the catalogue convention, and replace the remaining random-looking identifiers; `dev/identity and test and fixture identifiers`.

### Phase `P06` - Obligation simulation

Assert hand-grounded expected obligations per persona and period through the real application, then verify the whole change.

- [ ] `P06.S18` - Add the persona by year by period obligation suite asserting expected obligations through the real overview, calendar and calculation; `src/cadrumo/application/overview/tests and dev/fixtures/personas`.
- [ ] `P06.S19` - Run the full gates once and close the plan; `justfile`.

## Parallelization

P01 Steps are independent and may run in parallel. P02 follows P01.S01. P03.S07 (persona authoring) may run alongside P01 and P02; P03.S08 needs S07; P03.S09 to S11 need S08 and run in parallel with disjoint write scopes. P04 needs P02 and P03.S09. P05 needs P03.S08; its Steps run in parallel by package with disjoint ownership. P06.S18 needs P03.S07 and S08; P06.S19 is last. Agents commit serially in the worktree.

## Verification

- Every generator output is byte-identical across two consecutive runs (`fixtures-check`).
- No tracked file under `native/desktop/frontend/src/dev/fixtures/modelo/` or other declared projection paths; no hand copy of a projection anywhere.
- One identity per role: no persona identity appears in a second role across `dev/fixtures/personas/`, tests, docs or window fixtures.
- No persona is seeded by a direct storage write; no year literal in persona files.
- `just fixtures-status` reports fresh after `just setup`; `just test-frontend` and `just test-native` seed on a cold tree.
- Final gates green once at the end: import boundaries, style, format, types, `test-unit`, integration lanes, registry gate, docs sequence check, frontend check and native host tests. Regressions are reported separately from evidenced pre-existing failures.
- Final integrated review passes.
