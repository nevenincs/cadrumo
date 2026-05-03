# AEAT CLI v6 tax filing flow tapes

These tapes define granular user-facing CLI calls from setup through ledger
review, invoice review, declaration calculation, review, export, verification,
and corrective declaration work.

## Design Rules Applied

- Setup and app are separate domains.
- Import is an action, not a nested command domain.
- Import verification is `ledger import ... --verify`.
- Gap and duplicate diagnostics are output from import verification.
- Record decisions use `ledger edit`.
- Skipping uses `ledger edit --skip true|false --reason REASON`.
- Split values must add to `1.0`.
- Corrective declaration work recalculates a new draft after late or corrected records.
- Export writes to `--output`.
- Verify reads the exported file through `--file`; it has no export flag.
- `--verbose` exists for diagnostic and state-sensitive workflows.

## Command Surface

| Command | Description |
| --- | --- |
| `aeat setup auth status` | Shows configured provider and login state. |
| `aeat setup auth configure --provider clave_movil` | Configures a supported authentication provider. |
| `aeat setup auth login` | Starts the configured AEAT login flow. |
| `aeat setup profile list-keys` | Lists editable taxpayer profile keys. |
| `aeat setup profile set KEY VALUE` | Sets one schema-backed profile value. |
| `aeat setup profile validate` | Validates profile readiness. |
| `aeat app overview status --calendar --from DATE --to DATE` | Shows due, late, filed, and unknown period state. |
| `aeat app overview status --period PERIOD --verbose` | Explains one period and next actions. |
| `aeat app ledger import PATH --provider PROVIDER --dry-run` | Tests a transaction file before saving rows. |
| `aeat app ledger import PATH --provider PROVIDER --verify --source PATH` | Imports rows and runs backend verification. |
| `aeat app ledger review --filter KEY=VALUE` | Lists rows or diagnostics through cohesive filters. |
| `aeat app ledger review --id RECORD_ID --verbose` | Shows one row, provenance, edit state, and skip state. |
| `aeat app ledger edit --id RECORD_ID --set COLUMN=VALUE --reason REASON` | Edits auditable ledger fields. |
| `aeat app ledger edit --id RECORD_ID --skip true --reason REASON` | Skips a row without deleting it. |
| `aeat app ledger edit --id RECORD_ID --skip false --reason REASON` | Returns a skipped row to review. |
| `aeat app ledger edit --id RECORD_ID --split business=SHARE --split personal=SHARE --reason REASON` | Splits one source row into share values. |
| `aeat app ledger edit --id RECORD_ID --split clear --reason REASON` | Clears split metadata and returns to the source row. |
| `aeat app invoice import PATH --kind issued --dry-run` | Validates issued invoice records. |
| `aeat app invoice import PATH --kind received --dry-run` | Validates received invoice records. |
| `aeat app invoice review --filter status=pending --filter kind=received` | Lists invoice records needing review. |
| `aeat app invoice review --id INVOICE_ID --verbose` | Shows invoice lines, totals, metadata, and links. |
| `aeat app invoice edit --id INVOICE_ID --set COLUMN=VALUE --reason REASON` | Edits invoice metadata. |
| `aeat app invoice match --period PERIOD` | Matches invoice records to payments and ledger rows. |
| `aeat app declaration calculate --period PERIOD --modelo MODELO` | Calculates and prints a compact summary table plus next action. |
| `aeat app declaration review --period PERIOD --modelo MODELO --format table` | Reviews calculated values and warnings. |
| `aeat app declaration approve --id draft_MODELO_PERIOD --by reviewer --reason REASON` | Records human approval. |
| `aeat app declaration validate --id draft_MODELO_PERIOD` | Validates only after approval. |
| `aeat app declaration export --id draft_MODELO_PERIOD --output PATH` | Writes a local AEAT-compatible artifact. |
| `aeat app declaration verify --id DRAFT_ID --file PATH` | Verifies an exported file against the approved local draft. |
| `aeat app declaration calculate --period PERIOD --modelo MODELO` | Recalculates a draft after late or corrected records. |

## Tape: Setup From Unknown State

| Step | Command | User work represented |
| --- | --- | --- |
| 1 | `aeat --help` | User discovers setup/app boundary. |
| 2 | `aeat setup status` | User checks readiness without mutating state. |
| 3 | `aeat setup auth providers` | User sees supported auth methods. |
| 4 | `aeat setup auth configure --provider clave_movil` | User configures login. |
| 5 | `aeat setup auth login` | User authenticates. |
| 6 | `aeat setup auth whoami` | User confirms identity. |
| 7 | `aeat setup init --name autonomo-2026` | User creates a profile. |
| 8 | `aeat setup profile set tax.id 12345678Z` | User enters required data. |
| 9 | `aeat setup profile set tax.name Kent` | User enters display identity. |
| 10 | `aeat setup profile set activity.label design` | User records design activity. |
| 11 | `aeat setup profile set address.postcode 28013` | User enters address fact. |
| 12 | `aeat setup profile validate` | User closes setup readiness. |

