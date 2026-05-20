---
tags:
  - '#plan'
  - '#registry-casilla-identity'
date: '2026-05-20'
tier: L2
related:
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
  - '[[2026-05-20-branch-reconciliation-audit]]'
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

# `registry-casilla-identity` plan

Implement segment-scoped casilla identity and a fail-closed
Diseno-completeness gate in the calculations registry, then register the
Modelo 200 Liquidacion cuota-chain casillas the current `id == number`
model could not hold.

## Proposed Changes

The authorising ADR decides two coupled sub-decisions. A2b makes a
casilla's identity the pair `(segmento, number)`: `CasillaDefinition`
gains an optional `segmento: str | None` field carrying the AEAT
record-segment code (e.g. `DP200014`), the registry uniqueness invariant
generalises from `id`-unique to `(segmento, number)`-unique per modelo
revision, and reference resolution becomes segment-aware so a bare-number
formula or export reference resolves within its segment context. The
change is purely additive: the ~25 single-segment modelos leave
`segmento` unset and `(None, number)` uniqueness reproduces today's
bare-number behaviour exactly. B3 adds an extraction-derived,
checked-in Diseno-completeness manifest per modelo and a fail-closed hard
gate in `RegistryValidator` at snapshot build that fails the load when a
modelo's declared casillas diverge from its manifest, with an
off-load-path audit re-verification that re-derives the manifest from the
corpus to catch drift.

The work proceeds in five Phases. P01 lands the additive schema field
first to minimise collision with the concurrent Registry-hardening
commits. P02 changes the uniqueness invariant and defines segment-aware
reference resolution. P03 builds the completeness manifest, the hard
gate, and the drift re-verification. P04 registers the Modelo 200
Liquidacion III/IV page-14 cuota-chain casillas and re-points the M200
page-014 export binding. P05 adds the strict roundtrip and anti-tautology
proofs, the M200 manifest, the per-modelo gate rollout, and the
all-26-modelos validity confirmation. The work is constrained by the
schema-hardening ADR (strict-pydantic, hard-error-at-load discipline),
the Spanish-stem terminology ADR (`segmento`, not `segment`), and the
modelo-registry-fragment-architecture ADR (per-record-kind fragment
trees). No live AEAT write surface is touched; this is registry-data and
validation only.

This plan executes in a shared worktree. Other agents concurrently
commit Registry-hardening changes to `_schema.py` and the registry
validator. Execute must run a collision check (`git diff` against the
target files) and wait for a clean window before each Step that edits a
contended file; the additive schema field is sequenced first, the
validator change is isolated to its own Step, and the M200 casilla data
is authored in dedicated fragment files so it never collides with code
edits.

## Steps

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

### Phase `P01` - Schema - additive segmento field

Add the optional segmento field to CasillaDefinition under strict-pydantic discipline; additive and landed first to minimise collision with concurrent Registry-hardening commits.

- [x] `P01.S01` - Add optional strict-pydantic field segmento (str or None, default None) to CasillaDefinition carrying the AEAT record-segment code with a Spanish-stem name per the terminology ADR; `src/aeat/domain/calculations/registry/_schema.py`.
- [ ] `P01.S02` - Document the segmento field contract (composed id for multi-segment casillas, unset for single-segment) in the registry schema module docstring or field comment without embedding plan metadata; `src/aeat/domain/calculations/registry/_schema.py`.
- [ ] `P01.S03` - Add a focused strict-pydantic test asserting segmento defaults unset, accepts a DP-code string, and that a single-segment CasillaDefinition validates unchanged; `src/aeat/domain/calculations/registry/test_registry_schema.py`.

### Phase `P02` - Validator and reference resolution

Change the casilla-uniqueness invariant from id to (segmento, number) and define segment-aware reference resolution for formula, export, and relation args keyed on a bare casilla number.

