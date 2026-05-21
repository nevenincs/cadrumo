---
tags:
  - '#plan'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
tier: L2
related:
  - '[[2026-04-22-aeat-fichero-boe-export-adr]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
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

# `fichero-boe-export-layouts` plan

Author registry-TOML fichero-BOE export layouts for Modelo 130 and
Modelo 303 so the `aeat app modelo export` verb can serialise a
byte-accurate fichero-BOE for both modelos. This closes Gap 1 / row 7
of the branch-reconciliation audit: an unfulfilled requirement of the
accepted fichero-BOE export ADR.

## Proposed Changes

The fichero-BOE export ADR (`2026-04-22`) named modelos 130 and 303
as deliverables and declared Modelo 130 the first target. That ADR
originally described per-modelo Python format modules under
`src/aeat/adapters/outbound/aeat/export/_formats/`. The
calculation-truth registry ADR (`2026-05-03`) superseded that
authoring direction: export layouts are now reviewed registry data,
not Python modules, and the DR-spec generator (`_generate.py`) was
deleted under that ADR's migration disposition. The generic
serialiser, deserialiser, and record-spec primitives at
`src/aeat/adapters/outbound/aeat/export/_formats/` are retained and
are the runtime that consumes registry export layouts.

The work is therefore registry-data authoring grounded in the
official AEAT Diseno de Registros corpus, following the canonical
pattern already shipped for modelos 180, 202, and 232. The current
state, confirmed by codebase audit:

- Modelo 130 already carries an `export_layouts` block in
  `src/aeat/_data/registry/aeat/modelos/130.toml` (envelope header,
  page-01, envelope footer) but has no golden-SHA round-trip test
  proving byte-identity against the corpus Diseno; the layout must
  be audited for completeness against the roughly 878-byte single
  fixed-width record before it can be trusted.
- Modelo 303 carries 37 casillas in
  `src/aeat/_data/registry/aeat/modelos/303.toml` but has no
  `export_layouts` block at all and its casillas carry no
  `export_refs`. The full eight-segment multi-page envelope must be
  authored from the corpus Diseno.

The Modelo 303 fichero-BOE is the large and risky piece: an
eight-segment multi-page envelope of roughly 7994 bytes spanning the
DP30300 header, DP30301 through DP30305 page records, the DP303DID
identification record, and a page-closing trailer. The official
Diseno for both modelos is in the corpus at
`src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_130/`
and the sibling `modelo_303/` directory; the M303 record design is
the corpus xlsx workbook for ejercicio 2024 periods 09 and 3T and
later, whose sheet set (DP30300, DP30301-05, DP303DID) confirms the
segment structure. The deleted `dr303e24.json` DR-spec fixture is
not reinstated; its data is re-derived directly from the corpus xlsx
into the registry TOML, which the `2026-05-03` ADR makes the single
authoring surface.

Two ADR-record corrections are folded in. First, the fichero-BOE
ADR still describes the superseded Python-module authoring path; a
brief amendment to the fichero-BOE export ADR records that export
layouts are authored as registry TOML per the `2026-05-03`
direction. This is an amendment to an existing accepted ADR, not a
new ADR. Second, the Modelo 200 casilla finding in the
branch-reconciliation audit documents that AEAT multi-segment forms
reuse the same casilla number across record segments; the M303
fichero-BOE record layout exhibits the same reuse and the
casilla-disambiguation issues it raises must be re-resolved during
M303 authoring rather than allowed to silently drop fields.

This plan is open-ended where the M303 envelope detail is nebulous.
The eight-segment envelope, its inter-segment offsets, page-record
repetition rules, and the trailer record are only fully knowable
once the corpus xlsx is extracted; discovery in Phase P01 and
authoring in Phase P03 may surface additional Steps, which are
appended via the `vault plan` CLI rather than by hand-editing this
document.

