---
tags:
  - '#reference'
  - '#aeat-cli-redesign'
date: '2026-05-02'
modified: '2026-05-02'
related:
  - "[[2026-05-02-aeat-cli-redesign-research]]"
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
---



# `aeat-cli-redesign` reference: `user-cli-redesign-review-packet-v6`

## Packet Status

This packet is an in-progress recovered-comment review packet for the AEAT user
CLI redesign. It is not an accepted ADR, does not authorize implementation, and
does not supersede prior no-live-submit safety work.

The v6 packet supersedes the previous review surface because the previous
surface still contained rejected import subcommands, exclude/restore verbs,
ambiguous calculate output, `verify --export`, and an extra amendment command
noun.

## Accepted Anchors

- First-contact root: `aeat setup` and `aeat app`.
- Help grammar: `--help`, not bare help.
- Setup configures prerequisites.
- App performs tax preparation and declaration work.
- Active setup profile is the normal app identity context.
- App domain nouns are singular.
- Domain noun: `declaration`.
- Safety rule: local export only, no live submission command.
- Diagnostic rule: support `--verbose` on state-sensitive workflows.

## Reworked Or Rejected Areas

| Area | Status | Required Handling |
| --- | --- | --- |
| Authentication | Accepted anchor | Configure provider, log in, show status, show whoami, and logout. Do not model auth as file import. |
| Profile | Accepted anchor | Use schema-backed profile keys with keys/list/get/set/unset/validate. |
| Account noun | Rejected | Identity belongs to auth/profile status. |
| App domains | Accepted anchor | Use `overview`, `ledger`, `invoice`, `declaration`. |
| Ledger schema | Backend audit | Backend must define record fields, skip state, split metadata, edit history, filters, and lifecycle. |
| Ledger import | Reworked | Use `ledger import PATH --provider PROVIDER`; verification is `--verify`, not an import subcommand. |
| Import diagnostics | Reworked | Gap, duplicate, original-file, and parser diagnostics are output from `ledger import ... --verify`. |
| Ledger review | Reworked | Use `review` and `edit` with `--filter`, `--set`, `--skip`, and split share values. |
| Ledger exclude/restore | Rejected | Use `ledger edit --skip true|false --reason REASON`. |
| Supporting files | Accepted anchor | Model review files, references, and comments as record fields. |
| Invoice schema | Backend audit | Define base, IVA, IVA category, retention, payment link, references, comments, lines, and history. |
| Declaration calculate | Reworked | Bare calculate prints a summary, blocker counts, warnings, and next action. |
| Declaration review | Accepted anchor | Use calculate/review/status/edit/approve before validation/export. |
| Declaration export | Reworked | Export requires `--output`; verify reads `--file` and has no export flag. |
| Corrective declaration | Reworked | Recalculate a new declaration draft after late or corrected records. |
| Work state | Rejected old shape | Resume through active profile state, overview, and status filters. |

## Current Candidate CLI Shape

```text
aeat
  setup
  app
```

```text
aeat setup
  init
  status
  auth
  profile

aeat app
  overview
  ledger
  invoice
  declaration
```

## Candidate Commands

