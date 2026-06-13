---
tags:
  - '#plan'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
tier: L2
related:
  - '[[2026-04-22-aeat-fichero-boe-export-adr]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-20-branch-reconciliation-audit]]'
  - '[[2026-06-04-fichero-boe-export-layouts-adr]]'
  - '[[2026-06-04-fichero-boe-export-layouts-research]]'
---


# `fichero-boe-export-layouts` plan

### Phase `P01` - ADR amendment and corpus discovery

Record the registry-TOML authoring direction in the fichero-BOE export ADR and extract the Modelo 130 and Modelo 303 record specs from the corpus AEAT Diseno de Registros.

- [x] `P01.S01` - Append an amendment recording that fichero-BOE export layouts are authored as registry TOML per the 2026-05-03 registry-truth direction, an amendment to the existing accepted ADR rather than a new ADR; `.vault/adr/2026-04-22-aeat-fichero-boe-export-adr.md`.
- [x] `P01.S02` - Study the canonical registry-TOML fichero-BOE export layouts for modelos 180, 202, and 232 as the authoring template, capturing the record / field / encoding / line-ending grammar; `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/export_layouts/`.
- [x] `P01.S03` - Extract the Modelo 130 single fixed-width record spec - byte offsets, field kinds, encoding, padding - from the corpus AEAT Diseno de Registros xlsx and record it as the authoring reference; `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_130/`.
- [x] `P01.S04` - Extract the Modelo 303 eight-segment envelope record spec - DP30300 / DP30301-05 / DP303DID / trailer offsets, field kinds, encoding, segment repetition - from the corpus AEAT Diseno de Registros xlsx; `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_303/`.

### Phase `P02` - Modelo 130 export layout

Author and validate the Modelo 130 single fixed-width fichero-BOE export layout against the corpus Diseno and prove it with a golden-SHA round-trip test.

- [x] `P02.S05` - Audit the existing Modelo 130 export_layouts block against the corpus Diseno for record / field completeness and correct any offset, length, kind, or encoding divergence; `src/aeat/_data/registry/aeat/modelos/130.toml`.
- [x] `P02.S06` - Author or correct the Modelo 130 page-01 fixed-width casilla fields so every form casilla maps to a record field with grounded offsets and an export_refs binding; `src/aeat/_data/registry/aeat/modelos/130.toml`.
- [x] `P02.S07` - Add a golden-SHA fichero-BOE fixture for Modelo 130 derived from the corpus Diseno and a serialise-then-deserialise byte-identity round-trip test; `src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`.
- [x] `P02.S08` - Run the Modelo 130 registry snapshot load and the golden round-trip test, confirming the ~878-byte record serialises byte-accurately; `src/aeat/_data/registry/aeat/modelos/130.toml`.

### Phase `P03` - Modelo 303 export layout

Author the Modelo 303 eight-segment multi-page fichero-BOE export layout, re-resolve the casilla-disambiguation issues, and prove it with a golden-SHA round-trip test.

- [x] `P03.S09` - Re-derive the Modelo 303 DR-spec data - segment offsets, casilla field map, encoding - from the corpus xlsx workbook into registry-TOML form, not into an intermediate DR-spec JSON fixture; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [x] `P03.S10` - Re-resolve the documented Modelo 303 segment-scoped casilla-number reuse so each fichero-BOE field disambiguates to a distinct registry casilla with no silently dropped field; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [x] `P03.S11` - Wire export_refs onto the 37 Modelo 303 casillas so each casilla binds to its fichero-BOE record field; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [x] `P03.S12` - Author the Modelo 303 DP30300 envelope-header segment record - opening literals, modelo / page / year / period framing, presenter fields - establishing the envelope the page records sit inside; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [x] `P03.S13` - Author the Modelo 303 DP30301 page-01 segment record - IVA devengado regimen general casilla fields - grounded in the corpus Diseno; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [x] `P03.S14` - Author the Modelo 303 DP30302 page-02 segment record - IVA deducible casilla fields - grounded in the corpus Diseno; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [x] `P03.S15` - Author the Modelo 303 DP30303 page-03 segment record - regimen especial and informativo casilla fields - grounded in the corpus Diseno; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [x] `P03.S16` - Author the Modelo 303 DP30304 page-04 segment record - resultado liquidacion casilla fields - grounded in the corpus Diseno; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [x] `P03.S17` - Author the Modelo 303 DP30305 page-05 segment record - compensacion and resultado final casilla fields - grounded in the corpus Diseno; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [x] `P03.S18` - Author the Modelo 303 DP303DID identification segment record - declarant identity and additional-data fields - grounded in the corpus Diseno; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [x] `P03.S19` - Author the Modelo 303 page-closing trailer segment record completing the eight-segment ~7994-byte envelope; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [x] `P03.S20` - Add a golden-SHA fichero-BOE fixture for Modelo 303 derived from the corpus Diseno and a serialise-then-deserialise byte-identity round-trip test for the full eight-segment envelope; `src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`.

### Phase `P04` - Verification

Confirm byte-identity round-trips for both modelos, a green 26-modelo registry snapshot, and a byte-accurate export verb.

- [x] `P04.S21` - Run the serialise-then-deserialise byte-identity round-trip suite for both Modelo 130 and Modelo 303 and confirm both golden-SHA fixtures match; `src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`.
- [x] `P04.S22` - Load the full registry snapshot and confirm all 26 modelos remain valid with the new and amended Modelo 130 / Modelo 303 export layouts present, no validation regression at snapshot build; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `P04.S23` - Run the aeat app modelo export verb against a populated Modelo 130 and Modelo 303 draft and confirm each produces a byte-accurate fichero-BOE; `src/aeat/entrypoints/cli/`.

### Phase `P05` - Residual coverage audit and prerequisite identification

Audit the 17 modelos that still lack real export_layouts field specs as of 2026-05-31. For each: determine why it is blocked (PDF-only DR source, incomplete registry casillas, no DR corpus entry, or administrative form not requiring fichero-BOE). Document the prerequisite work required before each can be unblocked. This phase does not implement export layouts; it produces the evidence record that closes issue #563.

- [x] `P05.S24` - Audit the 17 modelos that lack real export_layouts field specs; `categorize each by blocker type (PDF-only DR corpus, incomplete registry casillas, no DR corpus entry, administrative form); document prerequisite work; produce coverage ledger closing issue #563; `src/aeat/_data/registry/aeat/modelos/`.
