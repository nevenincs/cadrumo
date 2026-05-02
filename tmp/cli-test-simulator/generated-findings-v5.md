# Kent/N26 CLI v5 audit findings

Seed: `kent-n26-v5`
Runs: `250`
Generated: `2026-05-02T23:26:04.536Z`

Kent is an autonomo who uses N26 and can download invoices, but does not know AEAT obligations or the CLI shape.

## Metrics

| Metric | Value |
| --- | --- |
| Completion Rate | 56% |
| Pending Review Rate | 44% |
| Commands To Success | 29.8 |
| Warning Count | 4.6 |
| Error Count | 0.0 |
| Command Guess Distance | v5 rerun |
| Record Completeness | 56% |
| Human Review Gate | tracked |
| Tax-Safety Risk | 0% |

## Findings

### Top Failed Command Guesses

- aeat setup auth configure --provider clave_permanente (56): Clave Permanente should remain research-only until implemented.

### Setup And Profile Friction

- aeat setup auth status (176): Auth state must be inspectable without changing it.
- aeat setup auth configure --provider clave_movil (176): Auth configuration names a supported provider.
- aeat setup auth login (176): Authentication is an actual login step.
- aeat setup auth whoami (176): Identity is exposed through auth/profile, not account.
- aeat setup profile list-keys (176): Profile keys must be discoverable.
- aeat setup profile set tax.id 12345678Z (176): Profile edits use schema-backed keys.

### Ledger Record Gaps

- aeat app ledger import ./downloads/n26-2025-Q4.csv --provider n26 --dry-run (92): Statement import is tested first.
- aeat app ledger import ./downloads/n26-2025-Q4.csv --provider n26 (92): Transaction records are imported into ledger.
- aeat app ledger import ./downloads/n26-2025-Q4.csv --provider n26 --verify --original ./downloads/n26-2025-Q4.pdf (92): Imported records are checked against the original downloaded file.
- aeat app ledger list --filter status=pending --filter period=2025-Q4 (92): Manual ledger review is visible through status filters.
- aeat app ledger import ./downloads/n26-2026-Q2.csv --provider n26 --dry-run (82): Statement import is tested first.
- aeat app ledger import ./downloads/n26-2026-Q2.csv --provider n26 (82): Transaction records are imported into ledger.

### Invoice Enrichment Gaps

- aeat app invoice list --filter status=pending --filter kind=received (250): Missing invoice metadata is visible.
- aeat app invoice import ./invoices/issued-2025-Q4.csv --kind issued --dry-run (92): Issued invoices stay under singular invoice.
- aeat app invoice import ./invoices/received-2025-Q4.csv --kind received --dry-run (92): Received invoices stay under singular invoice.
- aeat app invoice match --period 2025-Q4 (92): Invoice matching checks payments and ledger references.
- aeat app invoice import ./invoices/issued-2026-Q2.csv --kind issued --dry-run (82): Issued invoices stay under singular invoice.
- aeat app invoice import ./invoices/received-2026-Q2.csv --kind received --dry-run (82): Received invoices stay under singular invoice.

### Overview And Period Discovery

- aeat app overview --calendar --from 2025-10-01 --to 2026-07-20 (250): Overview handles filing discovery without a separate calendar command.
- aeat app overview --period 2025-Q4 (92): Period state is explained before declaration commands.
- aeat app overview --period 2026-Q2 (82): Period state is explained before declaration commands.
- aeat app overview --period 2026-Q1 (76): Period state is explained before declaration commands.

### Human Review Gate Risks

- aeat app declaration review --period 2025-Q4 --modelo 303 --format table (136): Human review is required before approval.
- aeat app declaration review --period 2026-Q2 --modelo 303 --format table (121): Human review is required before approval.
- aeat app declaration review --period 2026-Q1 --modelo 303 --format table (109): Human review is required before approval.
- aeat app declaration calculate --period 2025-Q4 --modelo 303 (65): Calculation is explicit and period-scoped.
- aeat app declaration calculate --period 2026-Q2 --modelo 303 (61): Calculation is explicit and period-scoped.
- aeat app declaration approve --period 2026-Q1 --modelo 303 --reason reviewed-against-ledger (48): Human approval gates validation.

