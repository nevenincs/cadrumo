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

## Recommendations

- Append one candidate finding per surface and exact applicability window.
- Preserve separate findings for declaration PDFs, submitted files, regime
  variants, and non-overlapping authority windows.
- Reject duplicate renderers, parsers, registry authorities, schema stores, and
  archive formats regardless of candidate disposition.
- Leave candidate outcomes unrecorded until their individual plan Steps inspect
  the required mandate, authority, implementation, and real evidence.