Conformance constraints apply to every Step. The worktree is shared
with concurrent agent campaigns: before the first edit of any
contended file (`130.toml`, `303.toml`, any export-layout TOML, the
fichero-BOE export ADR), the executor runs `git diff -- <path>` and
aborts on non-authored work-in-progress; commits are small and
frequent on the worktree branch with explicit-path staging. New and
amended registry data follows the schema-hardening discipline
(`2026-05-18`): strict, frozen, `extra="forbid"` typed models, the
richest applicable `data_type`, no bare `dict[str, Any]`, no
`cast(...)` escapes, hard validation at snapshot build. Identifiers
follow the Spanish-stem terminology authority (`2026-05-19`):
canonical Spanish stems (`iva`, `irpf`, `modelo`) with English
infrastructure suffixes, `iva` not `vat`. All layout data is
registry-driven; golden round-trip tests derive their expected
bytes from the AEAT Diseno, never from values hand-computed by the
test author, satisfying the no-tautological-tests rule. No live
AEAT write surface is introduced; the serialiser produces a file
for the operator to self-upload.

## Steps

The plan is tier `L2`: Phase blocks each containing contiguous Step
rows. P01 records the ADR correction and front-loads corpus
discovery. P02 delivers the Modelo 130 layout and its golden test.
P03 delivers the larger Modelo 303 eight-segment layout. P04
verifies both modelos end to end.

### Phase `P01` - ADR amendment and corpus discovery

Record the registry-TOML authoring direction in the fichero-BOE export ADR and extract the Modelo 130 and Modelo 303 record specs from the corpus AEAT Diseno de Registros.

- [ ] `P01.S01` - Append an amendment recording that fichero-BOE export layouts are authored as registry TOML per the 2026-05-03 registry-truth direction, an amendment to the existing accepted ADR rather than a new ADR; `.vault/adr/2026-04-22-aeat-fichero-boe-export-adr.md`.
- [ ] `P01.S02` - Study the canonical registry-TOML fichero-BOE export layouts for modelos 180, 202, and 232 as the authoring template, capturing the record / field / encoding / line-ending grammar; `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/export_layouts/`.
- [ ] `P01.S03` - Extract the Modelo 130 single fixed-width record spec - byte offsets, field kinds, encoding, padding - from the corpus AEAT Diseno de Registros xlsx and record it as the authoring reference; `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_130/`.
- [ ] `P01.S04` - Extract the Modelo 303 eight-segment envelope record spec - DP30300 / DP30301-05 / DP303DID / trailer offsets, field kinds, encoding, segment repetition - from the corpus AEAT Diseno de Registros xlsx; `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_303/`.

### Phase `P02` - Modelo 130 export layout

Author and validate the Modelo 130 single fixed-width fichero-BOE export layout against the corpus Diseno and prove it with a golden-SHA round-trip test.

- [ ] `P02.S05` - Audit the existing Modelo 130 export_layouts block against the corpus Diseno for record / field completeness and correct any offset, length, kind, or encoding divergence; `src/aeat/_data/registry/aeat/modelos/130.toml`.
- [ ] `P02.S06` - Author or correct the Modelo 130 page-01 fixed-width casilla fields so every form casilla maps to a record field with grounded offsets and an export_refs binding; `src/aeat/_data/registry/aeat/modelos/130.toml`.
- [ ] `P02.S07` - Add a golden-SHA fichero-BOE fixture for Modelo 130 derived from the corpus Diseno and a serialise-then-deserialise byte-identity round-trip test; `src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`.
- [ ] `P02.S08` - Run the Modelo 130 registry snapshot load and the golden round-trip test, confirming the ~878-byte record serialises byte-accurately; `src/aeat/_data/registry/aeat/modelos/130.toml`.

### Phase `P03` - Modelo 303 export layout

Author the Modelo 303 eight-segment multi-page fichero-BOE export layout, re-resolve the casilla-disambiguation issues, and prove it with a golden-SHA round-trip test.