### Amend Flag Safety

- aeat app declaration calculate --period 2026-Q1 --modelo 303 --amend --id 3031234567890 (29): Corrective declaration work uses --amend --id and keeps legal layering under audit.
- aeat app declaration calculate --period 2025-Q4 --modelo 303 --amend --id 3031234567890 (27): Corrective declaration work uses --amend --id and keeps legal layering under audit.
- aeat app declaration calculate --period 2026-Q2 --modelo 303 --amend --id 3031234567890 (21): Corrective declaration work uses --amend --id and keeps legal layering under audit.

### Export Reliability

- aeat app declaration preview --period 2026-Q1 --modelo 303 --format pdf (48): Preview PDF is not treated as the filing artifact.
- aeat app declaration verify --period 2026-Q1 --modelo 303 --format json --output ./exports/2026-Q1-verify.json (48): Local verification runs before manual upload.
- aeat app declaration preview --period 2025-Q4 --modelo 303 --format pdf (47): Preview PDF is not treated as the filing artifact.
- aeat app declaration verify --period 2025-Q4 --modelo 303 --format json --output ./exports/2025-Q4-verify.json (47): Local verification runs before manual upload.
- aeat app declaration validate --period 2025-Q4 --modelo 303 --format json --output ./exports/2025-Q4-validation.json (45): Validation report gives repair data without claiming export readiness.
- aeat app declaration preview --period 2026-Q2 --modelo 303 --format pdf (44): Preview PDF is not treated as the filing artifact.

### Suggested CLI Additions

- No material signal in this run set.

## Sample Generated Tape

- `aeat app overview --calendar --from 2025-10-01 --to 2026-07-20`
- `aeat app overview --period 2026-Q2`
- `aeat app ledger import ./downloads/n26-2026-Q2.csv --provider n26 --dry-run`
- `aeat app ledger import ./downloads/n26-2026-Q2.csv --provider n26`
- `aeat app ledger import ./downloads/n26-2026-Q2.csv --provider n26 --verify --original ./downloads/n26-2026-Q2.pdf`
- `aeat app ledger list --filter status=pending --filter period=2026-Q2`
- `aeat app ledger show --id row_8_1`
- `aeat app ledger edit --id row_8_1 --set category=software --set business.share=1.0 --set reference=invoice-8 --reason invoice`
- `aeat app invoice import ./invoices/issued-2026-Q2.csv --kind issued --dry-run`
- `aeat app invoice import ./invoices/received-2026-Q2.csv --kind received --dry-run`
- `aeat app invoice list --filter status=pending --filter kind=received`
- `aeat app invoice show --id inv_8_1`
- `aeat app invoice edit --id inv_8_1 --set base=120.00 --set iva.rate=21 --set iva.amount=25.20 --set payment.id=row_8_1 --reason invoice-review`
- `aeat app invoice edit --id inv_8_2 --set iva.category=general --set retention.rate=15 --reason metadata-gap`
- `aeat app invoice match --period 2026-Q2`
- `aeat app declaration calculate --period 2026-Q2 --modelo 303`
- `aeat app declaration review --period 2026-Q2 --modelo 303 --format table`
- `aeat app declaration edit --period 2026-Q2 --modelo 303 --set casilla.71=1200.00 --reason manual-check`
- `aeat app declaration review --period 2026-Q2 --modelo 303 --format table`
- `aeat app declaration status --filter status=pending --period 2026-Q2 --modelo 303`
- `aeat app declaration validate --period 2026-Q2 --modelo 303 --format json --output ./exports/2026-Q2-validation.json`
