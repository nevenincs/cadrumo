---
tags:
  - '#plan'
  - '#iva-workflow'
date: '2026-09-23'
tier: L1
related:
  - '[[2026-09-21-iva-workflow-m303-filing-evidence-authoring-adr]]'
modified: '2026-09-24'
body_schema: body-v2
body_hash: 'sha256:3ec5d48a3923a4ea199c7a70ff379dd21231de92b763ae303dd1854ff0f2c174'
---

# `iva-workflow` plan

Ordinary Modelo 303 evidence follows the record design's period rules, and monthly settlement periods are admitted.

## Description

Approved 2026-09-23. Basis: the operator's standing pre-approval of IVA implementation work in this session, and the coordinator's direction to amend the M303 filing-evidence decision before changing the persisted schema, then plan and implement monthly Modelo 303.

The governing decision is `2026-09-21-iva-workflow-m303-filing-evidence-authoring-adr`, Amendment 3, which carries the grounding (DP30301 fields 14, 23 and 24, Notas 3, 4 and 5, in every bundled design from 2022 through `2026-y-siguientes`; Orden EHA/3786/2008 art. 7). All Steps implement that amendment; no further costly decision is expected. The wrong annual-volume output the same reading exposed is already corrected outside this plan.

Scope: persisted evidence shape (S01), coordinate and authoring (S02), the calculate operation request (S03), CLI (S04), TUI (S05), documentation sequences (S07), and installed proof (S06). Out of scope: the exempt-from-390 branch, typed per-field period applicability in the registry, and monthly-settlement eligibility, which S02 only identifies an owner for.

## Steps

- [x] `S01` - make the persisted ordinary Modelo 303 evidence period-scoped: optional annual-volume answer, Modelo 390 evidence required only in the last period, stored revisions still valid; `src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py, application/filing/producer_snapshot.py, application/filing/export_producer.py, application/modelo/m303_filing_evidence.py`.
- [x] `S02` - admit monthly coordinates and author period-scoped evidence; refuse a 390 attestation outside the last period; record which owner refuses monthly work for a non-monthly filer; `src/cadrumo/application/modelo/m303_ordinary_evidence_coordinate.py, m303_ordinary_filing_evidence_authoring.py, m303_exonerado_390_applicability_attestation.py`.
- [x] `S03` - version the calculate request: nested ordinary request without the annual-volume answer and with an optional attestation pair, schema version 3, previous pending invocations refused; `src/cadrumo/application/modelo/operation_definitions.py and its conformance tests`.
- [x] `S04` - align the CLI and quickfile flags with the period rule and regenerate the CLI reference and locale keys; `src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py, _app_quickfile.py, command specs, locales`.
- [x] `S05` - align the TUI evidence form: no annual-volume question, attestation only in the last period; `src/cadrumo/entrypoints/tui/modelo/m303_evidence.py, view/overview.py, lifecycle.py, locales`.
- [x] `S07` - update the Modelo 303 and 390 docs sequence contracts to the period rule and regenerate their goldens through the sequence runner; `docs/_sequences/contracts/how-to/modelo-303, modelo-390 and the other contracts that calculate Modelo 303`.
- [x] `S06` - prove the attestation contract at 4T and a monthly coordinate on an installed wheel built from a committed source; `dev/acceptance/iva/installed_m303_evidence_journey.py`.

## Parallelization

Sequential. S01 fixes the persisted shape every later Step consumes; S02 and S03 build on it in order; S04 and S05 both consume the S03 request and may run in parallel only with disjoint files; S07 needs S04; S06 needs every earlier Step committed so the wheel is built from a committed source.

## Verification

- Persisted revisions written under the previous rules load and export unchanged in meaning; a last-period revision without Modelo 390 evidence is refused; a non-final revision without it is valid.
- A monthly coordinate (for example 2026/01) authors evidence and calculates; a quarterly non-final period calculates without any attestation; 4T and 12 require the attestation; an attestation supplied outside the last period refuses with a typed REFUSED code.
- A pending invocation recorded under the previous request schema is refused, never replayed.
- Focused unit and integration tests pass with `-n0` and explicit markers; ruff, format, ty, basedpyright and pyrefly are clean on every changed file; locale audit shows no new missing or extra key; the generated CLI reference and docs goldens are regenerated through their owners and their checks are clean.
- The installed journey on a wheel built from a committed source proves the 4T attestation contract and a monthly calculation, with receipts carrying commit, wheel digest, authority generation and installed module hash.
