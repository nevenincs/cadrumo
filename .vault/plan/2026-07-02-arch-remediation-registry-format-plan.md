---
tags:
  - '#plan'
  - '#arch-remediation-registry-format'
date: '2026-07-02'
modified: '2026-07-17'
tier: L2
related:
  - '[[2026-07-02-aeat-architecture-review-audit]]'
  - '[[2026-07-02-arch-remediation-program-adr]]'
  - '[[2026-07-02-arch-remediation-registry-format-adr]]'
  - '[[2026-07-06-arch-remediation-registry-format-research]]'
---
# `arch-remediation-registry-format` plan

### Phase `P01` - mechanical majority migration

Migrate the eight small inline informativa and retencion revisions to the fragmented layout, one atomic commit per revision, each gated by the compiled-schema equality test and a green registry validator.

- [x] `P01.S01` - Author the parameterised compiled-schema equality harness that captures each inline revision pre-migration ModeloRevision and asserts model equality against the post-migration fragmented shape; `src/aeat/domain/calculations/registry/tests/test_inline_fragment_equality.py`.
- [x] `P01.S02` - Enumerate the actual inline revision set at HEAD by grep for inline binding and formula tables in revision.toml, confirming it against the ADR list before migrating; `src/aeat/_data/registry/aeat/modelos`.
- [x] `P01.S03` - Migrate modelo 117 inline revision to the fragmented layout in one atomic commit gated by the equality test and a green registry validator; `src/aeat/_data/registry/aeat/modelos/117`.
- [x] `P01.S04` - Migrate modelo 126 inline revision to the fragmented layout in one atomic commit gated by the equality test and a green registry validator; `src/aeat/_data/registry/aeat/modelos/126`.
- [x] `P01.S05` - Migrate modelo 128 inline revision to the fragmented layout in one atomic commit gated by the equality test and a green registry validator; `src/aeat/_data/registry/aeat/modelos/128`.
- [x] `P01.S06` - Migrate modelo 187 inline revision to the fragmented layout in one atomic commit gated by the equality test and a green registry validator; `src/aeat/_data/registry/aeat/modelos/187`.
- [x] `P01.S07` - Migrate modelo 188 inline revision to the fragmented layout in one atomic commit gated by the equality test and a green registry validator; `src/aeat/_data/registry/aeat/modelos/188`.
- [x] `P01.S08` - Migrate modelo 194 inline revision to the fragmented layout in one atomic commit gated by the equality test and a green registry validator; `src/aeat/_data/registry/aeat/modelos/194`.
- [x] `P01.S09` - Migrate modelo 231 inline revision to the fragmented layout in one atomic commit gated by the equality test and a green registry validator; `src/aeat/_data/registry/aeat/modelos/231`.
- [x] `P01.S10` - Migrate modelo 361 inline revision to the fragmented layout in one atomic commit gated by the equality test and a green registry validator; `src/aeat/_data/registry/aeat/modelos/361`.

### Phase `P02` - calc-grade surface migration

Migrate the two large calc-grade inline surfaces (M303 2009-y-siguientes and the M369 schemas) with the same equality gate plus their filing-grade suites.

- [x] `P02.S11` - Migrate the M369 inline schemas to the fragmented layout in one atomic commit gated by the equality test plus the M369 filing-grade suites; `src/aeat/_data/registry/aeat/modelos/369`.
- [x] `P02.S12` - Migrate the M303 2009-y-siguientes inline revision to the fragmented layout in one atomic commit gated by the equality test plus the M303 filing-grade suites, scheduled per board state because it validates against the whole revision and waits on dirty peer WIP in that tree; `src/aeat/_data/registry/aeat/modelos/303`.

### Phase `P03` - closeout: delete inline support and converge the rule

At zero inline revisions, delete the loader inline-parsing branches, add the loud inline-refusal load error, converge the discovery rule at its vaultspec source, and delete the parameterised equality test.

