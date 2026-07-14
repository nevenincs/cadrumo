---
tags:
  - '#audit'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
  - "[[2026-07-14-calculation-export-import-adjudication-adr]]"
---
# `calculation-export-import-adjudication` audit: `Export and import candidate adjudication`

## Scope

This rolling audit records the candidate adjudications authorized by the
accepted backlog-admission decision. It covers the bounded outbound export,
submitted-file, declaration-PDF, and time-gated candidates named by the plan.
It does not treat source availability, unchecked legacy wording, or absent
optional registry data as product scope.

Candidate findings must inspect the canonical registry authority, generic
renderer or parser, and real-behavior evidence before they propose work. The
audit does not authorize production source, tests, or registry changes.

## Findings

### shared-adjudication-contract | low | Candidate findings use one evidence record and one disposition taxonomy

Each candidate finding records these fields separately: candidate surface and
window; mandate and its source; exact official authority window; canonical
implementation state; real evidence or specimen state; retirement status;
evidence block; four gate booleans and result; disposition; and next action.

The four booleans are `mandate_met`, `exact_authority_met`,
`canonical_gap_met`, and `eligible_met`. The result is `pass` only when every
boolean is true. `eligible_met` is true only when the candidate is neither
retired nor blocked on unavailable real evidence. Missing proof is false.

Select exactly one disposition in this order: `retired`, `not-mandated`,
`mandate-gated`, `delivered-equivalent`, `authority-gated`, `evidence-gated`,
or `implementation-admitted`. If no selection rule applies, the candidate
record is incomplete. Only `implementation-admitted` permits a successor
implementation plan, and that plan remains limited to reviewed registry data
and real-behavior coverage through the canonical engines.

### modelo-036-outbound-2025 | low | Definitive v43 authority does not establish an outbound product mandate

- **Candidate:** Modelo 036 outbound machine-file generation for revision
  `2025-02-03-y-siguientes`, events `alta`, `modificacion`, and `baja`, from
  `2025-02-03` with an open end.
- **Mandate:** `unproven`; legacy routing wording and a filing application link
  are not an accepted decision or explicit current product goal.
- **Exact authority window:** `aeat-dr-036-2025` registers definitive
  `DR036v43.xlsx` from `2025-02-03` with an open end. Provisional
  `DR036v42.xlsx` is not authority for the active revision.
- **Canonical implementation state:** `gap` for the candidate behavior because
  no Modelo 036 export layout exists; the generic renderer/parser is delivered
  and fails closed, so no new engine is missing.
- **Real evidence or specimen:** the official record design is available; a
  real golden outbound payload and mutation-sensitive round trip are missing.
- **Retirement:** `false`.
- **Evidence block:** `true`; real golden outbound evidence is unavailable.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = true`, `canonical_gap_met = false`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** obtain an accepted product decision for this exact window;
  until then, create no layout, renderer, parser, test, or successor step.

### modelo-037-declaration-extraction | low | Active extraction is retired in favour of Modelo 036

- **Candidate:** Modelo 037 declaration-PDF extraction for current support from
  `2025-02-03` with an open end.
- **Mandate:** `absent`; accepted authority requires historical inactive
  metadata and makes Modelo 036 the active successor.
- **Exact authority window:** `BOE-A-2025-410` and the reviewed suppression
  source apply from `2025-02-03`; they authorize suppression, not active 037
  extraction.
- **Canonical implementation state:** `delivered`; 037 is outside the registry,
  rejects active work units, has no snapshot/profile, and names 036 as
  successor while the generic parser remains registry-driven.
- **Real evidence or specimen:** `not-required` for a retired active surface;
  the reviewed suppression authority is available.
- **Retirement:** `true`.
- **Evidence block:** `false`; retirement independently closes the candidate.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = true`, `canonical_gap_met = false`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `retired`.
- **Next action:** `none`; preserve Modelo 036 and add no 037 profile, parser,
  shim, or active entry point.

### modelo-037-outbound | low | Current outbound support is retired in favour of Modelo 036

- **Candidate:** Modelo 037 outbound generation for current support from
  `2025-02-03` with an open end.
- **Mandate:** `absent`; accepted authority mandates suppression and names
  Modelo 036 as successor.
- **Exact authority window:** `BOE-A-2025-410` applies from `2025-02-03`; it is
  retirement authority, not an active export design.
- **Canonical implementation state:** `delivered`; 037 is historical metadata,
  has no active registry snapshot/layout, and the generic exporter fails closed.
- **Real evidence or specimen:** `not-required`; the zero-artefact inventory is
  negative evidence and must not revive support.
