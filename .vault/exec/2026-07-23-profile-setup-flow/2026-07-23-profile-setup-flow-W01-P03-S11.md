---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S11'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Implement the G313 certificate parser producing typed censal facts stamped with the artefact-origin non-official provenance token

## Scope

- `src/cadrumo/adapters/inbound/`

## Description

- Add `domain/censo`: `CertificadoSituacionCensal` typing the six
  officially certified G313 fields, `ActividadLocalCertificada`,
  the `CertificadoCensalError`/`ParseError` family (error codes
  registered), and `censo_facts_from_certificado` projecting only the
  unambiguous axes onto candidate `UserProfileFact` rows under the new
  `PROVENANCE_SOURCE_CENSO_ARTEFACT` non-official token, with each
  display-only exclusion reasoned in the module docstring.
- Add `adapters/inbound/censo`: `parse_certificado_censal_bytes`,
  structure-only per the coordinator ruling - refuses every document
  loudly (unrecognised vs extraction-unpinned) with instructive copy in
  all four catalogues; extraction lands behind the same signature when
  a specimen arrives through the encrypted evidence path.
- Regenerate api stubs; lift the fact projection's import to module
  level after the lazy-import gate flagged the function-local edge (no
  real cycle exists).

## Outcome

Committed (`feat(censo): G313 certificate target shape, fact
projection, and unpinned parser`). Domain + adapter suites 6/6; error
registry suites green (34 with core errors); censo edge cleared from
the lazy-import gate.

## Notes

The refusal tests pin the honesty contract: when a specimen pins the
extraction, the PDF-refusal test must change loudly. Remaining
lazy-import-gate reds are peer-owned (flows/tui) plus two pre-existing
locales edges - owner-triaged. The representantes axis is deliberately
NOT auto-mapped (legal-representative vs IRNR representante fiscal
conflation risk); it surfaces display-only in the cotejo.
