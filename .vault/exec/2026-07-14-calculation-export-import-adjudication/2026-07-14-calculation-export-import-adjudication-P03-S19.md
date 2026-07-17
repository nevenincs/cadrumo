---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-17'
step_id: 'S19'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---

# Gate Modelo 309 declaration extraction on a sanitized filed specimen and prohibit speculative profile authoring

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/309/`
- `.vault/reference/`

## Description

- Reconcile the Modelo 309 declaration-PDF candidate against the accepted
  live-filing mandate rather than treating the legacy parity checkbox as its
  authority.
- Inspect the canonical Modelo 309 revision, registered source applicability,
  extraction-profile data, shared declaration parser, committed specimens, and
  real Modelo 309 tests.
- Separate exercises 2004 through 2022 from the 2023-and-following
  record-design window.
- Apply the shared disposition precedence and authorize no speculative profile
  or Modelo-specific parser work.

## Outcome

### Modelo 309 declaration PDF, exercises 2004 through 2022

- **Candidate:** Modelo 309 declaration-PDF extraction for the `AD-HOC`
  exercise window `2004-01-01` through `2022-12-31`. The revision metadata uses
  `valid_from = 2003-12-31`, while its `year_from = 2004` period selector and
  `2004-y-siguientes` identity define the first filing exercise as 2004.
- **Mandate:** `proven`; the accepted live filed-declaration data-capture ADR
  requires the full declaration PDF as the fallback evidence path, requires
  that path to use registry extraction profiles, and requires Modelo-specific
  waves to add profile and parser coverage for their declaration PDFs. The
  legacy unchecked “live/static parity fixture” row is corroborating backlog
  history, not the mandate source.
- **Exact official authority:** `missing`; `boe-modelo-309-2003-form` establishes
  the legal form from `2003-12-31`, but the only registered machine-readable
  record design, `aeat-dr-309-2023`, applies from `2023-01-01`. Neither the
  revision label nor the later XLS proves the exact filed declaration-PDF
  representation across exercises 2004 through 2022.
- **Canonical implementation state:** `gap`; `parse_declaracion_bytes` and exact
  registry-profile selection already provide the generic engine, but the
  Modelo 309 revision contains no `extraction_profiles` data and therefore
  cannot satisfy the accepted fallback-path mandate for this window.
- **Real evidence or specimen:** `missing`; repository discovery found the
  official 2023 XLS record design and extracted derivatives but no sanitized
  filed Modelo 309 declaration PDF for exercises 2004 through 2022. The BOE
  form specification is authority evidence, not filed declaration bytes.
- **Retirement:** `false`; no accepted retirement or successor decision was
  found for Modelo 309.
- **Evidence block:** `true`; exact-window filed-artifact authority and a
  sanitized real specimen are unavailable.
- **Four-condition gate:** `mandate_met = true`,
  `exact_authority_met = false`, `canonical_gap_met = true`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `authority-gated`; the missing exact historical authority
  precedes the missing specimen in the shared taxonomy.
- **Next action:** obtain official authority that identifies the exact
  2004-to-2022 declaration-copy formats and obtain sanitized filed specimens
  for the applicable format windows. Until both exist, do not extrapolate from
  the 2023 XLS, author profile data, or add a parser.

### Modelo 309 declaration PDF, 2023-01-01 and following

- **Candidate:** Modelo 309 declaration-PDF extraction for the `AD-HOC`
  exercise window from `2023-01-01` with an open end.
- **Mandate:** `proven`; the accepted live filed-declaration data-capture ADR
  makes the declaration PDF the required fallback evidence path and assigns
  Modelo-specific extraction knowledge to registry profiles interpreted by the
  shared parser.
- **Exact official authority:** `available` for the candidate's applicability
  start and open-ended record-design window: reviewed AEAT source
  `aeat-dr-309-2023` applies from `2023-01-01` and is referenced by the active
  revision. Its `layout_authority` classification narrows the supported window;
  it does not substitute for real declaration bytes or prove PDF geometry.
- **Canonical implementation state:** `gap`; the canonical generic declaration
  parser is delivered and hard-fails when no unique applicable profile exists,
  while Modelo 309 has no extraction profile. The required addition, if the
  evidence gate is later cleared, is reviewed registry profile data and real
  corpus coverage—not another parser path.
- **Real evidence or specimen:** `missing`; no sanitized filed Modelo 309
  declaration PDF is committed. Existing Modelo 309 registry tests exercise
  validation, legal metadata, the ad-hoc selector and schedule, read-only
  references, workbook parity, and bindings; its two-year application fidelity
  tests exercise calculation and persistence. Neither suite parses real Modelo
  309 PDF bytes, and no Modelo 309 declaration-parser corpus test exists.
- **Retirement:** `false`; no accepted retirement or successor decision was
  found for Modelo 309.
- **Evidence block:** `true`; a sanitized filed exercise-2023-or-later Modelo
  309 declaration PDF is unavailable.
- **Four-condition gate:** `mandate_met = true`,
  `exact_authority_met = true`, `canonical_gap_met = true`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `evidence-gated`; mandate, exact-window authority, and the
  canonical required gap are proven, but real filed bytes are unavailable.
- **Next action:** obtain and sanitize a real filed exercise-2023-or-later PDF,
  confirm its precise format window, and only then author reviewed profile data
  plus real corpus coverage through the existing generic parser. Do not derive
  PDF coordinates from the XLS and do not add Modelo-specific parser code.

## Notes

- Intent-first Vaultspec RAG located the generic parser and profile-selection
  boundary, the accepted live-filing mandate, and the later architecture ADR
  that ratifies registry-driven extraction. The latter ADR's committed Modelo
  list does not name Modelo 309, but the earlier accepted live-filing ADR's
  per-Modelo fallback requirement does.
- Direct source inspection confirmed the `2004-y-siguientes` revision's
  exercise selector begins in 2004, source `aeat-dr-309-2023` begins on
  `2023-01-01`, and the Modelo 309 registry tree has no
  `extraction_profiles` directory.
- Repository specimen and parser-test searches found no sanitized filed Modelo
  309 PDF and no Modelo 309 declaration-parser test. The committed
  `test_modelo_309_registry.py` and `test_modelo_309_adhoc_fidelity.py` suites
  are real Modelo 309 behavioral coverage, but they do not evidence PDF
  extraction.
- This Step writes only the adjudication record. It changes no production
  source, tests, registry data, shared Reference or audit, plan state, staging,
  or commits, and it leaves unrelated inherited worktree changes untouched.