- [x] `P03.S13` - Confirm zero inline revisions remain by grep before deleting inline support; `src/aeat/_data/registry/aeat/modelos`.
- [x] `P03.S14` - Delete the loader inline-parsing branches now that no revision declares bindings or formulas inline; `src/aeat/domain/calculations/registry/_loader.py`.
- [x] `P03.S15` - Add a loud loader refusal that raises a load error naming the fragmented layout when an inline bindings or formulas table appears in revision.toml; `src/aeat/domain/calculations/registry/_loader.py`.
- [x] `P03.S16` - Converge the registry-revision-content-inline-or-fragmented discovery rule at its vaultspec source to record the convergence and retire the dual-format caveat, then run vaultspec-core sync; `.vaultspec/rules/registry-revision-content-inline-or-fragmented.md`.
- [x] `P03.S17` - Delete the parameterised compiled-schema equality harness now that migration is complete; `src/aeat/domain/calculations/registry/tests/test_inline_fragment_equality.py`.
- [x] `P03.S18` - Retroactively document the eight unplanned inline-revision migrations (136, 189, 280, 289, 296, 345, 379, 303/2023-y-siguientes) with commit evidence and equality-proof references; `.vault/exec/2026-07-02-arch-remediation-registry-format/`.

## Description

This plan converges the registry authoring tree onto the fragmented revision
layout as the single on-disk format, discharging deferral register item D6 per
the registry-format ADR. The architecture review confirmed the tree carries two
formats indefinitely: roughly ten revisions declare bindings, formulas, and
verification expectations inline in `revision.toml` while 35 modelos use
fragmented subdirectories. The loader normalises both into one strict schema, so
convergence is a pure authoring-surface move with a mechanical equality proof,
and it lets every future tool read one format instead of implementing both
forever, which is what hid two real under-declaration defects.

Phase P01 migrates the eight small inline informativa and retencion revisions
(117, 126, 128, 187, 188, 194, 231, 361 per the ADR; executors re-enumerate the
actual inline set at HEAD by grep before migrating), one atomic commit per
revision, each gated by a parameterised compiled-schema equality test that
asserts the loaded `ModeloRevision` compares equal before and after. Phase P02
migrates the two large calc-grade surfaces (M369 schemas and the M303
2009-y-siguientes revision) with the same equality gate plus their filing-grade
suites. Phase P03 is the closeout at zero inline revisions: delete the loader
inline-parsing branches, add a loud loader refusal so a future inline table
becomes a load error naming the fragmented layout, converge the discovery rule
at its vaultspec source, and delete the now-spent equality harness.

The ADR freezes the safety floor: byte-level authoring moves with zero semantic
drift, the registry validator and full registry-load suite green per commit, and
deletion of inline support is no-legacy compliant only once the inline set is
empty. The M303 2009 migration validates against the whole revision, so it is
scheduled per board state and genuinely waits on any dirty peer WIP in that tree.

## Steps

## Parallelization

P01 depends only on its own first step: the equality harness (P01.S01) and the
inline-set enumeration (P01.S02) must land before any migration. After that, the
eight per-revision migrations (P01.S03 through P01.S10) are independent atomic
commits on disjoint modelo directories and could parallelize across agents, but
they are cheap and mechanical, so single-owner sequential execution is the
simpler default and avoids equality-harness contention. P02 depends on P01's
harness but its two migrations are independent of each other; the M303 migration
additionally waits on board state per the ADR. P03 depends on every prior
migration having landed, because it asserts zero inline revisions before deleting
loader support; its steps are strictly ordered (confirm zero, delete branches,
add refusal, converge rule, delete harness). The rule convergence in P03.S16
edits the vaultspec source and runs `vaultspec-core sync`; it does not hand-edit
the generated provider copies.

## Verification

- Per migrated revision: the parameterised compiled-schema equality test asserts
  the loaded `ModeloRevision` compares equal before and after (P01.S01 harness),
  and the registry validator plus full registry-load suite stay green in the
  same commit.
- P02: the M369 and M303 migrations additionally pass their filing-grade suites
  (P02.S11, P02.S12).
- P03: a grep confirms zero inline `bindings`/`formulas` tables remain in any
  `revision.toml` (P03.S13); the loader raises a loud, layout-naming error on an
  injected inline table (P03.S15); the discovery rule at
  `.vaultspec/rules/registry-revision-content-inline-or-fragmented.md` records
  the convergence and `vaultspec-core sync` propagates it (P03.S16); the equality
  harness is deleted (P03.S17).
- The plan is complete when every Step is closed and each Step carries an exec
  record per the plan-closure discipline.
