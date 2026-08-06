---
tags:
  - '#audit'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:60c84485a41021b90f515072198dddb75298c352d48f03a062c1a5744c382c9a'
related:
  - "[[2026-08-04-modelo-localization-cascade-adr]]"
  - "[[2026-08-04-modelo-localization-cascade-research]]"
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
  - "[[2026-08-05-modelo-localization-cascade-execution-closeout-audit]]"
  - "[[2026-08-05-modelo-localization-cascade-implementation-cutover-audit]]"
---

# `modelo-localization-cascade` audit: `Final implementation review`

## Scope

This is a final implementation and safety review of the Modelo localization
cascade from the feature migration commits `777b6de826` through
`ced27b5a59`, plus the resulting live root-only registry, loader, resolver,
catalogue, CLI, scanner, export, and new-Modelo surfaces. The authorizing
corpus was read in full: `2026-08-04-modelo-localization-cascade-adr`,
`2026-08-04-modelo-localization-cascade-research`,
`2026-08-04-modelo-localization-cascade-migration-feasibility-research`,
`2026-08-04-modelo-localization-cascade-reference`,
`2026-08-04-modelo-localization-cascade-plan`,
`2026-08-05-modelo-localization-cascade-execution-closeout-audit`, and
`2026-08-05-modelo-localization-cascade-implementation-cutover-audit`.
The repository `AGENTS.md`, applicable `.codex` rules, and the required
`vaultspec-rag` discovery probes were used before source inspection.

The review checked the disposable migration records and deletion boundary,
the live identity codec and fallback resolver, loader enrollment, schema
language neutrality, continuity data, shared catalogue state, omission of
revision-local locale data, source-aware identical-value adjudication, and
the surviving real-behavior tests. No production code or tests were changed.
Unrelated shared-worktree WIP was excluded and preserved. The worktree moved
while this review was running, so command results below are point-in-time
evidence; no full-repository suite is claimed.

## Findings

### final-implementation-review | critical | Production cutover has no proven manually reviewable dry-run certification

The authorizing plan requires a deterministic, self-contained temporary
proposal before production mutation, including the staged tree, sealed source
manifest, unresolved review register, parity report, and summary
(`.vault/plan/2026-08-04-modelo-localization-cascade-plan.md:33,43,65-82`). Its wave order
requires staging before parity, and parity/review before disposal
(`.vault/plan/2026-08-04-modelo-localization-cascade-plan.md:39,84-117`). ADR D8/D9 likewise
requires parity-mode emission, exhaustive old-versus-new equality, source-hash
agreement, and proof before deleting an enrolled Modelo's old layout
(`.vault/adr/2026-08-04-modelo-localization-cascade-adr.md:158-182`).

The retained execution evidence says the opposite of an executed safety gate.
`W02-P03-S06` records that no staging output tree was retained and that the
row is closed by reconciliation rather than execution
(`.vault/exec/2026-08-04-modelo-localization-cascade/2026-08-04-modelo-localization-cascade-W02-P03-S06.md:28-36`).
`W02-P04-S08` records that there is no dry-run writer or live-registry
destination to invoke
(`.vault/exec/2026-08-04-modelo-localization-cascade/2026-08-04-modelo-localization-cascade-W02-P04-S08.md:28-35`),
`W02-P04-S09` says no post-cutover artifact bundle is claimed
(`.vault/exec/2026-08-04-modelo-localization-cascade/2026-08-04-modelo-localization-cascade-W02-P04-S09.md:28-36`),
and `W04-P08-S16` says the temporary-output tests were deleted with the
disposable application
(`.vault/exec/2026-08-04-modelo-localization-cascade/2026-08-04-modelo-localization-cascade-W04-P08-S16.md:28-36`). The execution closeout explicitly
confirms that no post-cutover artifact bundle or temporary-reader rerun exists
and labels the result historical reconciliation, not execution of deleted code
(`.vault/audit/2026-08-05-modelo-localization-cascade-execution-closeout-audit.md:65-73`).

