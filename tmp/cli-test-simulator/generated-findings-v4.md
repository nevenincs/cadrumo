# Kent/N26 CLI v4 audit findings

Seed: `kent-n26-v4`
Runs: `250`
Generated: `2026-05-02T22:40:14.347Z`

Kent is an autonomo who uses N26 and can download invoices, but does not know AEAT obligations or the CLI shape.

## Metrics

| Metric | Value |
| --- | --- |
| Completion Rate | 57% |
| Pending Review Rate | 43% |
| Commands To Success | 29.8 |
| Warning Count | 4.6 |
| Error Count | 0.0 |
| Command Guess Distance | v4 rerun |
| Record Completeness | 57% |
| Human Review Gate | tracked |
| Tax-Safety Risk | 0% |

## Findings

### Top Failed Command Guesses

- aeat setup auth configure --provider clave_permanente (63): Clave Permanente should remain research-only until implemented.

### Setup And Profile Friction

- aeat setup auth status (180): Auth state must be inspectable without changing it.
- aeat setup auth configure --provider clave_movil (180): Auth configuration names a supported provider.
- aeat setup auth login (180): Authentication is an actual login step.
- aeat setup auth whoami (180): Identity is exposed through auth/profile, not account.
- aeat setup profile list-keys (180): Profile keys must be discoverable.
- aeat setup profile set tax.id 12345678Z (180): Profile edits use schema-backed keys.

### Ledger Record Gaps

- aeat app ledger import ./downloads/n26-2026-Q2.csv --provider n26 --dry-run (92): Statement import is tested first.
- aeat app ledger import ./downloads/n26-2026-Q2.csv --provider n26 (92): Transaction records are imported into ledger.
- aeat app ledger list --filter status=pending --filter period=2026-Q2 (92): Manual ledger review is visible through status filters.
- aeat app ledger import ./downloads/n26-2026-Q1.csv --provider n26 --dry-run (81): Statement import is tested first.
- aeat app ledger import ./downloads/n26-2026-Q1.csv --provider n26 (81): Transaction records are imported into ledger.
- aeat app ledger list --filter status=pending --filter period=2026-Q1 (81): Manual ledger review is visible through status filters.

### Invoice Enrichment Gaps

- aeat app invoice list --filter status=pending --filter kind=received (250): Missing invoice metadata is visible.
- aeat app invoice import ./invoices/issued-2026-Q2.csv --kind issued --dry-run (92): Issued invoices stay under singular invoice.
- aeat app invoice import ./invoices/received-2026-Q2.csv --kind received --dry-run (92): Received invoices stay under singular invoice.
- aeat app invoice match --period 2026-Q2 (92): Invoice matching checks payments and ledger references.
- aeat app invoice import ./invoices/issued-2026-Q1.csv --kind issued --dry-run (81): Issued invoices stay under singular invoice.
- aeat app invoice import ./invoices/received-2026-Q1.csv --kind received --dry-run (81): Received invoices stay under singular invoice.

### Overview And Period Discovery

- aeat app overview --calendar --from 2025-10-01 --to 2026-07-20 (250): Overview handles filing discovery without a separate calendar command.
- aeat app overview --period 2026-Q2 (92): Period state is explained before declaration commands.
- aeat app overview --period 2026-Q1 (81): Period state is explained before declaration commands.
- aeat app overview --period 2025-Q4 (77): Period state is explained before declaration commands.

### Human Review Gate Risks

- aeat app declaration review --period 2026-Q2 --modelo 303 --format table (124): Human review is required before approval.
- aeat app declaration review --period 2026-Q1 --modelo 303 --format table (121): Human review is required before approval.
- aeat app declaration review --period 2025-Q4 --modelo 303 --format table (109): Human review is required before approval.
- aeat app declaration calculate --period 2026-Q2 --modelo 303 (73): Calculation is explicit and period-scoped.
- aeat app declaration calculate --period 2026-Q1 --modelo 303 (65): Calculation is explicit and period-scoped.
- aeat app declaration calculate --period 2025-Q4 --modelo 303 (65): Calculation is explicit and period-scoped.

### Amendment Safety