- [ ] `P02.S04` - Generalise the casilla duplicate-id invariant to (segmento, number) uniqueness per modelo revision so a casilla with segmento unset reproduces today's bare-number uniqueness exactly; `src/aeat/domain/calculations/registry/_validate.py`.
- [ ] `P02.S05` - Define segment-aware reference resolution so a bare-number formula, export, or relation arg resolves within its segment context and only genuinely cross-segment references need the composed id; `src/aeat/domain/calculations/registry/_validate.py`.
- [ ] `P02.S06` - Apply segment-aware casilla lookup to the runtime graph dependency walk so expression_casilla_refs resolves multi-segment numbers correctly; `src/aeat/domain/calculations/registry/_runtime_graph.py`.
- [ ] `P02.S07` - Add validator tests covering (segmento, number) uniqueness, the single-segment (None, number) collision still failing, and segment-aware reference resolution; `src/aeat/domain/calculations/registry/test_referential_integrity.py`.

### Phase `P03` - Diseno-completeness gate

Build the extraction-derived per-modelo Diseno-completeness manifest, the fail-closed hard gate in RegistryValidator at snapshot build, and the off-load-path drift re-verification.

- [ ] `P03.S08` - Add a Diseno-completeness manifest schema model enumerating the expected (segmento, number) casilla set per modelo revision under strict-pydantic discipline; `src/aeat/domain/calculations/registry/_schema.py`.
- [ ] `P03.S09` - Build an off-load-path manifest-derivation tool that runs the record-design extraction against the corpus Diseno workbooks and emits the per-modelo completeness manifest as reviewed checked-in data; `src/aeat/domain/calculations/registry/_record_design.py`.
- [ ] `P03.S10` - Add a fail-closed completeness gate to RegistryValidator that hard-errors at snapshot build when declared casillas diverge from the manifest or when a casilla-bearing revision has no manifest; `src/aeat/domain/calculations/registry/_validate.py`.
- [ ] `P03.S11` - Add an off-load-path drift re-verification test that re-derives every manifest from the corpus Diseno and fails CI on divergence, with explicit manual-extraction markers for PDF-only Disenos; `src/aeat/domain/calculations/registry/test_record_design.py`.
- [ ] `P03.S12` - Add completeness-gate tests covering a missing manifest failing closed, a missing casilla failing, and an extra casilla failing; `src/aeat/domain/calculations/registry/test_referential_integrity.py`.

### Phase `P04` - Modelo 200 casilla registration

Register the M200 Liquidacion III/IV page-14 cuota-chain casillas from the corpus AEAT 2024 Diseno xlsx and re-point the M200 page-014 export binding off the ECPN occurrence.

- [ ] `P04.S13` - Register the M200 Liquidacion base imponible casilla 00552 under segmento DP200014 as a new fragment file carrying legal_refs and source_refs from the corpus 2024 Diseno xlsx; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00552-base-imponible.toml`.
- [ ] `P04.S14` - Register the M200 Liquidacion tipo de gravamen casilla 00558 under segmento DP200014 as a new fragment file carrying legal_refs and source_refs from the corpus 2024 Diseno xlsx; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00558-tipo-de-gravamen.toml`.
- [ ] `P04.S15` - Register the M200 Liquidacion cuota integra casilla 00562 under segmento DP200014 as a new fragment file carrying legal_refs and source_refs from the corpus 2024 Diseno xlsx; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00562-cuota-integra.toml`.
- [ ] `P04.S16` - Register the M200 Liquidacion cuota liquida casilla 00592 under segmento DP200014B as a new fragment file carrying legal_refs and source_refs from the corpus 2024 Diseno xlsx; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00592-cuota-liquida.toml`.
- [ ] `P04.S17` - Register the M200 Liquidacion cuota del ejercicio casilla 00599 under segmento DP200014B as a new fragment file carrying legal_refs and source_refs from the corpus 2024 Diseno xlsx; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00599-cuota-del-ejercicio.toml`.
- [ ] `P04.S18` - Register the M200 Liquidacion cuota diferencial casilla 00611 under segmento DP200014B as a new fragment file carrying legal_refs and source_refs from the corpus 2024 Diseno xlsx; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00611-cuota-diferencial.toml`.
- [ ] `P04.S19` - Re-point the M200 page-014 export field binding for casilla 00562 from the ECPN occurrence to the new Liquidacion DP200014 casilla; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0017-modelo-200-page-014.toml`.

### Phase `P05` - Verification and rollout

Add strict roundtrip and anti-tautology proofs, the M200 manifest, the per-modelo gate rollout, and the all-26-modelos validity confirmation.

- [ ] `P05.S20` - Add a strict roundtrip test for the extended CasillaDefinition that populates segmento with a non-default value, pushes through the real load cycle, and asserts strict pydantic equality across the boundary; `src/aeat/domain/calculations/registry/test_registry_schema.py`.
- [ ] `P05.S21` - Add an anti-tautology proof that mutates a fragment to drop or collide segmento and asserts the (segmento, number) uniqueness gate surfaces a hard error; `src/aeat/domain/calculations/registry/test_tautology_gate.py`.
- [ ] `P05.S22` - Author the Modelo 200 Diseno-completeness manifest from the corpus 2024 Diseno xlsx and confirm it hard-fails until the Liquidacion casillas are registered; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/completeness-manifest.toml`.
- [ ] `P05.S23` - Author Diseno-completeness manifests for the remaining casilla-bearing modelos so the fail-closed gate has a manifest for every modelo it gates; `src/aeat/_data/registry/aeat/modelos/`.
- [ ] `P05.S24` - Extend the M200 registry test to assert the Liquidacion cuota-chain casillas resolve under their DP200014 segmento and the page-014 export binding resolves 00562 to the Liquidacion occurrence; `src/aeat/domain/calculations/registry/test_modelo_200_registry.py`.
- [ ] `P05.S25` - Run the full registry parity-coverage suite to confirm all 26 modelos load valid after the gate flips to hard-error per modelo; `src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py`.