- [ ] `P03.S09` - Re-derive the Modelo 303 DR-spec data - segment offsets, casilla field map, encoding - from the corpus xlsx workbook into registry-TOML form, not into an intermediate DR-spec JSON fixture; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [ ] `P03.S10` - Re-resolve the documented Modelo 303 segment-scoped casilla-number reuse so each fichero-BOE field disambiguates to a distinct registry casilla with no silently dropped field; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [ ] `P03.S11` - Wire export_refs onto the 37 Modelo 303 casillas so each casilla binds to its fichero-BOE record field; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [ ] `P03.S12` - Author the Modelo 303 DP30300 envelope-header segment record - opening literals, modelo / page / year / period framing, presenter fields - establishing the envelope the page records sit inside; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [ ] `P03.S13` - Author the Modelo 303 DP30301 page-01 segment record - IVA devengado regimen general casilla fields - grounded in the corpus Diseno; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [ ] `P03.S14` - Author the Modelo 303 DP30302 page-02 segment record - IVA deducible casilla fields - grounded in the corpus Diseno; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [ ] `P03.S15` - Author the Modelo 303 DP30303 page-03 segment record - regimen especial and informativo casilla fields - grounded in the corpus Diseno; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [ ] `P03.S16` - Author the Modelo 303 DP30304 page-04 segment record - resultado liquidacion casilla fields - grounded in the corpus Diseno; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [ ] `P03.S17` - Author the Modelo 303 DP30305 page-05 segment record - compensacion and resultado final casilla fields - grounded in the corpus Diseno; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [ ] `P03.S18` - Author the Modelo 303 DP303DID identification segment record - declarant identity and additional-data fields - grounded in the corpus Diseno; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [ ] `P03.S19` - Author the Modelo 303 page-closing trailer segment record completing the eight-segment ~7994-byte envelope; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [ ] `P03.S20` - Add a golden-SHA fichero-BOE fixture for Modelo 303 derived from the corpus Diseno and a serialise-then-deserialise byte-identity round-trip test for the full eight-segment envelope; `src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`.

### Phase `P04` - Verification

Confirm byte-identity round-trips for both modelos, a green 26-modelo registry snapshot, and a byte-accurate export verb.

- [ ] `P04.S21` - Run the serialise-then-deserialise byte-identity round-trip suite for both Modelo 130 and Modelo 303 and confirm both golden-SHA fixtures match; `src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`.
- [ ] `P04.S22` - Load the full registry snapshot and confirm all 26 modelos remain valid with the new and amended Modelo 130 / Modelo 303 export layouts present, no validation regression at snapshot build; `src/aeat/_data/registry/aeat/modelos/`.
- [ ] `P04.S23` - Run the aeat app modelo export verb against a populated Modelo 130 and Modelo 303 draft and confirm each produces a byte-accurate fichero-BOE; `src/aeat/entrypoints/cli/`.

## Parallelization

P01 has a hard ordering ahead of P02 and P03: the corpus record-spec
extraction Steps establish the byte offsets, field kinds, encoding,
and segment structure that the layout-authoring Steps depend on, and
the ADR amendment fixes the authoring direction every later Step
follows. Once P01 is closed, P02 (Modelo 130) and P03 (Modelo 303)
share no registry data and may proceed in parallel by two agents,
subject to the shared-worktree collision check before the first edit
of each modelo file. Within P03 the segment-authoring Steps carry a
soft ordering: the DP30300 header record (P03.S12) establishes the
envelope framing the page records sit inside, so it is authored
first; the DP30301 through DP30305 page records (P03.S13 to P03.S17)
and the DP303DID record (P03.S18) may then be authored concurrently,
with the trailer (P03.S19) and the golden test (P03.S20) last. P04
has a hard ordering after both P02 and P03: it verifies the combined
result and cannot start until both layouts exist.

## Verification

The plan is complete when every Step in every Phase is closed
(`- [x]`) and all of the following verifiable checks pass:

- The Modelo 130 fichero-BOE golden round-trip test passes:
  serialise then deserialise yields byte-identity against a
  golden-SHA fixture derived from the corpus Diseno de Registros.
- The Modelo 303 fichero-BOE golden round-trip test passes:
  serialise then deserialise of the eight-segment roughly
  7994-byte envelope yields byte-identity against a golden-SHA
  fixture derived from the corpus Diseno de Registros.
- The registry snapshot loads green for all 26 modelos with the new
  and amended Modelo 130 and Modelo 303 export layouts present; no
  validation regression at snapshot build.
- The `aeat app modelo export` verb produces a byte-accurate
  fichero-BOE for both Modelo 130 and Modelo 303 from a populated
  draft.
- Every M303 casilla that the fichero-BOE layout references resolves
  to a real registry casilla; segment-scoped casilla-number reuse is
  disambiguated with no silently dropped field.
- `vault plan check` and `vault check all` report the plan and vault
  clean.

For tier-specific verification cadence, see the convention ADR
authorising this plan via the `related:` frontmatter.
