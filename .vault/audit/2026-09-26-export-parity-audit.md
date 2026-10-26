---
tags:
  - '#audit'
  - '#export-parity'
date: '2026-09-26'
modified: '2026-09-26'
body_schema: 'body-v2'
body_hash: 'sha256:27bfe93cb80c5d3cc52887c92a6cdbe4f0da05871cd7f5baa1e0e4a1920c63bb'
related:
  - "[[2026-09-23-tuimodelo-export-paths-reference]]"
  - "[[2026-09-07-tuimodelo-export-destinations-adr]]"
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
