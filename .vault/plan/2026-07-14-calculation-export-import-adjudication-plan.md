---
tags:
  - '#plan'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
tier: L2
related:
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-07-14-calculation-export-import-adjudication-reference]]'
  - '[[2026-07-12-calculation-truth-registry-plan]]'
  - '[[2026-07-14-calculation-export-import-adjudication-adr]]'
  - '[[2026-07-14-calculation-export-import-adjudication-research]]'
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

# `calculation-export-import-adjudication` plan

## Outcome and boundary

Produce one evidence-backed disposition for every bounded export-layout and
extraction-profile candidate without turning legacy wording or source
availability into product scope. The companion
`2026-07-14-calculation-export-import-adjudication-reference` owns definitions,
implementation anchors, authority windows, and the candidate registers.

This is a reconciliation plan. It does not authorize production code. The
accepted central calculation-registry ADR already decides the architecture:
reviewed registry data feeds the existing generic renderer and parsers. No new
ADR is needed unless adjudication discovers a genuinely new design choice.

## Prerequisites and start checks

- Read the accepted calculation-registry ADR, the companion Reference, and the
  reopened calculation-truth continuation before executing a Step.
- Re-run intent-first `vaultspec-rag` discovery and exact source lookup at the
  start of each Phase so concurrent implementation cannot be mistaken for a
  gap.
- Verify the official bundled artefact's applicability window before using it
  as layout or extraction evidence.
- Preserve the existing export renderer/parser, declaration-PDF parser,
  registry authority, and sealed-archive service as single canonical paths.

## Decision gate

A candidate may reach a successor implementation plan only when all four
conditions are proven:

1. A current product or filing mandate requires the capability.
2. Official authority exists for the exact revision and filing window.
3. The capability is absent from the canonical current implementation.
4. The candidate is neither retired nor blocked on unavailable real evidence.

An unchecked legacy row, an extractor application link, or a bundled record
design is not sufficient by itself. Retired, delivered-equivalent,
not-mandated, and evidence-gated candidates end in the adjudication record and
must not become implementation work.

### Phase `P01` - Decision boundary

Freeze the mandate, authority, current-implementation, evidence, and non-duplication gate before any candidate can become implementation work.

- [x] `P01.S01` - Reconfirm the canonical registry, export renderer/parser, declaration parser, and sealed-archive boundaries against current source and tests; `src/cadrumo/, .vault/reference/`.
- [x] `P01.S02` - Publish the shared disposition taxonomy, evidence-field contract, and four-condition gate for the individual candidate Steps; `.vault/reference/, .vault/audit/`.

### Phase `P02` - Outbound export-layout candidates

Adjudicate each legacy outbound candidate against product mandate and source applicability without creating a second renderer.

- [x] `P02.S03` - Adjudicate Modelo 036 outbound machine-file generation against the definitive current design and retire provisional-layout inferences; `src/cadrumo/_data/registry/aeat/modelos/036/, .vault/reference/`.
- [x] `P02.S04` - Record Modelo 037 outbound support as retired and prohibit new registry or export work; `src/cadrumo/_data/registry/aeat/, .vault/reference/`.
- [ ] `P02.S05` - Adjudicate Modelo 184 export only for the 2025-and-following authority window and gate earlier revisions; `src/cadrumo/_data/registry/aeat/modelos/184/, .vault/reference/`.
- [ ] `P02.S06` - Reconcile Modelo 190 2024 and 2025 design windows before deciding any outbound mandate; `src/cadrumo/_data/registry/aeat/modelos/190/, .vault/reference/`.
- [ ] `P02.S07` - Reconcile Modelo 193 2024 and 2025 design windows before deciding any outbound mandate; `src/cadrumo/_data/registry/aeat/modelos/193/, .vault/reference/`.
- [ ] `P02.S08` - Adjudicate Modelo 308 export only for the 2019-and-following authority window and gate earlier revisions; `src/cadrumo/_data/registry/aeat/modelos/308/, .vault/reference/`.
- [ ] `P02.S09` - Record that Modelo 309 has no legacy outbound mandate and prevent source availability from manufacturing one; `src/cadrumo/_data/registry/aeat/modelos/309/, .vault/reference/`.
- [ ] `P02.S10` - Adjudicate Modelo 322 export only for the 2026-and-following authority window and gate earlier revisions; `src/cadrumo/_data/registry/aeat/modelos/322/, .vault/reference/`.
- [ ] `P02.S11` - Adjudicate Modelo 347 export by registered authority window and gate uncatalogued 2008-to-2010 layouts; `src/cadrumo/_data/registry/aeat/modelos/347/, .vault/reference/`.
- [ ] `P02.S12` - Adjudicate Modelo 353 export only for the 2026-and-following authority window and gate earlier revisions; `src/cadrumo/_data/registry/aeat/modelos/353/, .vault/reference/`.
- [ ] `P02.S13` - Record that Modelo 360 has no legacy outbound mandate and preserve its layout authority as evidence only; `src/cadrumo/_data/registry/aeat/modelos/360/, .vault/reference/`.
- [ ] `P02.S14` - Adjudicate Modelo 369 export while preserving Union, Importacion, and Exterior revision separation; `src/cadrumo/_data/registry/aeat/modelos/369/, .vault/reference/`.
- [ ] `P02.S15` - Adjudicate Modelo 840 registry field and binding work only if machine-file generation is a confirmed product mandate; `src/cadrumo/_data/registry/aeat/modelos/840/, .vault/reference/`.

