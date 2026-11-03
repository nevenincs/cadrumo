---
tags:
  - '#audit'
  - '#export-parity'
date: '2026-09-26'
modified: '2026-11-03'
body_schema: 'body-v2'
body_hash: 'sha256:75c87e4894859fdaa5119121a33be9536f28398f77e91c25e3ba0ad78860e96f'
related:
  - "[[2026-09-23-tuimodelo-export-paths-reference]]"
  - "[[2026-09-07-tuimodelo-export-destinations-adr]]"
  - '[[2026-11-01-export-parity-plan]]'
---

# `export-parity` audit: `export parity campaign findings`

## Scope

CLI and TUI export of IVA and income-tax modelos (periodic and annual summaries, Modelo 100 Renta) in fichero-BOE, XML dictionary, XLSX, CSV and PDF, exercised against isolated synthetic secure stores. The live working ledger is kept in the gitignored campaign scratch home; this record carries the durable findings.

## Findings

### baseline export matrix | info | live lanes against authority generation eedc949c

Fresh installed-CLI journeys, one store each, filing year 2025: Modelo 130 1T-4T fichero-BOE exported; Modelo 100 XML exported and validated against the official 2025 XSD; Modelo 111 and 115 2T exported and parsed back to their oracle casillas; Modelo 180 and 190 annual exported and parsed back; Modelo 303 verified complete and refused export; Modelo 390 verified complete and its journey never attempts export.

### envelope exports blocked on developer identity | high | Modelo 303 and every envelope-prefixed layout refuse

The record design reserves the program identifier and developer NIF header fields for a registered software developer. `AeatProductSoftwareIdentity` existed at `src/cadrumo/domain/filing/software_identity.py` but no entrypoint could supply it, so `src/cadrumo/application/modelo/export.py` refused every layout rendering an envelope prefix. Recommendation: decide how the identity is supplied while no AEAT registration exists.

### retention credit sourced from the declarant's own payer returns | critical | 0596 and 0597 prefilled from Modelos 111, 123 and 190

`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/bindings/0001-declarations.toml:24-47` sums the declarant's own Modelo 111 casilla 28 into Modelo 100 casilla 0596 and Modelo 123 casilla 03 into 0597; the 2025 alternate copies the Modelo 190 summary total. Those returns declare withholding the declarant practised on others as payer, not withholding the declarant suffered. Recommendation: decide the creditable-retention source for retenciones soportadas.

### amortization coefficients authored only for 2025 | high | multi-year asset registers cannot resolve 2022-2024

`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0001-declarations.toml:419-515` declares the coefficient tables valid for 2025 only; no earlier revision declares them.

### modelo calculation exports limited to the filing file | high | no offline XLSX, CSV or PDF of a calculation

The offline workbook renderer the accepted workbook-parity decision relies on no longer exists; `src/cadrumo/application/export/tabular.py` serves only ledger rows; no runtime PDF producer exists. Export also overwrites an existing file, contrary to the accepted destinations decision.

### export route and result divergence | medium | CLI bypasses the supervised operation

The CLI calls the export service directly while the TUI submits `modelo.export`, whose executor returns only the file digest (`src/cadrumo/application/modelo/operation_definitions.py:1143`), so the TUI cannot state evidence status or completeness.

### incomplete producer facts reported as a write failure | medium | Modelo 202

Missing Modelo 202 producer facts raise inside the draft write and surface as `FAIL_MODELO_EXPORT` with only the cause type, not a typed refusal naming the missing facts.

## Recommendations

- Decide the creditable-retention source for Modelo 100 retenciones soportadas and remove the payer-return prefills.
- Author amortization coefficient tables for every supported year through the registry authoring tooling.
- Wire offline XLSX, CSV and a calculation-report PDF as export destinations and refuse to overwrite an existing file.
- Route the CLI export through the supervised operation and widen its public result.

## Phase review 2026-11-02: `2026-11-01-export-parity-plan` P02 (S14, S05, S16, S15)

