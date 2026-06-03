---
tags:
  - '#plan'
  - '#modelo-export-evidence-parity'
date: '2026-06-03'
tier: L3
related:
  - '[[2026-06-03-modelo-export-evidence-parity-adr]]'
  - '[[2026-06-03-modelo-export-workbook-parity-adr]]'
  - '[[2026-06-03-modelo-export-evidence-parity-research]]'
  - '[[2026-06-03-ledger-google-live-export-plan]]'
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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace modelo-export-evidence-parity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'. The related field
     carries the AUTHORISING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add frontmatter fields
     outside the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution-log artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorising documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. See the
     CLI ADR (2026-05-06-plan-hardening-adr) for the full
     subcommand surface. -->

# `modelo-export-evidence-parity` `ledger-evidence-bundled modelo calculation + export parity` plan

## Wave `W01` - Foundational ledger-evidence record + capture

Extend the snapshot layer with a typed LedgerFilingEvidence record (contributor projections + manual fact basis) pegged to the revision's snapshot fingerprint, captured at verify time, persisted in the encrypted revision envelope with strict roundtrip + no-silent-omission guards.

<!-- One-line headline summary plan. -->

### Phase `W01.P01` - Evidence domain record + verify-time capture

Pure domain record + application capture + revision peg + roundtrip.

- [x] `W01.P01.S01` - LedgerFilingEvidence domain record: typed contributor projection (tax facts + legal_refs + attachment/doc-link ids) + manual fact-basis entries, pegged to snapshot_fingerprint; `src/aeat/domain/modelos/_ledger_filing_snapshot.py`.
- [x] `W01.P01.S02` - Verify-time capture: project source_transaction_ids + operator casilla inputs into typed evidence (single catalogue load, alongside fingerprint capture); `src/aeat/application/aggregation/_ledger_filing_snapshot.py`.
- [x] `W01.P01.S03` - Peg evidence onto CalculationRevision and wire capture into verify_modelo_revision; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P01.S04` - Strict encrypted-storage roundtrip + anti-tautology test (every defaultable field non-default; `mutate-then-reload inequality); `src/aeat/domain/modelos/test_ledger_filing_evidence_roundtrip.py`.
- [x] `W01.P01.S05` - Capture guard: bundled evidence contributor set equals the fingerprint snapshot set (no silent omission); `src/aeat/application/aggregation/_ledger_filing_snapshot.py`.

## Wave `W02` - Evidence in the offline export

Add a SheetExportPlan evidence facet + an Evidencia tab in the offline xls + a machine-readable evidence sidecar; refuse exporting a ledger-derived revision that carries neither bundled evidence nor a resolvable reference.

### Phase `W02.P02` - Evidencia surface + export gate

Plan facet, xls Evidencia tab, sidecar, unevidenced-export refusal.

- [x] `W02.P02.S06` - SheetExportPlan evidence facet: per-casilla contributing rows + manual basis as typed plan records; `src/aeat/application/storage/calc_sheets/_records.py`.
- [ ] `W02.P02.S07` - Render an Evidencia tab in the offline xls workbook from the evidence facet; `src/aeat/application/ledger/_workbook_export.py`.
- [ ] `W02.P02.S08` - Emit a machine-readable evidence sidecar alongside the exported artefact; `src/aeat/application/ledger/_workbook_export.py`.
- [ ] `W02.P02.S09` - Refuse exporting a ledger-derived revision that carries neither bundled evidence nor a resolvable reference; `src/aeat/application/modelo/_actions.py`.
- [ ] `W02.P02.S10` - Offline export evidence roundtrip test (export -> read back -> evidence reconstitutes the casilla basis); `src/aeat/entrypoints/cli/test_modelo_export_evidence.py`.

## Wave `W03` - Uniform workbook UX + official-parity gate

Typed presentation facets (number formats by data_type, section-header styling, explicit labelled start/final anchors) rendered identically offline and online, plus a registry-grounded parity gate (casilla set, numbering, segmento, section order, live-formula presence).

