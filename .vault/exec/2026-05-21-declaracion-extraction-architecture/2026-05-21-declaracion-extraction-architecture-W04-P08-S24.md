---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: S24
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W04.P08.S24 - Named-field modelo corpus and registry presence sweep

## Discovery Results

### M036
- Registry: `src/aeat/_data/registry/aeat/modelos/036.toml`
  - Revision: `2025-02-03-y-siguientes`
  - Casillas: `decl.event-kind` (text, tipo-declaracion), `decl.vigencia-2025` (text, vigencia)
  - No `extraction_profiles` stanza present — needs authoring
- Corpus: Diseño xlsx files (4 versions), instructions HTML
- **Feasibility: FEASIBLE** — label patterns derived from registry casilla labels;
  **PROVISIONAL**: the corpus contains only a diseño de registro (EDI record-layout
  spec), NOT a real printed-declaración-form PDF. The label patterns are unverified
  guesses until a W05 round-trip parse test runs against a real M036 PDF specimen.

### M037
- Registry: no entry (no `037*` file in modelos/)
- Corpus: manifest.json confirms zero artefacts (`artefact_count: 0`,
  `not_found_note` present), no instructions directory
- **Feasibility: SOURCE-BLOCKED** — defer; no form specimen available

### M369
- Registry: `src/aeat/_data/registry/aeat/modelos/369/revisions/esquema-union/revision.toml`
  - Casillas: `decl.ejercicio` (year), `decl.periodo` (period_code), and IVA money casillas
  - No `extraction_profiles` stanza in construct — needs authoring
- Corpus: Diseño xlsx + procedure HTML in instructions
- **Feasibility: FEASIBLE** — `decl.ejercicio` and `decl.periodo` can be targeted
  with `named_label`; IVA casillas have numeric slugs that are not printed literally
  on the declaration summary page so numeric matching would also not work —
  `named_label` on the header fields is the right scope.
  **PROVISIONAL**: the corpus contains only a diseño de registro (HAC/610/2021 xlsx),
  NOT a real printed-declaración-form PDF. Patterns are unverified guesses until a
  W05 round-trip parse test runs against a real M369 PDF specimen.

### M720
- Registry: `src/aeat/_data/registry/aeat/modelos/720.toml`
  - Profile `modelo-720-declaracion-pdf` ALREADY EXISTS and is functional
- **STATUS: COMPLETE** — no action needed

### M840
- Registry: `src/aeat/_data/registry/aeat/modelos/840.toml`
  - No `extraction_profiles` stanza — W02 review-fix removed it
  - Casillas: `decl.tipo-declaracion` (text), `decl.ejercicio` (year)
- Corpus: Diseño PDF (Orden HAC/2572/2003)
- **Feasibility: FEASIBLE** — label patterns derived from casilla labels in registry;
  **PROVISIONAL**: the corpus contains only a diseño de registro PDF (Orden
  HAC/2572/2003), NOT a real printed-declaración-form PDF. Patterns are unverified
  guesses until a W05 round-trip parse test runs against a real M840 PDF specimen.

## Additional discoveries

No schema-tweak Steps were surfaced. The `ExtractionTargetDefinition` schema
(W02 primitive) covers all needed cases.

## Action

No code changes. This Step is a discovery record only.