Reviewed end state `1071f11907..fb96c84e97` against the binding-capability-grade, observation-filing-kind and suffered-withholding-schemas ADRs. Verdict: revision required. Tax-rule citations (RIRPF 79, 7.2, LIRPF 14.1.b, Modelo 130 casilla 18 and Modelo 131 casilla 14 instructions, the marker domain) hold. 203 focused tests passed. One isolated probe confirmed the high finding.

### borrador key refusal breaks the status read | high | one legacy snapshot fails the whole AEAT Sync status
`src/cadrumo/application/live/borrador_100.py:281` raises `LiveApplicationInputError` while listing. `src/cadrumo/application/aeat_sync/status_operation.py:166-173` does not treat that error as an unavailable area, so a single `casilla.<id>` snapshot fails the status read for every area, and also list, latest and the TUI and MCP projections. Capture still accepts free keys. Recommendation: refuse per snapshot (typed skip, or mark only the borrador area unreadable), check keys at capture, add a status test with a legacy snapshot. Reopens S15.

### filed-state gate exemption skips blocking notes | medium | PRESENTADO revisions bypass the existing note check
`src/cadrumo/application/modelo/calculation_note_gate.py:137` returns before the persisted blocking-note check as well as the screen check. Export of a PRESENTADO revision (`export.py:897`) and amendments built from it (`amendment_actions.py:206`) no longer see blocking notes. Recommendation: exempt only the screen check. Handling of pending-local revisions filed before the cap needs a follow-on decision.

### form and gate disagree on stale revisions | medium | the form does not project `calculation_screen_outdated`
Only the gate reads the stamp. The form, its next step and the TUI and MCP projections offer verify, export and file for unstamped revisions, which the gate then refuses. Recommendation: project staleness in `work_form_notes` and offer recalculation.

### previews omit the advisory note | medium | report PDF and Sheets workbook show capped values without the note
No module under `calculation_report*` or `storage/calc_sheets/` reads source issues or notes, although the ruling says both previews show the note.

### end-to-end cap evidence | medium | cap tests bypass the real calculate, verify, export and file actions
`test_advisory_binding_value_gate.py:150-214` and `test_modelo_100_actividad_retencion_credit.py` hand-build revisions and call a private helper. Recommendation: one profile-persistence test from Modelo 130 calculation with withholding-bearing rows through verify, export and file refusals, stamped identity and form agreement.

### borrador re-import of a superseded document | medium | re-importing A after B leaves B active silently
With content identity independent of the capture instant, `snapshot_base.py:329` returns the stored SUPERSEDED snapshot. Recommendation: reactivate it or report the outcome.

### public result contract | medium | `unowned_casillas` is required and schema versions were not bumped
`borrador_100_contracts.py:234` has no default; nine result schemas changed fingerprint at the same `schema_version`. A result journaled before the change may fail validation on replay. Recommendation: default to an empty tuple, or confirm journaled results are never re-validated.

### proven-zero note not persisted | low | a reloaded form cannot show a proven zero
`calculation_bucket_actions.py:835` drops it. Acknowledged in the ledger.

### stamp reads routing fact at today's date | low | cap-map redirect uses `today_madrid()`
`retenciones_routing_integrity.py:48`. Single variant today, so no current effect.

### operator-keyed casilla 06 stays blocked | low | an operator figure cannot clear the cap
Consistent with the rulings. Whether operator input should clear it is a follow-on decision.

Pending verification, not defects: installed borrador stdio acceptance on a disposable host; 31 Chromium sede and live tests; whether recorded results are re-validated on replay; publication and runtime adoption of the S05 and S16 registry edits; the ADR's stored-revision replay test and the sede-level Modelo 131 DPA disagreement test.

## Re-review 2026-11-02: P02 fixes (`4e3833056c` to `2c8663b9c4`)

Resolved: borrador per-snapshot refusal and capture-time key check, PRESENTADO exemption narrowed to the screen check, form and declarations-list agreement on recalculation, re-import outcome, routing fact read at the period date. Partly resolved: previews (the review workbook shows the note; the signed report stays sealed-only by orchestrator decision), public result contract (`unowned_casillas` defaulted; `outcome` stays required because a result recorded under an older contract is refused before re-validation, `src/cadrumo/application/operations/_projection_read.py:468-475`, and a default would assert an outcome that never happened). Open by decision: proven-zero persistence, operator-keyed casilla 06. 144 focused tests passed.