| Command | Description |
| --- | --- |
| `aeat --help` | Shows global help and setup/app boundary. |
| `aeat setup --help` | Shows setup commands. |
| `aeat app --help` | Shows tax-work domains. |
| `aeat setup init` | Initializes local prerequisites and directs the user to auth/profile setup. |
| `aeat setup status` | Shows auth provider, login state, active profile, missing profile keys, and next setup action. |
| `aeat setup auth providers` | Lists implemented and research-only authentication providers. |
| `aeat setup auth configure --provider certificate --file PATH` | Configures certificate authentication. |
| `aeat setup auth configure --provider clave_movil` | Configures Clave Movil authentication. |
| `aeat setup auth login` | Starts the configured AEAT login flow. |
| `aeat setup auth status` | Shows provider and login state. |
| `aeat setup auth whoami` | Shows the authenticated identity when available. |
| `aeat setup auth logout` | Clears active authentication state. |
| `aeat setup init --name NAME` | Creates a taxpayer profile. |
| `aeat setup profile use NAME` | Selects the active profile. |
| `aeat setup profile show` | Shows current profile facts and validation state. |
| `aeat setup profile list-keys` | Lists editable keys, value types, requiredness, and descriptions. |
| `aeat setup profile get KEY` | Reads one profile value. |
| `aeat setup profile set KEY VALUE` | Sets one schema-backed profile value. |
| `aeat setup profile unset KEY` | Clears one optional profile value. |
| `aeat setup profile validate` | Validates profile completeness and consistency. |
| `aeat setup profile list` | Lists configured setup profiles. |
| `aeat app overview status` | Shows profile-scoped readiness, pending record counts, declaration state, and next action. |
| `aeat app overview status --calendar --from DATE --to DATE` | Shows period states across a date range. |
| `aeat app overview status --period PERIOD --verbose` | Explains local state, unresolved work, and next commands for one period. |
| `aeat app ledger import PATH --provider n26 --dry-run` | Validates a transaction file before saving records. |
| `aeat app ledger import PATH --provider n26 --verify --source PATH --verbose` | Imports records and runs original-file, gap, duplicate, parser, and verbose diagnostics. |
| `aeat app ledger review --filter status=pending --filter period=PERIOD` | Lists records needing review. |
| `aeat app ledger review --filter issue=duplicate --filter period=PERIOD` | Lists duplicate diagnostics produced by import verification. |
| `aeat app ledger review --id RECORD_ID --verbose` | Shows one ledger record, provenance, editable columns, document links, and skip state. |
| `aeat app ledger edit --id RECORD_ID --set COLUMN=VALUE --reason REASON` | Edits schema-backed ledger columns. |
| `aeat app ledger edit --id RECORD_ID --skip true --reason REASON` | Skips a row without deleting it. |
| `aeat app ledger edit --id RECORD_ID --skip false --reason REASON` | Returns a skipped row to review. |
| `aeat app ledger edit --id RECORD_ID --split business=SHARE --split personal=SHARE --reason REASON` | Splits mixed spending into share values that add to `1.0`. |
| `aeat app ledger edit --id RECORD_ID --split clear --reason REASON` | Clears split metadata and returns to the source row. |
| `aeat app invoice import PATH --kind issued --dry-run` | Validates invoice records issued by the taxpayer. |
| `aeat app invoice import PATH --kind received --dry-run` | Validates invoice records received from suppliers. |
| `aeat app invoice review --filter status=pending --filter kind=received` | Lists invoice records needing metadata review. |
| `aeat app invoice review --id INVOICE_ID --verbose` | Shows invoice metadata, lines, totals, payment linkage, references, and comments. |
| `aeat app invoice edit --id INVOICE_ID --set COLUMN=VALUE --reason REASON` | Edits invoice metadata. |
| `aeat app invoice match --period PERIOD` | Matches invoice records to payments and ledger records. |
| `aeat app declaration calculate --period PERIOD --modelo MODELO` | Calculates declaration values and prints summary output, blockers, warnings, and next action. |
| `aeat app declaration review --period PERIOD --modelo MODELO --format table` | Presents human-reviewable calculated values and assumptions. |
| `aeat app declaration status --filter status=pending --period PERIOD --modelo MODELO` | Shows unresolved declaration work. |
| `aeat app declaration edit --id draft_MODELO_PERIOD --set COLUMN=VALUE --reason REASON` | Records a manual calculation value change and resets approval. |
| `aeat app declaration approve --id draft_MODELO_PERIOD --by reviewer --reason REASON` | Marks reviewed values as approved by a human. |
| `aeat app declaration validate --id draft_MODELO_PERIOD` | Validates only after review approval. |
| `aeat app declaration validate --id draft_MODELO_PERIOD --format json --output PATH` | Saves a validation report when unresolved work remains. |
| `aeat app declaration preview --id draft_MODELO_PERIOD` | Creates a non-filing preview where supported. |
| `aeat app declaration export --id draft_MODELO_PERIOD --output PATH` | Exports a local AEAT-compatible file where supported. |
| `aeat app declaration verify --id DRAFT_ID --file PATH` | Verifies the exported file against the approved local draft. |
| `aeat app declaration calculate --period PERIOD --modelo MODELO` | Recalculates a new draft after late or corrected records. |
| `aeat app declaration review --period PERIOD --modelo MODELO --format table` | Reviews recalculated declaration values. |
| `aeat app declaration approve --id draft_MODELO_PERIOD --by reviewer --reason REASON` | Approves recalculated declaration state. |
| `aeat app declaration validate --id draft_MODELO_PERIOD` | Validates recalculated declaration state. |
| `aeat app declaration export --id draft_MODELO_PERIOD --output PATH` | Exports recalculated declaration output. |

