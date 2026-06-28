---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-21-fresh-cli-persona-testimonial-wave-plan]]'
  - '[[2026-05-21-fresh-cli-persona-testimonial-briefs-audit]]'
---

# Fresh CLI persona testimonials

Fresh testimonial-driven CLI wave after the cross-campaign hardening
closeout. Six persona agents operated only through `uv run aeat ...`,
`uv run --no-sync aeat ...`, and `--help`, each with an isolated scratch
root under `.vault-scratch/fresh-personas`.

## Persona Verdicts

| Persona | Task | Verdict |
|---|---|---|
| Ana | Sole-professional profile and Modelo 130 | partial success; verified 130 workflow works locally, but applicability guidance is weak |
| Bruno | S.L. company profile and Modelo 303 | partial success; company profile create path has verified parsing defect |
| Clara | Landlord Renta / Modelo 100 rental income | partial success; rental casillas visible, ledger traceability absent |
| Diego | Payroll retentions / Modelo 111 | partial success; calculation works, workflow guidance is weak |
| Elena | Correction and filing handoff | partial success; handoff path discoverable, export hint is wrong |
| Fatima | Legal/manual explainability | partial success; legal/source ids visible, source drill-down is not discoverable |

## Confirmed Positives

- Modelo discovery remained usable across 100, 111, 130, 303, and company
  tax families.
- Profile creation and inspection exposed the facts needed by the
  personas, including entity type, IVA regime, IRPF estimation regime,
  and withholding flags.
- Modelo 130 calculation and verification completed in coordinator
  reproduction after explicit zero bindings were supplied.
- Modelo 111 calculation produced the expected retention total from
  manually supplied casillas.
- Modelo 303 work creation and calculation completed in coordinator
  reproduction.
- Formula explainability exposes legal and source reference identifiers.
- Local-only filing and export copy clearly says it does not submit to
  AEAT.

## Persona Findings

### Ana - Sole Professional

Ana could create an autonomo profile, inspect Modelo 130, create a work
unit, supply missing bindings, and calculate a draft. She did not get a
profile-filtered explanation that Modelo 130 applies to her and why.

Highest-value feedback:

- major: no direct "applies because" explanation after profile creation;
- major: profile creation's next action does not suggest likely modelo,
  period, or revision;
- minor: binding ids are technically precise but not first-time
  operator-friendly.

### Bruno - Company Administrator

Bruno could create a minimal profile, edit it into a legal entity, and
inspect Modelo 303 and company-tax models. Direct S.L. profile creation
failed.

Highest-value feedback:

- major: `--entity-type legal_entity --legal-entity-form sl` is rejected
  as though `sl` were an IRPF income category;
- major: company setup still exposes spouse/family IRPF prompts and
  defaults in confusing places;
- minor: the first successful minimal profile does not clearly show
  whether it represents a natural person or company.

### Clara - Landlord

Clara found Modelo 100 and rental-income casillas such as 0102, 0109,
0113, 0115, 0131, 0150, and 0153. She could not find ledger-bound
traceability for rental-property expense casillas.

Highest-value feedback:

- major: capital-inmobiliario rental expenses are visible as manual
  casillas but not ledger-traceable;
- major: Renta calculation asks for prior relations before rental-only
  work feels understandable;
- cosmetic: some Modelo help discovery felt incomplete from the first
  help surface.

### Diego - Payroll Retentions

Diego discovered Modelo 111, its casillas, and formulas. Manual
calculation of casillas 03 and 09 produced total casilla 28 and result
casilla 30 as expected.

Highest-value feedback:

- major: `casillas 111 --required` returns only headers, making Modelo
  111 look like it has no practical required input set;
- major: readiness says `ready True` and `missing 0` before any payroll
  figures exist, which reads like filing readiness rather than workflow
  readiness;
- minor: aggregate input JSON shape is not discoverable from help.

### Elena - Correction Handoff

Elena created and calculated a Modelo 303 work unit, then verified that
filing/export were blocked until verification. She discovered the
amendment route through `work amend --help`.

Highest-value feedback:

- major: verification refusal reports `DRAFT_HAS_ERRORS` without
  actionable field-level detail;
- major: export recovery text says `aeat app modelo verify`, but the
  actual surface is `aeat app modelo work verify`;
- minor: `work amend --help` does not enumerate expected amendment-kind
  values.

### Fatima - Legal Explainability

Fatima used registry, overview, modelo, casilla, formula, and binding
surfaces. Formula `--explain` exposed legal/source ids, but she could
not discover a human-readable manual or source drill-down.

Highest-value feedback:

- major: `aeat app manual --help` does not exist, so manual
  explainability is not discoverable by name;
- major: legal and source refs are opaque ids without a visible CLI
  drill-down to title, URL, or excerpt;
- major: `casillas 303 --period 1T --form-number 69` returns only the
  header even though unfiltered computed casillas include number 69.

## Shared Import-Error Reports

Ana, Bruno, Clara, Diego, and Elena reported an internal
`ImportError: cannot import name 'SecureObjectUnreadable' from
'aeat.adapters.persistence.storage.sql'` on at least one workflow path.

Coordinator reproduction did not confirm the import error in a fresh
environment. The symbol is currently exported from
`aeat.adapters.persistence.storage.sql`, and clean coordinator runs of
Modelo 303 work create, filing-record list, verification-report list,
Modelo 303 calculate, Modelo 130 calculate, and Modelo 130 verify did
not crash. This remains an investigation item because independent
personas reported it, but it is not promoted as a verified stable defect
without a smaller reproducer.