## Tape: Invalid And Incomplete N26 Imports

| Step | Command | User work represented |
| --- | --- | --- |
| 1 | `aeat app ledger import ./downloads/n26-invoices.pdf --provider n26 --dry-run` | Invalid ledger input is rejected before state changes. |
| 2 | `aeat app ledger import ./downloads/n26-jan.csv --provider n26 --dry-run` | User tests January rows. |
| 3 | `aeat app ledger import ./downloads/n26-jan.csv --provider n26 --verify --source ./downloads/n26-jan.pdf --verbose` | User imports and compares against the original source PDF. |
| 4 | `aeat app ledger import ./downloads/n26-feb-mar.csv --provider n26 --dry-run` | User tests missing months before saving. |
| 5 | `aeat app ledger import ./downloads/n26-feb-mar.csv --provider n26 --verify --source ./downloads/n26-feb-mar.pdf` | User imports missing months with verification. |
| 6 | `aeat app ledger review --filter issue=gap --filter period=2026-Q1` | User reviews any remaining coverage gaps. |

## Tape: Duplicate And Wrong Account Import

| Step | Command | User work represented |
| --- | --- | --- |
| 1 | `aeat app ledger import ./downloads/n26-business-q1.csv --provider n26 --verify` | User imports the intended business file. |
| 2 | `aeat app ledger import ./downloads/n26-business-q1-copy.csv --provider n26 --verify --verbose` | Duplicate diagnostics appear during verification. |
| 3 | `aeat app ledger review --filter issue=duplicate --filter period=2026-Q1` | User inspects duplicate rows. |
| 4 | `aeat app ledger edit --id row_dup_002 --skip true --reason duplicate-file` | Duplicate rows are skipped without deleting trace. |
| 5 | `aeat app ledger import ./downloads/n26-personal-q1.csv --provider n26 --verify --source ./downloads/n26-personal-q1.pdf` | User accidentally imports personal data. |
| 6 | `aeat app ledger review --filter import=import_003 --filter period=2026-Q1` | User inspects rows from that import. |
| 7 | `aeat app ledger edit --id row_personal_001 --skip true --reason personal-account` | User marks the row skipped. |
| 8 | `aeat app ledger edit --id row_personal_001 --skip false --reason user-corrected-account` | User tests the revision path. |
| 9 | `aeat app ledger edit --id row_personal_001 --skip true --reason personal-account-confirmed` | User finalizes the corrected decision. |

## Tape: Manual Ledger Decisions

| Step | Command | User work represented |
| --- | --- | --- |
| 1 | `aeat app ledger review --filter status=pending --filter period=2026-Q1` | User finds pending rows. |
| 2 | `aeat app ledger review --id row_1042` | User inspects one row. |
| 3 | `aeat app ledger edit --id row_1042 --set category=software --set business.share=1.0 --set reference=invoice-901 --set comments=invoice-reviewed --reason invoice` | User categorizes and references a business cost. |
| 4 | `aeat app ledger edit --id row_1043 --set category=design-services --set business.share=1.0 --set comments=client-payment --reason client-payment` | User classifies income. |
| 5 | `aeat app ledger edit --id row_1050 --split business=0.45 --split personal=0.55 --reason mixed-card-payment` | User splits mixed spending. |
| 6 | `aeat app ledger edit --id row_1050 --split clear --reason corrected-single-use` | User clears a mistaken split. |
| 7 | `aeat app ledger edit --id row_1050 --split business=0.45 --split personal=0.55 --reason mixed-card-payment-confirmed` | User applies corrected split metadata. |
| 8 | `aeat app ledger edit --id row_1051 --skip true --reason private-expense` | User decides a row is not needed. |
| 9 | `aeat app ledger edit --id row_1051 --skip false --reason invoice-found` | User reverses that decision. |
| 10 | `aeat app ledger edit --id row_1051 --set category=supplies --set business.share=1.0 --set document.path=./receipts/receipt-901.pdf --reason invoice-found` | User links supporting evidence. |

## Tape: Declaration Export And Verification