### Phase `P03` - Inbound extraction-profile candidates

Adjudicate each inbound candidate against real filed-artifact evidence and the existing generic parser boundary.

- [x] `P03.S16` - Record Modelo 037 extraction as retired and preserve the active Modelo 036 successor boundary; `src/cadrumo/_data/registry/aeat/, .vault/reference/`.
- [ ] `P03.S17` - Confirm Modelo 200 submitted-file parsing as delivered through the generic export parser and gate declaration-PDF work on a real specimen; `src/cadrumo/_data/registry/aeat/modelos/200/, src/cadrumo/adapters/inbound/declaracion/, .vault/reference/`.
- [ ] `P03.S18` - Gate Modelo 308 declaration extraction on a sanitized filed specimen and prohibit speculative profile authoring; `src/cadrumo/_data/registry/aeat/modelos/308/, .vault/reference/`.
- [ ] `P03.S19` - Gate Modelo 309 declaration extraction on a sanitized filed specimen and prohibit speculative profile authoring; `src/cadrumo/_data/registry/aeat/modelos/309/, .vault/reference/`.
- [ ] `P03.S20` - Gate Modelo 322 declaration extraction on a sanitized filed specimen and prohibit speculative profile authoring; `src/cadrumo/_data/registry/aeat/modelos/322/, .vault/reference/`.
- [ ] `P03.S21` - Gate Modelo 353 declaration extraction on a sanitized filed specimen and prohibit speculative profile authoring; `src/cadrumo/_data/registry/aeat/modelos/353/, .vault/reference/`.
- [ ] `P03.S22` - Gate Modelo 360 declaration extraction on a sanitized filed specimen and prohibit speculative profile authoring; `src/cadrumo/_data/registry/aeat/modelos/360/, .vault/reference/`.

### Phase `P04` - Time gates and successor handoff

Record unavailable-authority gates, publish the final residual audit, and authorize successor planning only for confirmed current gaps.

- [ ] `P04.S23` - Record Modelo 100 exercise-2026 export authority as unavailable until an official current-year design is published and bundled; `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/, .vault/reference/`.
- [ ] `P04.S24` - Publish the final adjudication audit with dispositions, evidence windows, duplicate-code guards, and unresolved external gates; `.vault/audit/, .vault/reference/`.
- [ ] `P04.S25` - Determine whether any candidate passes all four gates and either record no successor handoff or write a successor implementation plan limited to proven gaps; `.vault/audit/, .vault/plan/`.

## Parallelization

`P01` is a hard prerequisite. After both `P01` Steps are reviewed and
committed, `P02` and `P03` may run in parallel because they adjudicate separate
outbound and inbound surfaces. Steps within each Phase may also run in parallel
when agents own disjoint Modelo directories and write through a single
coordinating editor for the shared Reference and audit. `P04` begins only after
both candidate phases finish. `P04.S25` follows the final audit, records no
handoff when zero candidates pass, and writes a successor plan only when at
least one candidate passes every decision-gate condition.

## Verification

- `vaultspec-core vault plan check` reports a valid L2 plan with four Phases and
  25 Steps, and every completed Step has a reviewed Step Record.
- The companion Reference and final audit contain exactly one disposition for
  every listed candidate, with mandate, authority window, current implementation,
  evidence, and next action recorded separately.
- The adjudication commits change no production source, tests, or registry data.
- No disposition proposes a per-Modelo renderer, per-Modelo parser, second
  registry, second archive format, or provider-specific recovery path.
- Every evidence-gated candidate remains closed to implementation until the
  named official source or sanitized real specimen is available.
- Any successor plan contains only candidates that pass all four decision-gate
  conditions and receives independent technical and editorial review before
  execution approval is requested.