### Phase `W03.P03` - Presentation facets

Number formats, section headers, start/final anchors as typed plan facets.

- [ ] `W03.P03.S11` - Number-format plan facet by CasillaDefinition.data_type (money/integer/percentage); `src/aeat/application/storage/calc_sheets/_records.py`.
- [ ] `W03.P03.S12` - Section-header styling facet derived from CasillaDefinition.section; `src/aeat/application/storage/calc_sheets/_engine.py`.
- [ ] `W03.P03.S13` - Explicit labelled start (Entradas opening) and final (resultado/cuota) anchor cells; `src/aeat/application/storage/calc_sheets/_engine.py`.

### Phase `W03.P04` - Official-parity gate

Registry-grounded structural parity + live-formula + offline/online conformance.

- [ ] `W03.P04.S14` - Parity gate: exported casilla set equals completeness-manifest required set (number + segmento) and section order follows registry declaration; `src/aeat/application/storage/calc_sheets/test_modelo_export_parity.py`.
- [ ] `W03.P04.S15` - Assert every computed casilla carries a live spreadsheet formula; `src/aeat/application/storage/calc_sheets/test_modelo_export_parity.py`.
- [ ] `W03.P04.S16` - Offline/online renderer conformance: one plan renders structurally identical xls + Sheets grids; `src/aeat/application/storage/calc_sheets/test_modelo_export_parity.py`.

## Wave `W04` - Per-modelo coverage rollout

Enroll each supported ledger-fed modelo (M303/M390, M130, M100, M200, ...) into evidence-bundling + parity, with an honest per-modelo coverage report (no implied parity beyond what the completeness manifest backs).

### Phase `W04.P05` - Supported-modelo enrolment

Per-modelo evidence + parity coverage with honest reporting.

- [ ] `W04.P05.S17` - Enroll M303 + M390 (IVA) into evidence-bundling + parity; `src/aeat/application/storage/calc_sheets/`.
- [ ] `W04.P05.S18` - Enroll M130 (pagos fraccionados actividad) into evidence-bundling + parity; `src/aeat/application/storage/calc_sheets/`.
- [ ] `W04.P05.S19` - Enroll M100 (renta) into evidence-bundling + parity; `src/aeat/application/storage/calc_sheets/`.
- [ ] `W04.P05.S20` - Enroll M200 (sociedades) into evidence-bundling + parity; `src/aeat/application/storage/calc_sheets/`.
- [ ] `W04.P05.S21` - Honest per-modelo coverage report (parity/evidence status; `no implied parity beyond manifest backing); `src/aeat/application/storage/calc_sheets/`.

## Wave `W05` - Offline/online export parity

The online Sheets export renders formatting + start/final + Evidencia identically to offline; an offline/online evidence-identical assertion locks parity. The live network push itself remains tracked in the ledger-google-live-export follow-up plan.

### Phase `W05.P06` - Sheets parity with offline

Online renders identically; evidence-identical assertion; live push deferred to follow-up.

- [ ] `W05.P06.S22` - Sheets apply renders number formats + start/final + Evidencia identically to the offline xls; `src/aeat/adapters/outbound/google/_calc_sheets_apply.py`.
- [ ] `W05.P06.S23` - Offline/online evidence-identical assertion (same revision -> byte-equal evidence surface); `src/aeat/adapters/outbound/google/`.
- [ ] `W05.P06.S24` - Reference the live network push to the ledger-google-live-export follow-up plan (no live write here); `src/aeat/application/storage/calc_sheets/`.

## Description

<!-- Briefly describe the proposed work. Reference `{adr}`s,
`{research}`, `{reference}`. Supporting documentation must be read prior to
writing the plan document. -->

## Steps

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorising documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

<!-- State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelised when they share no hard
interdependency. -->

## Verification

<!-- State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step in every Wave is closed
(`- [x]`). At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

For tier-specific verification cadence, see the convention ADR
authorising this plan via the `related:` frontmatter. -->