| Step | Command | User work represented |
| --- | --- | --- |
| 1 | `aeat app overview status --calendar --from 2026-01-01 --to 2026-04-20` | User discovers Q1 obligations. |
| 2 | `aeat app overview status --period 2026-Q1` | User reviews period state. |
| 3 | `aeat app declaration calculate --period 2026-Q1 --modelo 303` | CLI prints summary and next action. |
| 4 | `aeat app declaration review --period 2026-Q1 --modelo 303 --format table` | User reviews values. |
| 5 | `aeat app declaration edit --id draft_303_2026-Q1 --set casilla.71=1200.00 --reason manual-check` | Manual edit resets approval. |
| 6 | `aeat app declaration review --period 2026-Q1 --modelo 303 --format table` | User reviews again. |
| 7 | `aeat app declaration approve --id draft_303_2026-Q1 --by reviewer --reason reviewed-against-ledger` | User approves. |
| 8 | `aeat app declaration validate --id draft_303_2026-Q1` | CLI validates. |
| 9 | `aeat app declaration preview --id draft_303_2026-Q1` | User inspects a non-filing preview. |
| 10 | `aeat app declaration export --id draft_303_2026-Q1 --output ./exports/2026-q1` | CLI writes local export. |
| 11 | `aeat app declaration verify --id draft_303_2026-Q1 --file ./exports/2026-q1-verify.json` | CLI verifies the exported file. |

## Tape: Behind With Multiple Periods

| Step | Command | User work represented |
| --- | --- | --- |
| 1 | `aeat app overview status --calendar --from 2025-10-01 --to 2026-07-20` | User discovers late and current periods. |
| 2 | `aeat app overview status --period 2025-Q4` | User reviews older period. |
| 3 | `aeat app overview status --period 2026-Q1` | User reviews next period. |
| 4 | `aeat app overview status --period 2026-Q2` | User reviews current period. |
| 5 | `aeat app ledger import ./downloads/n26-2025-q4.csv --provider n26 --verify` | User imports old records. |
| 6 | `aeat app ledger import ./downloads/n26-2026-q1.csv --provider n26 --verify` | User imports Q1. |
| 7 | `aeat app ledger import ./downloads/n26-2026-q2.csv --provider n26 --verify` | User imports Q2. |
| 8 | `aeat app ledger review --filter issue=gap --filter period=2026-Q1` | User checks Q1 coverage. |
| 9 | `aeat app ledger review --filter issue=gap --filter period=2026-Q2` | User checks Q2 coverage. |
| 10 | `aeat app ledger edit --id row_3110 --split business=0.60 --split personal=0.40 --reason shared-subscription` | User handles a shared subscription. |
| 11 | `aeat app declaration calculate --period 2025-Q4 --modelo 303` | User recalculates old period. |
| 12 | `aeat app declaration calculate --period 2026-Q1 --modelo 303` | User calculates Q1. |
| 13 | `aeat app declaration calculate --period 2026-Q2 --modelo 303` | User calculates Q2. |

## Tape: Corrective Declaration After New Data

| Step | Command | User work represented |
| --- | --- | --- |
| 1 | `aeat app overview status --period 2026-Q1` | User sees a previously exported period. |
| 2 | `aeat app invoice import ./late-file/invoice-2026-041.pdf --kind received --dry-run` | User tests a late invoice record. |
| 3 | `aeat app invoice import ./late-file/invoice-2026-041.pdf --kind received` | User saves the late invoice record. |
| 4 | `aeat app invoice edit --id inv_2041 --set base=320.00 --set iva.rate=21 --set iva.amount=67.20 --set payment.id=row_1141 --reason late-invoice` | User completes invoice metadata. |
| 5 | `aeat app ledger edit --id row_1141 --set category=supplies --set business.share=1.0 --set reference=inv_2041 --reason found-after-export` | User updates the linked ledger row. |
| 6 | `aeat app invoice match --period 2026-Q1` | User reruns matching. |
| 7 | `aeat app declaration calculate --period 2026-Q1 --modelo 303` | User recalculates after late evidence changed the period. |
| 8 | `aeat app declaration review --period 2026-Q1 --modelo 303 --format table` | User reviews changed values. |
| 9 | `aeat app declaration approve --id draft_303_2026-Q1 --by reviewer --reason recalculation-reviewed` | User approves recalculated state. |
| 10 | `aeat app declaration validate --id draft_303_2026-Q1` | CLI validates recalculated state. |
| 11 | `aeat app declaration export --id draft_303_2026-Q1 --output ./exports/2026-q1-recalculated` | CLI writes recalculated export. |
| 12 | `aeat app declaration verify --id draft_303_2026-Q1 --file ./exports/2026-q1-recalculated-verify.json` | CLI verifies the recalculated export. |

## Remaining Design Gaps

| Gap | V6 surface |
| --- | --- |
| Ledger schema cannot be manually approved. | Backend audit for stable rows, skip, split, edit history, and migrations. |
| Import verification must be real backend behavior. | `ledger import ... --verify`. |
| Split and clear need backend metadata. | `ledger edit --split business=SHARE --split personal=SHARE` and `ledger edit --split clear`. |
| Invoice retention and IVA category need implementation audit. | `invoice edit --set retention.rate=... --set iva.category=...`. |
| Calculate output needs a contract. | `declaration calculate` prints summary and blockers. |
| Corrective declaration identity needs official behavior. | a recalculated draft, using latest required AEAT justificante id where applicable. |