## Parallelization

This is an `L2` plan with hard inter-Phase ordering, so the Phases run
in sequence rather than in parallel. P01 (additive schema field) must
land before P02, because the uniqueness invariant in P02 reads the new
`segmento` field. P02 must land before P03, because the completeness
gate compares declared `(segmento, number)` pairs and depends on the
generalised uniqueness key. P03 must land before P04, because P04's
casilla registration is what makes the M200 manifest satisfiable. P04
must land before P05, because the roundtrip proofs and the per-modelo
gate rollout verify the registered M200 casillas. Within a Phase, Steps
are ordered: in P01 the schema field precedes its targeted test; in P04
the six casilla-registration Steps share no interdependency and may be
authored concurrently, but the export re-point Step depends on all six.

Shared-worktree sequencing overrides intra-Phase concurrency: Execute
runs `git diff` against `_schema.py` and `_validate.py` before any Step
that edits them and waits for a clean window, because other agents
concurrently commit Registry-hardening changes to those files. The M200
casilla fragments and the manifest files are new paths and do not
contend with code edits.

## Verification

The plan is complete when every Step in every Phase is closed
(`- [x]`) and the following criteria hold:

- `CasillaDefinition` carries an optional `segmento` field under the
  strict / frozen / `extra="forbid"` registry discipline; a
  single-segment modelo with `segmento` unset validates identically to
  its pre-change behaviour.
- The registry validator enforces `(segmento, number)` uniqueness per
  modelo revision; a `(None, number)` collision still fails exactly as
  the prior bare-number duplicate-id check did.
- `RegistryValidator` fails the snapshot build, fail-closed, when a
  modelo's declared casillas diverge from its Diseno-completeness
  manifest or when a casilla-bearing revision has no manifest.
- The off-load-path drift re-verification re-derives every manifest from
  the corpus Diseno and fails CI on divergence.
- The Modelo 200 Liquidacion casillas `00552`, `00558`, `00562`,
  `00592`, `00599`, `00611` are registered under their `DP200014` /
  `DP200014B` segmento codes, each carrying its `legal_refs` and
  `source_refs` provenance; the M200 page-014 export binding resolves
  `00562` to the Liquidacion casilla, not the ECPN occurrence.
- Strict roundtrip tests and an anti-tautology proof for the extended
  `CasillaDefinition` pass with real adapters and no mocks, skips, or
  xfail markers.
- All 26 modelos load valid throughout the rollout; the completeness
  gate flips to hard-error per modelo only after that modelo clears its
  manifest.
- No live AEAT write surface is touched.

For tier-specific verification cadence, see the convention ADR
authorising this plan via the `related:` frontmatter.
