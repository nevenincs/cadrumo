---
tags:
  - '#audit'
  - '#export-parity'
date: '2026-09-26'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:3f4c3f263e5ba648cae8ee173aa663b29b0bd10f1f08aa671a1c87354ce5e22a'
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