Nevertheless, `ced27b5a59` deleted `dev/registry/migration`, its migration
tests, the old Modelo locale-reader surface, and the revision-local locale
files while landing the root-only production path. The live negative scans are
now clean (`NO_MODEL_LOCALE_DIRECTORIES`,
`NO_LEGACY_RUNTIME_MODEL_LOCALE_READER_REFERENCES`), but that proves only
absence after deletion. It does not prove that the proposal was manually
reviewable, that all old resolved values matched, or that rollback evidence
can reproduce the pre-cutover Modelo payload. The root-only implementation is
therefore not certified under the ADR/plan and the cutover safety boundary is
unsafe or, at minimum, unproven. The W02-W04 checked rows must not be treated
as evidence that the required pre-mutation dry run occurred.

### final-implementation-review | high | Grounded continuity is not represented as an applicable variant or tombstone enrollment

The ADR requires language-neutral enrollment records selecting a continuity
base, an explicitly applicable variant, an exact ungrounded occurrence, or a
tombstone, with non-overlapping applicability and right-biased materialization
(`.vault/adr/2026-08-04-modelo-localization-cascade-adr.md:102-118`). For a grounded field,
resolution must use the applicable continuity variant/base; exact occurrence
entries are for occurrences without grounded continuity
(`.vault/adr/2026-08-04-modelo-localization-cascade-adr.md:122-130`).

The live loader instead attaches an exact occurrence key to every casilla and
appends a continuity key when `continuidad_id` exists
(`src/cadrumo/domain/calculations/registry/_loader.py:250-308`). The live
resolver then searches that tuple in order, exact first, and has no
applicability, variant, or tombstone record
(`src/cadrumo/domain/calculations/registry/_modelo_localization.py:95-118`).
The schema retains `continuidad_id` and `casilla_continuidad_evolutions`, but
has no Modelo localization enrollment surface
(`src/cadrumo/domain/calculations/registry/_schema.py:1083-1114`;
`src/cadrumo/domain/calculations/registry/_schema_surfaces.py:237-318`).

`W02-P03-S07` also records that no post-cutover staging catalogue or temporary
variant/tombstone emitter was retained
(`.vault/exec/2026-08-04-modelo-localization-cascade/2026-08-04-modelo-localization-cascade-W02-P03-S07.md:28-36`).

Read-only live resolution of Modelo 100 casilla 1038 demonstrates the gap:
both revisions 2023 and 2024 carry exact and continuity keys. For 2024, the
Hungarian exact key resolves to `EgyÃƒÂ©b levonÃƒÂ¡sok`, while the same continuity
key resolves to `EgyÃƒÂ©b kedvezmÃƒÂ©nyek`; `get_label("hu")` returns the exact
value. That difference may be a legitimate reviewed variant, but the current
implementation has no variant identity or revision applicability with which
to adjudicate it. It is therefore a deterministic exact override, not proof
of the ADR's continuity cascade, and it leaves future revision selection
exposed to duplicate or wrong inherited text.

### final-implementation-review | high | The ADR-amended non-Modelo localization inventory is not closed

The accepted ADR amendment states that the inventory boundary extends beyond
the Modelo tree: user-profile prose (26 section titles and 162 descriptions)
and candidate calendar, IVA, and category surfaces (46, 36, and 8) must be
classified or explicitly decided as schema-resident; an omitted surface
blocks cutover (`.vault/adr/2026-08-04-modelo-localization-cascade-adr.md:132-140`).

The migration plan and its W01-W04 execution records contain only
`dev/registry/migration`/Modelo work and no inventory or explicit decision for
those surfaces. The live user-profile schema still carries literal
presentation prose, for example `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:4,26,66,75`,
and `src/cadrumo/domain/user_profile/_labels.py:12-24` deliberately states
that schema prose remains the copy authority and fallback. No corresponding
feature evidence records the required D5 classification or a formally
authorizing decision to leave these fields schema-resident. Under the
accepted ADR wording, the root-only Modelo cutover cannot be declared fully
certified while this inventory boundary remains unclosed.

### final-implementation-review | medium | Surviving tests are real but do not prove exhaustive parity or all fallback surfaces

