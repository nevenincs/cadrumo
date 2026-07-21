---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-17'
step_id: 'S20'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---

# Gate Modelo 322 declaration extraction on a sanitized filed specimen and prohibit speculative profile authoring

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/322/`
- `.vault/reference/`

## Description

- Reconcile the Modelo 322 declaration-PDF candidate against the accepted live
  filed-declaration fallback mandate rather than the legacy fixture checkbox.
- Inspect the canonical Modelo 322 revision, exact registered source windows,
  extraction-profile data, shared declaration parser, committed specimens, and
  real Modelo 322 tests.
- Separate exercises 2008 through 2025 from the 2026-and-following
  record-design window.
- Apply the shared disposition precedence and authorize no speculative profile
  or Modelo-specific parser work.

## Outcome

### Modelo 322 declaration PDF, exercises 2008 through 2025

- **Candidate:** Modelo 322 declaration-PDF extraction for the monthly revision
  window from `2008-01-01` through `2025-12-31`, covering periods `01` through
  `12`.
- **Mandate:** `proven`; the accepted live filed-declaration data-capture ADR
  requires the full declaration PDF as the fallback evidence path, requires
  that path to use registry extraction profiles, and requires Modelo-specific
  waves to add profile and parser coverage for their declaration PDFs. The
  legacy unchecked “Modelo 322 live/read fixture evidence” row is corroborating
  backlog history, not the mandate source.
- **Exact official authority:** `missing`; `boe-modelo-322-2007-form`
  establishes the legal form from `2007-11-30`, but the only registered
  machine-readable record design, `aeat-dr-322-2026`, applies from
  `2026-01-01`. Neither the revision label, the BOE form specification, nor the
  later XLSX proves the exact filed declaration-copy representation across
  exercises 2008 through 2025.
- **Canonical implementation state:** `gap`; `parse_declaracion_bytes` and exact
  registry-profile selection already provide the generic engine, but the
  Modelo 322 revision contains no `extraction_profiles` data and therefore
  cannot satisfy the accepted fallback-path mandate for this window.
- **Real evidence or specimen:** `missing`; repository discovery found the
  official 2026 XLSX and 2024 calculation manual-oracle JSON, but no sanitized
  filed Modelo 322 declaration PDF for exercises 2008 through 2025. A record
  design, BOE form specification, or calculation oracle is not filed
  declaration bytes.
- **Retirement:** `false`; no accepted retirement or successor decision was
  found for Modelo 322.
- **Evidence block:** `true`; exact-window declaration-copy authority and a
  sanitized real specimen are unavailable.
- **Four-condition gate:** `mandate_met = true`,
  `exact_authority_met = false`, `canonical_gap_met = true`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `authority-gated`; the missing exact historical authority
  precedes the missing specimen in the shared taxonomy.
- **Next action:** obtain official authority that identifies the exact
  2008-to-2025 declaration-copy formats and obtain sanitized filed specimens
  for the applicable format windows. Until both exist, do not extrapolate from
  the 2026 XLSX, author profile data, or add a parser.

### Modelo 322 declaration PDF, 2026-01-01 and following

- **Candidate:** Modelo 322 declaration-PDF extraction for the monthly revision
  window from `2026-01-01` with an open end, covering periods `01` through
  `12`.
- **Mandate:** `proven`; the accepted live filed-declaration data-capture ADR
  makes the declaration PDF the required fallback evidence path and assigns
  Modelo-specific extraction knowledge to registry profiles interpreted by the
  shared parser.
- **Exact official authority:** `available` for the candidate's applicability
  start and open-ended record-design window: reviewed AEAT source
  `aeat-dr-322-2026` applies from `2026-01-01` and is referenced by the active
  `2008-y-siguientes` revision. Its `layout_authority` classification narrows
  the supported window; it does not substitute for real declaration bytes or
  prove PDF geometry.
- **Canonical implementation state:** `gap`; the canonical generic declaration
  parser is delivered and hard-fails when no unique applicable profile exists,
  while Modelo 322 has no extraction profile. The required addition, if the
  evidence gate is later cleared, is reviewed registry profile data and real
  corpus coverage—not another parser path.
- **Real evidence or specimen:** `missing`; no sanitized filed Modelo 322
  declaration PDF is committed. Existing registry tests exercise validation,
  legal metadata, the monthly selector and deadlines, read-only references,
  workbook parity, and IVA bindings. The application continuity and 2024
  manual-worked-example suites exercise calculation behavior, not extraction
  from real Modelo 322 PDF bytes; no Modelo 322 declaration-parser corpus test
  exists.
- **Retirement:** `false`; no accepted retirement or successor decision was
  found for Modelo 322.
- **Evidence block:** `true`; a sanitized filed exercise-2026-or-later Modelo
  322 declaration PDF is unavailable.
- **Four-condition gate:** `mandate_met = true`,
  `exact_authority_met = true`, `canonical_gap_met = true`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `evidence-gated`; mandate, exact-window authority, and the
  canonical required gap are proven, but real filed bytes are unavailable.
- **Next action:** obtain and sanitize a real filed exercise-2026-or-later PDF,
  confirm its precise format window, and only then author reviewed profile data
  plus real corpus coverage through the existing generic parser. Do not derive
  PDF coordinates from the XLSX and do not add Modelo-specific parser code.

## Notes

- Intent-first Vaultspec RAG located the shared parser and exact profile
  selection boundary and the accepted 2026-05-04 live filed-declaration
  data-capture ADR that supplies the fallback mandate.
- Direct source inspection confirmed the `2008-y-siguientes` revision begins on
  `2008-01-01`, source `aeat-dr-322-2026` begins on `2026-01-01`, and the
  Modelo 322 registry tree has no `extraction_profiles` directory.
- Repository specimen and parser-test searches found no sanitized filed Modelo
  322 PDF and no Modelo 322 declaration-parser test. The committed
  `test_modelo_322_registry.py`,
  `test_modelo_322_grupo_individual_continuity.py`, and
  `test_m322_2024_grupo_entidades_manual_worked_example.py` suites are real
  Modelo 322 behavioral coverage, but they do not evidence PDF extraction.
- This Step writes only the adjudication record. It changes no production
  source, tests, registry data, shared Reference or audit, plan state, staging,
  or commits, and it leaves unrelated inherited worktree changes untouched.