### borrador support-envelope refusal | medium | a capture outside the support envelope still fails the status read
`src/cadrumo/application/live/borrador_100.py:158` lets `FilingYearOutsideSupportEnvelopeError` escape the status guard at `src/cadrumo/application/aeat_sync/status_operation.py:81,169`. Recommendation: return a typed per-snapshot refusal.

### signed report on stale sealed revisions | medium | the report omits the screen check that export applies
`src/cadrumo/application/export/calculation_report_export.py:276` signs a sealed revision verified before the cap, with no stamp and no note, while export refuses it as stale. Recommendation: apply the screen check to non-filed sealed revisions.

### review workbook omits notes without a casilla | low | unrouted blocking notes and stale revisions show no finding
`src/cadrumo/application/export/review_snapshot_loader.py:333`.

### summary gate outside the per-row guard | low | a stamp error can fail the whole declarations list
`src/cadrumo/application/modelo/declaration_summary.py:98`.

### build-time routing check date | low | checked at year end while calculation reads at period end
`src/cadrumo/domain/renta/retenciones_routing_integrity.py:103`. No effect with one routing variant.

## Final P02 re-review 2026-11-02 (`7a0846f6ed..90c716ec26`)

Resolved: borrador support-envelope refusal, signed report screen check for non-filed sealed revisions, workbook notes without a casilla, summary per-row guard. Checked and sound: proven-zero persistence and identity, filed-before-cap refusal and recalculation path, filing kind without the DPA reading, the 31 December reach date for undated instalment periods (`src/cadrumo/application/modelo/amendment_regime_policy.py:137`), and every local-file export passing the gate (`src/cadrumo/application/modelo/export.py:706`). 279 focused tests passed on an archive of `90c716ec26`.

### saved-review staleness | medium | the review screens the old rendering snapshot through current facts
`src/cadrumo/application/modelo/calculation_note_gate.py:186-207` can disagree with the export gate's current law-selected snapshot. Recommendation: use the gate's snapshot; treat an unresolvable snapshot as stale.

### outdated borrador count | medium | a corrupt older-schema row is counted as outdated, not raised
`src/cadrumo/adapters/persistence/profile/snapshots.py:224-229` ignores the unreadable reason. Recommendation: count only lineage refusals.

### outdated borrador remedy | low | the count never clears and is read in a second scan
The advice implies re-import clears it; the count covers the whole store and comes from a separate read.

### signed report on rows filed before the cap | low | an unstamped filed revision is signed with its capped figure and no note
Orchestrator decision under the 2026-11-02 ruling: the report and the review workbook apply the `filed_before_grade_cap` predicate as export does.

Out of scope, queued: Modelo 131 2024-onward complementaria export refuses the boolean `declaracion-complementaria` value at position 692 (`text value must be text or absent`).

## Phase review 2026-11-03: `2026-11-01-export-parity-plan` P03 (S17, S18, S29, S06)

Reviewed against `2026-11-01-export-parity-suffered-withholding-schemas-adr` (ADR D): the namespace and key grammar, the record and its write port, the certificate and absence operations, the `retencion_soportada` source kind and resolver, and the 0596, 0597 and 0603 bindings with the borrador cross-check marker. Sound: the keyed `payer_ref`, the exact-profile worker composition, the self-NIF, unsupported-year and undeclared-family refusals, the revision-guarded overwrite and removal, the absence/record contradiction handling, the fail-closed applicability, and the 2022 baseline bindings with `cross_check_only`. Findings below; the first three are fixed, the rest need an operator decision.

### payer tax ID without a checksum | medium | the import only trimmed and upper-cased the payer ID
`src/cadrumo/application/retencion_soportada_certificado/executor.py` keyed the row by `tax_id_identity_token`, so a mistyped payer ID stored a certificate under a payer that does not exist. Fixed in `bc9c230741`: the import validates through the registry tax-ID validator and refuses a failing ID with the existing `validation` reason, which already names the payer ID. No contract change.