- aeat app declaration amendment create --period 2026-Q2 --modelo 303 --id 3031234567890 --csv-code CSV123 --reason changed-records (19): Corrective filing uses amendment grammar and keeps legal layering under audit.
- aeat app declaration amendment create --period 2026-Q1 --modelo 303 --id 3031234567890 --csv-code CSV123 --reason changed-records (16): Corrective filing uses amendment grammar and keeps legal layering under audit.
- aeat app declaration amendment create --period 2025-Q4 --modelo 303 --id 3031234567890 --csv-code CSV123 --reason changed-records (12): Corrective filing uses amendment grammar and keeps legal layering under audit.

### Export Reliability

- aeat app declaration preview --period 2026-Q2 --modelo 303 --format pdf (54): Preview PDF is not treated as the filing artifact.
- aeat app declaration verify --export ./exports/2026-Q2 (54): Local verification runs before manual upload.
- aeat app declaration preview --period 2025-Q4 --modelo 303 --format pdf (46): Preview PDF is not treated as the filing artifact.
- aeat app declaration verify --export ./exports/2025-Q4 (46): Local verification runs before manual upload.
- aeat app declaration validate --period 2026-Q2 --modelo 303 (43): Validation passes before export.
- aeat app declaration export --period 2026-Q2 --modelo 303 --format boe --output ./exports/2026-Q2 (43): Local AEAT-compatible export is generated.

### Suggested CLI Additions

- No material signal in this run set.

## Sample Generated Tape

- `aeat setup auth configure --provider clave_permanente`
- `aeat setup auth status`
- `aeat setup auth configure --provider clave_movil`
- `aeat setup auth login`
- `aeat setup auth whoami`
- `aeat setup profile list-keys`
- `aeat setup profile set tax.id 12345678Z`
- `aeat setup profile set tax.name Kent`
- `aeat setup profile set address.postcode 28013`
- `aeat setup profile validate`
- `aeat app overview --calendar --from 2025-10-01 --to 2026-07-20`
- `aeat app overview --period 2026-Q2`
- `aeat app ledger import ./downloads/n26-invoices.pdf --provider n26 --dry-run`
- `aeat app ledger import ./downloads/n26-2026-Q2.csv --provider n26 --dry-run`
- `aeat app ledger import ./downloads/n26-2026-Q2.csv --provider n26`
- `aeat app ledger import verify import_2 --file ./downloads/n26-2026-Q2.pdf`
- `aeat app ledger list --filter status=pending --filter period=2026-Q2`
- `aeat app ledger show --id row_2_1`
- `aeat app ledger edit --id row_2_1 --set category=software --set business_pct=100 --set reference=invoice-2 --reason invoice`
- `aeat app ledger split --id row_2_2 --business 45.00 --personal 20.00 --reason mixed-card-payment`
- `aeat app ledger exclude --id row_2_3 --reason private-expense`
- `aeat app ledger restore --id row_2_3 --reason invoice-found`
- `aeat app invoice import ./invoices/issued-2026-Q2.csv --kind issued --dry-run`
- `aeat app invoice import ./invoices/received-2026-Q2.csv --kind received --dry-run`
- `aeat app invoice list --filter status=pending --filter kind=received`
- `aeat app invoice show --id inv_2_1`
- `aeat app invoice edit --id inv_2_1 --set base=120.00 --set iva.rate=21 --set iva.amount=25.20 --set payment.id=row_2_1 --reason invoice-review`
- `aeat app invoice edit --id inv_2_2 --set iva.category=general --set retention.rate=15 --reason metadata-gap`
- `aeat app invoice match --period 2026-Q2`
- `aeat app declaration amendment create --period 2026-Q2 --modelo 303 --id 3031234567890 --csv-code CSV123 --reason changed-records`
- `aeat app declaration calculate --period 2026-Q2 --modelo 303 --amendment amend_001`
- `aeat app declaration review --period 2026-Q2 --modelo 303 --format table`
- `aeat app declaration status --filter status=pending --period 2026-Q2 --modelo 303`
- `aeat app declaration validate --period 2026-Q2 --modelo 303 --format json --output ./exports/2026-Q2-validation.json`
