# Kent/N26 CLI v3 audit findings

Seed: `kent-n26-v3`
Runs: `250`
Generated: `2026-05-02T21:29:02.313Z`

Kent is an autonomo who uses N26 and can download invoices, but does not know AEAT obligations or the CLI shape.

## Metrics

| Metric | Value |
| --- | --- |
| Completion Rate | 51% |
| Pending Review Rate | 49% |
| Commands To Success | 25.1 |
| Warning Count | 3.9 |
| Error Count | 0.0 |
| Command Guess Distance | v3 rerun |
| Source Completeness | 51% |
| Human Review Gate | tracked |
| Tax-Safety Risk | 0% |

## Findings

### Top Failed Command Guesses

- aeat setup verify (60): Do not guide users to verify until readiness semantics are researched.

### Common Workflow Friction

- aeat setup status (370): Setup state must be inspectable without mutation.
- aeat setup auth import ./setup/token.json --dry-run (185): Auth ingestion can be tested safely.
- aeat setup init (185): Setup is repaired using the approved init word.
- aeat setup profile create autonomo-2026 --activity design (185): Profile is explicit setup state.
- aeat setup profile use autonomo-2026 (185): Active profile replaces normal --profile flags.
- aeat app ledger search --needs-review --period 2026-Q1 (93): Manual ledger row work is visible.

### Ledger Data Keeping Gaps

- aeat app ledger import ./downloads/n26-2026-Q1.csv --statement n26 --dry-run (93): Statement import is tested first.
- aeat app ledger import ./downloads/n26-2026-Q1.csv --statement n26 (93): Statement rows are imported into ledger.
- aeat app ledger import ./downloads/n26-2026-Q2.csv --statement n26 --dry-run (91): Statement import is tested first.
- aeat app ledger import ./downloads/n26-2026-Q2.csv --statement n26 (91): Statement rows are imported into ledger.
- aeat app ledger import ./downloads/n26-2025-Q4.csv --statement n26 --dry-run (66): Statement import is tested first.
- aeat app ledger import ./downloads/n26-2025-Q4.csv --statement n26 (66): Statement rows are imported into ledger.

### Source Document Gaps

- aeat app invoice import ./invoices/issued-2026-Q1.csv --kind issued --dry-run (93): Issued invoices are separate from receipt metadata.
- aeat app invoice import ./invoices/received-2026-Q1.csv --kind received --dry-run (93): Received tax invoices are separate from receipt metadata.
- aeat app invoice match --period 2026-Q1 (93): Invoice matching checks invoices and ledger references.
- aeat app invoice import ./invoices/issued-2026-Q2.csv --kind issued --dry-run (91): Issued invoices are separate from receipt metadata.
- aeat app invoice import ./invoices/received-2026-Q2.csv --kind received --dry-run (91): Received tax invoices are separate from receipt metadata.
- aeat app invoice match --period 2026-Q2 (91): Invoice matching checks invoices and ledger references.

### Overview And Filing Discovery

- aeat app overview --calendar --from 2025-10-01 --to 2026-07-20 (250): Overview replaces standalone calendar/status for due and missing periods.
- aeat app overview --period 2026-Q1 (93): Period state is explained before filing commands.
- aeat app overview --period 2026-Q2 (91): Period state is explained before filing commands.
- aeat app overview --period 2025-Q4 (66): Period state is explained before filing commands.

### Human Review Gate Risks

- aeat app declaration review --period 2026-Q1 --modelo 303 --format table (126): Human review is required before approval.
- aeat app declaration review --period 2026-Q2 --modelo 303 --format table (125): Human review is required before approval.
- aeat app declaration review --period 2025-Q4 --modelo 303 --format table (98): Human review is required before approval.
- aeat app declaration calculate --period 2026-Q2 --modelo 303 (77): Calculation is explicit.
- aeat app declaration calculate --period 2026-Q1 --modelo 303 (72): Calculation is explicit.
- aeat app declaration calculate --period 2025-Q4 --modelo 303 (58): Calculation is explicit.

### Correction Safety

- aeat app declaration correct --period 2026-Q1 --modelo 303 --id 3031234567890 --reason amount (21): Correction uses --id for prior filing identity.
- aeat app declaration correct --period 2026-Q2 --modelo 303 --id 3031234567890 --reason amount (14): Correction uses --id for prior filing identity.
- aeat app declaration correct --period 2025-Q4 --modelo 303 --id 3031234567890 --reason amount (8): Correction uses --id for prior filing identity.

### Export Reliability

- aeat app declaration preview --period 2026-Q2 --modelo 303 --format pdf (56): Preview PDF is not treated as the filing artifact.
- aeat app declaration verify --export ./exports/2026-Q2 (56): Local verification runs before manual upload.
- aeat app declaration validate --period 2026-Q1 --modelo 303 --format json --output ./exports/2026-Q1-validation.json (51): Validation report gives repair data.
- aeat app declaration validate --period 2026-Q2 --modelo 303 (46): Validation passes before export.
- aeat app declaration export --period 2026-Q2 --modelo 303 --format boe --output ./exports/2026-Q2 (46): Local AEAT-compatible export is generated.
- aeat app declaration preview --period 2026-Q1 --modelo 303 --format pdf (42): Preview PDF is not treated as the filing artifact.

### Suggested CLI Additions

- aeat app declaration package export --period 2026-Q1 --modelo 303 --include-source --output ./exports/2026-Q1-package (93): Filing package keeps support artifacts attached to the declaration.
- aeat app declaration package export --period 2026-Q2 --modelo 303 --include-source --output ./exports/2026-Q2-package (91): Filing package keeps support artifacts attached to the declaration.
- aeat app declaration package export --period 2025-Q4 --modelo 303 --include-source --output ./exports/2025-Q4-package (66): Filing package keeps support artifacts attached to the declaration.

## Sample Generated Tape

- `aeat setup status`
- `aeat setup auth import ./setup/token.json --dry-run`
- `aeat setup init`
- `aeat setup profile create autonomo-2026 --activity design`
- `aeat setup profile use autonomo-2026`
- `aeat setup status`
- `aeat app overview --calendar --from 2025-10-01 --to 2026-07-20`
- `aeat app overview --period 2026-Q1`
- `aeat app ledger import ./downloads/n26-2026-Q1.csv --statement n26 --dry-run`
- `aeat app ledger import ./downloads/n26-2026-Q1.csv --statement n26`
- `aeat app ledger import verify import_0 --source ./downloads/n26-2026-Q1.pdf`
- `aeat app ledger search --needs-review --period 2026-Q1`
- `aeat app ledger edit --row row_0_1 --category software --business 100 --reason invoice`
- `aeat app ledger exclude --row row_0_3 --reason private-expense`
- `aeat app ledger restore --row row_0_3 --reason invoice-found`
- `aeat app invoice import ./invoices/issued-2026-Q1.csv --kind issued --dry-run`
- `aeat app invoice import ./invoices/received-2026-Q1.csv --kind received --dry-run`
- `aeat app ledger receipt list --missing --period 2026-Q1`
- `aeat app invoice match --period 2026-Q1`
- `aeat app declaration calculate --period 2026-Q1 --modelo 303`
- `aeat app declaration review --period 2026-Q1 --modelo 303 --format table`
- `aeat app declaration review --period 2026-Q1 --modelo 303 --pending --format table`
- `aeat app declaration validate --period 2026-Q1 --modelo 303 --format json --output ./exports/2026-Q1-validation.json`
- `aeat app declaration package export --period 2026-Q1 --modelo 303 --include-source --output ./exports/2026-Q1-package`
