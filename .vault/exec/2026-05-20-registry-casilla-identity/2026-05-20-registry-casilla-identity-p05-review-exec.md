---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` P05 Code Review

Holistic safety, intent, and quality audit of Phase P05 — verification
and rollout — covering Steps S20, S21, S22, S23, S31, S24, S25 across
`test_referential_integrity.py`, `test_tautology_gate.py`,
`_record_design.py`, `completeness-manifest.toml`, `__init__.py`,
`test_record_design.py`, and `test_modelo_200_registry.py`.

## Status: PASS

No CRITICAL or HIGH findings. Two MEDIUM-severity *findings about the
existing codebase* were surfaced during S22 and fixed in the same Step;
one structural finding (S23) is recorded as a follow-up inventory. The
phase is safe to merge.

## Scope

Audited the seven P05 commits: `39fdf0bb1` (S20), `67de38897` (S21),
`2534df927` (S22), `deb7f0afd` (S23), `e58b70ba4` (S31), `83938d546`
(S24), `41d1fa2ce` (S25). Concurrent non-`#476` commits in the shared
worktree were excluded from scope. The audit verified the implementation
against the ADR amendment of 2026-05-20, which is the authority for the
calculation-completeness gate.

## Safety Domain

- **No crash paths introduced.** `build_diseno_coverage_report` and the
  refocused `derive_calculation_completeness_casillas` iterate validated
  typed collections; dict `.get` returns `None` and is handled. The S21
  anti-tautology test copies the fragment tree to a `tmp_path` and never
  mutates the committed corpus.
- **No import cycle.** `_record_design.py` gained
  `build_diseno_coverage_report` / `DisenoCoverageReport`; both reuse the
  existing module imports (`ModeloRevision`, `extract_record_design`).
  The intra-package graph remains a DAG.
- **No live AEAT write surface.** P05 touches registry data, validation,
  and tests only.
- **Rollout safety holds.** The calculation-completeness gate is live for
  exactly one modelo — Modelo 200, the one carrying a checked-in
  `completeness_manifest` — and rollout-staged dormant for the other 25.
  All 26 modelos load and validate clean (confirmed by S25's
  registry-wide `RegistryValidator` sweep and the 107-test registry
  suite).

## Intent Domain

- **S20 strict roundtrip is non-tautological.** The test populates
  `segmento` with the non-default `DP200014`, pushes through
  `freeze_toml(model_dump(...))` — the genuine loader normalisation — then
  `model_validate`, and asserts strict pydantic equality. It would fail
  if `segmento` were dropped on serialise or re-defaulted on load, which
  is exactly the roundtrip-discipline contract.
- **S21 anti-tautology proof exercises the correct gate.** Dropping the
  `segmento` line from the Liquidación `00562` fragment collapses its
  identity to `(None, 00562)`, colliding with the ECPN occurrence. The
  two casillas keep distinct `id` values, so the duplicate-`id` check
  cannot fire — only the generalised `(segmento, number)` uniqueness gate
  catches it. The paired sound-registry test proves the gate accepts the
  committed tree, so the proof distinguishes broken from sound. Non-
  tautological. The test mutates on-disk fragments and constructs no
  schema-authority objects, so it stays clear of the schema-hygiene gate.
- **S22 derivation-tool corrections are correct and ADR-conformant.**
  Two real defects in the P06.S28 derivation tool were found while
  deriving the M200 manifest and fixed in the same Step:
  - `calculation_closure_numbers` folded `RelationDefinition.source_output`
    into the modelo's closure. Verified against `RelationDefinition`:
    every relation carries a `source_modelo` and `source_output` is a
    casilla on that *foreign* modelo. The M200 `rel-202-pagos-fraccionados`
    relation has `source_modelo = "202"`, `source_output = "34"` — a
    Modelo 202 casilla. Removing it from the M200 closure is correct; the
    cross-modelo edge correctly enters via `relation.target_binding`.
  - `derive_calculation_completeness_casillas` over-generated for
    multi-segment modelos: it emitted a pair for *every* Diseño sheet
    carrying a closure number, so M200's two-casilla closure yielded six
    pairs. The segment-aware fix pins a closure number to the segment(s)
    the registry's calculation surface declares it under — the ADR-
    amendment "Diseño intersected with the modelo's calculation surface".
    An undeclared or single-segment number keeps the every-sheet fallback,
    so the M200 missing-casilla defect class still surfaces.
  - With both fixes the M200 manifest derives to exactly
    `{(DP200014B, 00592), (DP200014B, 00599)}`, and M200 clears the gate.
    The off-load-path drift test re-derives and matches.