## Candidate Data Fields

Ledger target fields:

- `id`
- `source.import.id`
- `source.transaction.id`
- `period`
- `date`
- `description`
- `amount`
- `direction`
- `status`
- `category`
- `business.share`
- `skip`
- `reference`
- `comments`
- `invoice.id`
- `document.path`
- `modelo`
- `review.history`
- `split.metadata`

Invoice target fields:

- `id`
- `kind`
- `status`
- `issue_date`
- `counterparty`
- `base`
- `iva.rate`
- `iva.amount`
- `iva.category`
- `retention.rate`
- `retention.amount`
- `payment.id`
- `document.path`
- `reference`
- `comments`
- `lines`
- `review.history`

## Removed From The Candidate Surface

- account as a setup command family
- auth as an import/validation shortcut
- import subcommands named `verify`, `gaps`, `duplicates`, `exclude`, or
  `restore`
- ledger `exclude` and `restore`
- supporting files as standalone attach commands
- declaration support bundles as a package command
- corrective declaration nouns and amendment subcommands
- separate CSV-code identity flags
- `declaration verify --export`
- one-off needs-review flags instead of `--filter status=pending`
- user-facing session/workspace save-load commands

## Tape Coverage Requirements

The simulator and tapes must exercise:

- Setup from unknown state using status, auth provider configuration, login, and
  profile validation.
- Profile key discovery, incorrect profile value revision, and validation.
- Invalid transaction file calls.
- Partial imports and missing date coverage through `--verify`.
- Original downloaded file verification against imported records.
- Duplicate imports and wrong-account imports.
- User decisions to skip and unskip ledger records.
- Manual ledger categorization, references, comments, and document-path fields.
- Mixed business/personal spending with split share values.
- Split clearing and reapplying corrected split metadata.
- Issued and received invoice import through singular `invoice`.
- Invoice enrichment for base, IVA, IVA category, retention, payment link,
  reference, comments, and document path.
- Overview discovery across filed, due, missing, late, and unknown periods.
- Explicit calculation output, review, status, manual edit, human approval,
  validation, preview, export, and verification.
- Multi-period forgetfulness.
- Missed deadline recovery.
- Stale calculations after data changes.
- Recalculated declaration flow after late or corrected records.
- Validation report output for unresolved work.
- Interruption and resume through profile-scoped persistent state.

## Open Approval Questions

- Which profile keys are required for first implementation?
- Which ledger fields already exist versus require migration?
- How should backend import verification persist gap, duplicate, parser, and
  original-file diagnostics?
- How should skip state affect declaration calculations?
- How should split metadata preserve source transactions and support clearing?
- Which invoice retention and IVA category fields must be implemented first?
- What exact declaration staleness rules must block validation and export?
- How should official AEAT correction modes and justificante identity rules be
  mapped after research?

No completion-rate score is valid until the v6 tapes are replayed.