### printed and bare payer ID forms | medium | `B-0000001-8` and `B00000018` keyed two rows
The same change keys the row by the validator's canonical form, so one payer is one row and the own-NIF check also sees the separated form. Teeth: the printed form meets the stored row as a stale revision instead of opening a second row.

### listed absence label in the worker language | low | `--language` did not reach `income_class_label`
The worker worded the label in the profile language and the CLI printed it. Fixed in `8e15a7a749`: the CLI words it from the class token in the invocation language. The projection field stays, because the desktop reads it in the person's language.

### certificate fingerprint not checked against custody | medium | a payer-certificate record rests on an unverified digest
ADR D section 3 defines `evidence_fingerprint` as the sha256 of the certificate bytes held in attachment custody, but its list of write-port refusals has no custody check, and P03 gives the operator no route that puts certificate bytes into attachment custody. The CLI takes a bare `--evidence-sha256`, and the resolver passes it on as provenance `fingerprint`. Not fixed: a custody check needs a custody-ingest route and a new refusal reason, which is a public-contract change (`RetencionSoportadaCertificadoRefusalReason`, locale keys, operation manifest). Operator decision: add the check and its route, or amend ADR D to call the fingerprint operator-asserted.

### same-fingerprint amendment | low | re-entering figures from the same certificate is refused as `validation`
`RetencionSoportadaRecord` refuses `replaces_evidence_fingerprint == evidence_fingerprint`, and the executor fills the replaced fingerprint from the stored row, so correcting a typo against the same certificate file fails with the generic reason. ADR D section 4 says only that "a corrected or replacement certificate overwrites that row"; it does not settle the same-file case. Not changed. The workaround is remove then record, which drops the lineage. Operator decision: allow it (with no `replaces` value) or keep the refusal and give it its own reason.

### proven zero from the profile carries `PROFILE_FIELD` | medium | ADR D section 1 lists two terminal origins
The provider registration admits `PAYER_CERTIFICATE`, `OPERATOR_INPUT` and `PROFILE_FIELD`, and the resolver stamps `PROFILE_FIELD` on a class the profile positively declares absent (the same reading the activity-rental applicability uses). ADR D section 1 says "Terminal origins are `PAYER_CERTIFICATE` and `OPERATOR_INPUT`"; section 5 grants the proven zero without an attestation but names the origin only for the attestation. Not changed. Operator decision: amend ADR D to admit `PROFILE_FIELD`, or stamp `OPERATOR_INPUT`.

### attestation against a ledger income row | low | the section 5 hypothesis is not implemented
ADR D section 5 hypothesises reporting an attestation contradicted by a ledger income row of the same class. Only the record-versus-attestation contradiction exists. It was marked a hypothesis, so this is a gap to schedule, not a defect.

### verification pending | note | live Modelo 100 credit tests cannot run on the shared tree
`test_modelo_100_retencion_soportada_credits_live.py` and `test_retencion_soportada_absence_m100.py` fail at construction with `CalculationActionPorts.__init__() missing ... 'credit_resolution_reader'`. The uncommitted P04 edits in `src/cadrumo/application/modelo/calculation_action_ports.py` add that argument before its callers are updated. Not caused by P03 or by the fixes above. Re-run both files when the P04 writer commits.

### P03 findings ruled and resolved 2026-11-03 | medium | the three open P03 findings follow the operator's rulings
The operator ruled on each open item. The `PROFILE_FIELD` origin is admitted by the ADR amendment of 2026-11-03. The certificate fingerprint is checked against attachment custody by the write port, and the import takes the certificate file (`01a28ab372`). A correction against the same certificate overwrites the row and keeps the lineage (`18aa70a39f`). Recommendations kept open: the desktop files named in the amendment still send a typed fingerprint and know none of the new refusal reasons; the live Modelo 100 credit tests were re-run against the new custody check and passed.