- **S23 finding is accurate, not a cover for a registry gap.** Verified:
  the calculation-completeness manifest is `closure ∩ Diseño five-digit
  [NNNNN] tags`. Modelo 200 is the only modelo whose registry casilla
  `number`s are genuine five-digit AEAT Diseño tags; every other
  calculation-bearing modelo identifies casillas by semantic slug or
  short ordinal, so its Diseño carries zero `[NNNNN]` tags and the
  derivation yields an empty intersection. Verified directly for M303:
  its 17 closure casillas are all declared and all grounded — there is no
  registry defect, only a tooling-vocabulary gap. The plan's S23 mandate
  is satisfied: no manifest was authored for a modelo with an underived
  closure (authoring one would fail the non-empty validator or the drift
  test), the gate was not weakened, and the per-modelo inventory is
  recorded.
- **S31 advisory report matches the ADR amendment.**
  `build_diseno_coverage_report` is off-load-path, never reds a load, and
  partitions the full Diseño set into covered and gap subsets — the
  full-Diseño-coverage-as-advisory-inventory the amendment prescribes,
  separate from the load-blocking calculation-completeness gate.
- **S24 tests assert the real M200 outcome.** They build a real snapshot
  and assert the six cuota-chain casillas resolve under their
  `DP200014` / `DP200014B` segments and that the page-014 export field
  `modelo-200-page-014-casilla-00562` binds the Liquidación
  `DP200014:00562` occurrence, not the ECPN one — proving the P04 export
  re-point landed.
- **No plan drift.** No feature beyond the seven planned Steps was added.

## Quality Domain

### Observations (no action required)

- No mocks, skips, xfail markers, or tautological assertions across the
  P05 test changes. Every test loads or validates the real registry, or
  roundtrips through the real loader primitive.
- Spanish-stem terminology respected: `segmento` throughout;
  `multi_segment` is an infrastructure boolean parameter, ADR-conformant.
- No transient dev metadata in identifiers, comments, or test names.
- The S23 finding records a genuine follow-up: generalising
  `derive_calculation_completeness_casillas` (and the
  `calculation_closure_numbers` `id`/`number` token-form handling) to the
  non-five-digit casilla-number vocabularies so the calculation-
  completeness gate can roll out beyond Modelo 200. This is correctly
  logged as a follow-up, not silently absorbed.
- The segment-aware derivation omits a closure casilla whose declared
  segment is absent from the Diseño. This is the documented contract — a
  number the official form does not declare under that segment cannot be
  assigned to it — and the drift test catches any manifest that includes
  such a pair. Acceptable; the gate stays honest.

## Verification

- `pytest test_modelo_parity_coverage.py test_schema_hygiene.py
  test_modelo_200_registry.py test_referential_integrity.py
  test_tautology_gate.py test_record_design.py` — 107 tests pass.
- Registry-wide `RegistryValidator` sweep: all 26 modelos validate clean;
  the gate is enforcing for Modelo 200 (the one manifest) and rollout-
  staged dormant for the other 25.
- `ruff check` clean on every touched production and test file.
- `vault plan check` passes (one expected PLAN022 warning: Phase `P06`
  carries the append-only id `P06` but sits before `P05` in document
  order, by design per the convention ADR and explained in the plan's
  Parallelization section).
