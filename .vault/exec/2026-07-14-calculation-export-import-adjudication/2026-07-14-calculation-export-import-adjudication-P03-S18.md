---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S18'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---

# Gate Modelo 308 declaration extraction on a sanitized filed specimen and prohibit speculative profile authoring

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/308/`
- `.vault/reference/`

## Description

- Reconcile the Modelo 308 declaration-PDF candidate against the accepted live
  filed-declaration mandate instead of treating an unchecked legacy fixture row
  as its authority.
- Inspect the canonical Modelo 308 revision, registered source applicability,
  extraction-profile data, generic declaration parser, and committed test and
  specimen surfaces.
- Separate the unsupported 2009-to-2018 window from the registered
  2019-and-following record-design window.
- Apply the shared disposition precedence before considering later authority
  and evidence gates; authorize no profile or parser implementation.

## Outcome

### Modelo 308 declaration PDF, 2009-01-01 through 2018-12-31

- **Candidate:** Modelo 308 declaration-PDF extraction for the `AD-HOC`
  revision window from `2009-01-01` through `2018-12-31`.
- **Mandate:** `proven`; the accepted live filed-declaration data-capture ADR
  requires the full declaration PDF as the fallback evidence path, requires
  that path to use registry extraction profiles, and requires Modelo-specific
  waves to add profile and parser coverage for their declaration PDFs. The
  legacy unchecked “Modelo 308 live/read fixture evidence” row is corroborating
  backlog history, not the mandate source.
- **Exact official authority:** `missing`; the registry revision
  `2009-y-siguientes` starts on `2009-01-01`, but the only registered
  record-design authority, `aeat-dr-308-2019`, applies from `2019-01-01`.
  Neither that later XLS nor the revision label establishes declaration-PDF
  geometry for 2009 through 2018.
- **Canonical implementation state:** `gap`; the shared
  `parse_declaracion_bytes` path and exact profile selection already provide the
  generic engine, but the Modelo 308 revision contains no
  `extraction_profiles` data and therefore cannot satisfy the accepted fallback
  path mandate for this window.
- **Real evidence or specimen:** `missing`; repository discovery found the
  official 2019 XLS record design and its extracted derivatives, but no
  sanitized filed Modelo 308 declaration PDF for this window. A record design
  is not filed declaration bytes.
- **Retirement:** `false`; no accepted retirement or successor decision was
  found for Modelo 308.
- **Evidence block:** `true`; exact-window authority and sanitized filed bytes
  are unavailable.
- **Four-condition gate:** `mandate_met = true`,
  `exact_authority_met = false`, `canonical_gap_met = true`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `authority-gated`; the missing exact historical authority
  precedes the missing specimen in the shared taxonomy.
- **Next action:** obtain official authority that identifies the exact
  2009-to-2018 declaration-copy formats and obtain sanitized filed specimens
  for the applicable format windows. Until both exist, do not extrapolate from
  the 2019 XLS, author profile data, or add a parser.

### Modelo 308 declaration PDF, 2019-01-01 and following

- **Candidate:** Modelo 308 declaration-PDF extraction for the `AD-HOC`
  revision window from `2019-01-01` with an open end.
- **Mandate:** `proven`; the accepted live filed-declaration data-capture ADR
  makes the declaration PDF the required fallback evidence path and assigns
  Modelo-specific extraction knowledge to registry profiles interpreted by the
  shared parser. The legacy evidence row is not the mandate source.
- **Exact official authority:** `available` for the candidate's applicability
  start and open-ended record-design window: the reviewed AEAT source
  `aeat-dr-308-2019` applies from `2019-01-01` and is referenced by the active
  `2009-y-siguientes` revision. Its `layout_authority` classification does not
  prove PDF geometry and cannot substitute for a filed specimen.
- **Canonical implementation state:** `gap`; the canonical generic declaration
  parser is delivered, while Modelo 308 has no extraction profile. The accepted
  fallback-path mandate makes this a canonical required gap, but no second or
  Modelo-specific parser is warranted.
- **Real evidence or specimen:** `missing`; no sanitized filed Modelo 308
  declaration PDF is committed. The existing Modelo 308 registry and
  application fidelity tests exercise revision, legal, schedule, link, and
  calculation facts, not extraction of real Modelo 308 PDF bytes. Generic
  parser and schema tests prove the shared engine and profile contract only;
  they do not prove this Modelo and window.
- **Retirement:** `false`; no accepted retirement or successor decision was
  found for Modelo 308.
- **Evidence block:** `true`; a sanitized filed Modelo 308 declaration PDF is
  unavailable.
- **Four-condition gate:** `mandate_met = true`,
  `exact_authority_met = true`, `canonical_gap_met = true`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `evidence-gated`; mandate, exact-window authority, and the
  canonical required gap are proven, but real filed bytes are unavailable.
- **Next action:** obtain and sanitize a real filed 2019-or-later PDF, confirm
  its precise format window, and only then author reviewed profile data plus
  real corpus coverage through the existing generic parser. Do not derive PDF
  coordinates from the XLS and do not add Modelo-specific parser code.

## Notes

- The HIGH review reopened this Step after identifying that its original
  mandate analysis omitted the accepted 2026-05-04 live filed-declaration
  data-capture ADR. This correction records that ADR as the mandate source and
  re-applies disposition precedence; the legacy unchecked fixture row remains
  non-authoritative.
- Intent-first Vaultspec RAG searches for Modelo 308 extraction mandate,
  profile, source, and specimen evidence found the generic parser and schema
  contract, the accepted live-filing mandate, the adjudication corpus, and the
  legacy unchecked fixture row.
- Direct source inspection confirmed revision `2009-y-siguientes` starts on
  `2009-01-01`, source `aeat-dr-308-2019` starts on `2019-01-01`, and the
  Modelo 308 registry tree contains no `extraction_profiles` directory.
- Repository specimen discovery found no sanitized filed Modelo 308 PDF.
  `test_modelo_308_registry.py` and `test_modelo_308_adhoc_fidelity.py` are real
  Modelo 308 coverage, but neither is a declaration-PDF parser corpus test.
- This Step writes only the adjudication record. It changes no production
  source, tests, registry data, shared Reference or audit, plan state, staging,
  or commits, and it leaves unrelated inherited worktree changes untouched.