- **Retirement:** `true`.
- **Evidence block:** `false`.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = true`, `canonical_gap_met = false`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `retired`.
- **Next action:** `none`; add no 037 registry, layout, renderer, parser, shim,
  test, active entry point, or successor work.

### modelo-200-submitted-file-2025 | low | Generic submitted-file parsing is delivered for the evidenced 2025 window

- **Candidate:** Modelo 200 submitted-file parsing, annual period `0A`, exercise
  2025.
- **Mandate:** `proven`; accepted live filing-data capture prefers submitted
  files when AEAT exposes them.
- **Exact authority window:** `aeat-dr-200-2025` and
  `modelo-200-fichero-boe` cover exercise 2025 only; the enclosing revision's
  2024 start does not extend that authority backwards.
- **Canonical implementation state:** `delivered`; the generic live route uses
  `resolve_export_layout` and `parse_export_payload` and emits observations.
- **Real evidence or specimen:** the reviewed, hash-pinned design, registry
  layout, layout-resolution tests, generic round trips, and observation test are
  available; no separate filed specimen or 2024 parity is claimed.
- **Retirement:** `false`.
- **Evidence block:** `false`.
- **Four-condition gate:** `mandate_met = true`,
  `exact_authority_met = true`, `canonical_gap_met = false`, and
  `eligible_met = true`.
- **Gate result:** `fail` because no canonical gap exists.
- **Disposition:** `delivered-equivalent`.
- **Next action:** `none`; preserve the generic path and limit the claim to 2025.

### modelo-200-declaration-pdf-2025 | low | Declaration extraction awaits a real sanitized filed specimen

- **Candidate:** Modelo 200 declaration-PDF extraction, annual period `0A`,
  exercise 2025.
- **Mandate:** `proven`; accepted live filing-data capture uses declaration PDF
  as the fallback observation format.
- **Exact authority window:** reviewed 2025 record-design and form authority
  establish the exercise window but do not prove filed-PDF geometry.
- **Canonical implementation state:** `gap`; the generic declaration parser
  exists, but Modelo 200 has no registry-owned extraction profile.
- **Real evidence or specimen:** `missing`; neither the record design, 2024
  manual, nor a synthetic Modelo 130 fixture is a filed Modelo 200 PDF.
- **Retirement:** `false`.
- **Evidence block:** `true`; a sanitized filed 2025 specimen is unavailable.
- **Four-condition gate:** `mandate_met = true`,
  `exact_authority_met = true`, `canonical_gap_met = true`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `evidence-gated`.
- **Next action:** obtain and sanitize a real filed exercise-2025 PDF before
  proposing profile data and real corpus coverage through the generic parser.

### modelo-184-outbound-2025-open | low | Exact 2025 authority remains mandate-gated

- **Candidate:** Modelo 184 outbound generation from `2025-01-01`, open end.
- **Mandate:** `unproven`; conditional legacy wording is not current scope.
- **Exact authority window:** `aeat-dr-184-2025` covers 2025+.
- **Canonical implementation state:** `gap` for the optional behavior; no layout
  exists, while the generic engine is delivered and fails closed.
- **Real evidence or specimen:** official design available; golden payload and
  real round trip missing.
- **Retirement:** `false`.
- **Evidence block:** `true`.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = true`, `canonical_gap_met = false`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** obtain an accepted 2025+ outbound product mandate before any
  registry or implementation proposal.

### modelo-184-outbound-2015-2024 | low | Later authority cannot be projected backwards

- **Candidate:** Modelo 184 outbound generation from 2015 through 2024.
- **Mandate:** `unproven`.
- **Exact authority window:** `missing`; the 2025 design does not cover this
  earlier revision window.
- **Canonical implementation state:** `gap` for the optional behavior; the
  generic engine remains the only permitted path.
- **Real evidence or specimen:** no exact-window design or golden payload.
- **Retirement:** `false`.
- **Evidence block:** `true`.
- **Four-condition gate:** `mandate_met = false`,
  `exact_authority_met = false`, `canonical_gap_met = false`, and
  `eligible_met = false`.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** establish both a current mandate and exact earlier-window
  authority; do not back-project the 2025 design.

## Recommendations

- Append one candidate finding per surface and exact applicability window.
- Preserve separate findings for declaration PDFs, submitted files, regime
  variants, and non-overlapping authority windows.
- Reject duplicate renderers, parsers, registry authorities, schema stores, and
  archive formats regardless of candidate disposition.
- Leave candidate outcomes unrecorded until their individual plan Steps inspect
  the required mandate, authority, implementation, and real evidence.
