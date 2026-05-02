# AEAT CLI v5 design wireframe

Status: review candidate, not approved for implementation.

## Design Principles

- Separate prerequisites from tax work: `setup` configures, `app` operates.
- Use singular app domains: `overview`, `ledger`, `invoice`, `declaration`.
- Make import an action, not a nested command domain.
- Put diagnostics on the action with flags when they do not produce a distinct
  user object.
- Use read-only inspection before mutation: `list`, then `show`, then `edit`.
- Make every mutation auditable with a required reason where the change affects
  filing values.
- Use record fields for references, comments, document paths, payment links,
  and invoice links.
- Do not expose backend/developer terminology in user command names.
- Do not introduce emotional commands or panic/status shortcuts.
- Keep export local. Do not introduce live submission.

## Root

```text
aeat setup
  Configure authentication, profile data, and local readiness.

aeat app
  Work through overview, ledger, invoice, and declaration workflows.
```

## Setup

```text
aeat setup auth providers
aeat setup auth configure --provider certificate --file PATH
aeat setup auth configure --provider clave_movil
aeat setup auth login
aeat setup auth status
aeat setup auth whoami
aeat setup auth logout

aeat setup profile create NAME
aeat setup profile use NAME
aeat setup profile show
aeat setup profile list-keys
aeat setup profile get KEY
aeat setup profile set KEY VALUE
aeat setup profile unset KEY
aeat setup profile validate
aeat setup profile edit
```

## App

```text
aeat app overview
aeat app ledger
aeat app invoice
aeat app declaration
```

## Ledger

```text
aeat app ledger import PATH --provider n26 --dry-run
  Validate a transaction file before saving records.

aeat app ledger import PATH --provider n26 --verify --original PATH --verbose
  Import records and run source-file, gap, duplicate, parser, and verbose diagnostics.

aeat app ledger list --filter status=pending --filter period=2026-Q1
  List records or diagnostics using cohesive filters.

aeat app ledger show --id row_1042 --verbose
  Show one row, provenance, edit history, document links, and skip state.

aeat app ledger edit --id row_1042 --set category=software --set business.share=1.0 --reason invoice
  Edit schema-backed fields.

aeat app ledger edit --id row_1051 --skip true --reason private-expense
  Skip a row without deleting it.

aeat app ledger edit --id row_1051 --skip false --reason invoice-found
  Return a skipped row to review.

aeat app ledger split --id row_1050 --business 0.45 --personal 0.55 --reason mixed-card-payment
  Split one source row into normalized shares that add to 1.0.

aeat app ledger split --id row_1050 --clear --reason corrected-single-use
  Clear split metadata and return to the source row.
```

## Invoice

```text
aeat app invoice import PATH --kind issued --dry-run
aeat app invoice import PATH --kind received --dry-run
aeat app invoice list --filter status=pending --filter kind=received
aeat app invoice show --id inv_2041 --verbose
aeat app invoice edit --id inv_2041 --set base=120.00 --set iva.rate=21 --set iva.amount=25.20 --set iva.category=general --set retention.rate=15 --set payment.id=row_1042 --reason invoice-review
aeat app invoice match --period 2026-Q1
```

Invoice remains a separate tax-document domain. Ledger evidence files stay as
ledger record fields.

## Declaration

```text
aeat app declaration calculate --period 2026-Q1 --modelo 303
  Calculate and print a compact summary table, blocker counts, warnings, and next action.

aeat app declaration review --period 2026-Q1 --modelo 303 --format table
  Review values, assumptions, warnings, and changed inputs.

aeat app declaration status --filter status=pending --period 2026-Q1 --modelo 303
  Show unresolved work.

aeat app declaration edit --period 2026-Q1 --modelo 303 --set casilla.71=1200.00 --reason manual-check
  Record a manual change and reset approval.

aeat app declaration approve --period 2026-Q1 --modelo 303 --reason reviewed-against-ledger
  Approve the reviewed declaration state.

aeat app declaration validate --period 2026-Q1 --modelo 303
  Validate only after approval.

aeat app declaration validate --period 2026-Q1 --modelo 303 --format json --output PATH
  Write repair data when unresolved work remains.

aeat app declaration preview --period 2026-Q1 --modelo 303 --format pdf
  Create a non-filing preview.

aeat app declaration export --period 2026-Q1 --modelo 303 --format boe --output PATH
  Write a local AEAT-compatible artifact.

aeat app declaration verify --period 2026-Q1 --modelo 303 --format json --output PATH
  Write verification audit output.
```

## Amended Declaration

```text
aeat app declaration calculate --period 2026-Q1 --modelo 303 --amend --id JUSTIFICANTE_ID
aeat app declaration review --period 2026-Q1 --modelo 303 --amend --id JUSTIFICANTE_ID --format table
aeat app declaration approve --period 2026-Q1 --modelo 303 --amend --id JUSTIFICANTE_ID --reason REASON
aeat app declaration validate --period 2026-Q1 --modelo 303 --amend --id JUSTIFICANTE_ID
aeat app declaration export --period 2026-Q1 --modelo 303 --amend --id JUSTIFICANTE_ID --format boe --output PATH
```

There is no corrective-filing noun, no amendment subcommand, no `--amendment`,
and no separate CSV-code identity. The id is the AEAT justificante id.

## Backend Audit Gates

- Profile key registry, validation, and storage.
- Ledger row schema, skip state, split metadata, edit history, filters, and
  lifecycle.
- Import verification output for original-file, gap, duplicate, and parser
  diagnostics.
- Invoice retention, IVA category, document path, and payment linkage.
- Declaration calculate output contract.
- Export and verify output contracts.
- AEAT justificante id behavior for amended declarations.
