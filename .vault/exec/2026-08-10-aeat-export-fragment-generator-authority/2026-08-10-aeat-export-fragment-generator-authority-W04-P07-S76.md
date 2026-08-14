---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-13'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:93c98c5b2685d927b9879bb4363d45a97a98fe4f940fad5cd71f8caed1932a64'
step_id: 'S76'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Establish the complete Modelo 303 simplified-regime value-arrival authority over immutable evidence-bearing filing rows and the exact annual Orden snapshot, producing one typed per-activity result bound to year, revision, period, evidence, legal and source provenance and a deterministic clock-free digest, and carry it through `M303FilingFacts` and `FilingProducerSnapshot`. Consume the bundled DANA authorities for the 25 per cent reduction of the 2024 ANNUAL simplified-regime cuota devengada por operaciones corrientes, applying it once to the annual cuota and never once per quarter, and never transcribing the municipal anexo

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/application/calculations/`
- `src/cadrumo/application/filing/`
- `src/cadrumo/domain/modelos/`

## Description

- Add a deterministic, immutable per-activity simplified-regime calculation result beside filing rows and the resolved annual Orden snapshot.
- Calculate module cuota devengada, annual DANA reduction, difficult-justification deduction and cuota minima from the exact annual authority.
- Resolve the DANA rate and legal/source provenance from the bundled legal parameter without copying the mutable municipal anexo.
- Require the DANA attestation only for the 2024 final filing period, reject it for quarterly periods, and retain its evidence reference.
- Replay the canonical calculation before revision persistence and carry the exact result through `M303FilingFacts`.
- Refuse a structurally valid, digest-bearing result when calculator replay proves it diverges from the immutable evidence.
- Migrate every direct filing-evidence and filing-facts fixture to the required calculation-bearing contract.
- Add a real 2024 annual Orden proof for the 25 per cent relief and its annual-only boundary.

## Outcome

The simplified-regime value-arrival boundary now has one typed, content-addressed result per filing activity. The result retains the filing period, annual Orden and record-design coordinates, module and activity evidence, legal/source provenance, and a clock-free digest. DANA eligibility is attested rather than inferred from a copied geography, and the 25 per cent relief applies once to each eligible 2024 annual activity cuota devengada before the annual difficult-justification and minimum-cuota calculation.

## Notes

Focused Ruff and basedpyright pass, as does the 117-test real S76 regression slice, including the non-tautological replay-refusal proof. The broader existing exonerado-390 export test presently expects an obsolete English refusal while the live runtime emits the established locale key `application.filing.export.errors.layout_not_renderable`; that unrelated assertion remains outside this step's calculation boundary. S77 remains responsible for replacing the legacy `off_form_result` projection channel.