The surviving tests use real bundled registry/catalogue data and no mocks,
fakes, stubs, patches, skips, or xfails. The focused registry and new-Modelo
run passed 15 tests. The live parity module, however, asserts four sample
Modelos and all 20 casillas only for Modelo 130
(`src/cadrumo/domain/calculations/registry/tests/test_registry_locales_parity.py:17-80`);
it is not the ADR D9 matrix over every supported Modelo, revision, casilla,
field, and locale. The migration tests that exercised the old source matrix,
manifest, and pre-emission review were deleted by `ced27b5a59`, and the
retained W04 record confirms that the temporary-output tests were deleted.

The resolver's static order does enforce requested-locale-then-Spanish and
does not fall from one non-Spanish locale into another
(`src/cadrumo/domain/calculations/registry/_modelo_localization.py:102-117`).
A real read-only probe also showed a missing Catalan, English, or Hungarian
value for Modelo 036 `decl.causa-110` resolving to the same Spanish source.
That is useful bounded evidence, not exhaustive proof of strict Spanish
missing-key behavior, null/key-echo suppression, optional help, year
parameterization, special identity encoding, aliases, constructs, and every
revision/field. One combined focused locale run in this moving worktree
returned 14 passed and one key-echo failure; an immediate isolated rerun of
that test passed. This instability reinforces the boundary: no current full
certification or full-suite claim is justified.

### final-implementation-review | low | The historical 14/64/44 equality findings do not block the current source-aware equality gate

The earlier cutover audit's 14 Catalan, 64 Spanish, and 44 Hungarian
equal-to-English counts predate source-aware adjudication
(`.vault/audit/2026-08-05-modelo-localization-cascade-implementation-cutover-audit.md:65-74`).
The later adjudication record correctly treats Spanish Modelo values as the
official source, not as Spanish translation debt, and says those counts are
not current authority (`.vault/research/2026-08-05-modelo-localization-cascade-identical-source-adjudication-research.md:19-49,64-100`).

The live read-only commands `uv run --no-sync python -m cadrumo.locales status`
and `uv run --no-sync python -m cadrumo.locales audit` reported
`identical_pending=0` for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`, and
`ok` for all four catalogues. A direct source-aware inventory of the current
catalogues found 30/30 Catalan generic equalities allowlisted, 51/51 Spanish
generic equalities allowlisted, and 30/30 Hungarian generic equalities
allowlisted, with no unallowlisted equality in those buckets. The 14/64/44
figures therefore do not block the equality gate. They also do not repair the
missing pre-mutation certification, continuity enrollment, or D5 inventory
findings above.

## Recommendations

1. Treat the cutover as certification-blocked until an authorized recovery or
   independently reproducible evidence package establishes the pre-cutover
   oracle, manually reviewable temporary proposal, source hashes, exhaustive
   old/new parity, and rollback boundary required by D8/D9. Do not infer this
   proof from the absence of `dev/registry/migration` or from the checked
   W02-W04 reconciliation rows.

2. Resolve the continuity representation under the ADR: record grounded bases,
   explicitly applicable variants, exact ungrounded occurrences, and
   tombstones in language-neutral enrollment data, with legal applicability
   and semantic adjudication. Then rerun the complete per-Modelo parity matrix
   before accepting any value deduplication or deletion boundary.

3. Close the amended D5 inventory with either shared-key enrollment or a
   separately authorized ADR decision for every non-Modelo prose surface,
   including the user-profile descriptions. Keep the Modelo cutover marked
   un-certified until the omission rule is resolved.

4. Retain real-behavior tests for the resolver's requested-locale/Spanish
   fallback, strict Spanish failure, null and key-echo handling, codec
   identity, alias/construct/revision surfaces, and exhaustive registry
   coverage. Rerun the bounded gates after concurrent WIP settles and report
   the exact selectors and results; do not call the historical 424-test
   campaign or any focused run a full-suite result.

5. Keep the source-aware equality adjudication and treat the old 14/64/44
   numbers as historical only. No automatic translation edits are warranted
   by those stale counts, and their zero-pending replacement must not be used
   as a substitute for migration certification.
