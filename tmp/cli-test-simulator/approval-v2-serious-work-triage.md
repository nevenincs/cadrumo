# AEAT CLI Approval Notes Serious-Work Triage

Status: recovered-note triage, not approved.
Generated: 2026-05-02.

Primary input: `approval-decisions-v2-recovered-2026-05-02.json`.

Every recovered note is treated as blocking design input. The v2 approval
surface was not approved; it contained terms and command shapes that the notes
explicitly reopened or rejected.

## Section Triage

| Section | Status | Required Action |
| --- | --- | --- |
| Root Boundary | Accepted | Keep `aeat setup` and `aeat app`; replace bare `help` with `--help`; rewrite app description as programs used to prepare, declare, and verify tax obligations. |
| Setup Start | Accepted | Keep `aeat setup init`; make setup configurable by `auth`, `account`, `profile`, and storage subcommands; model `init` as a fresh complete-auth path. |
| Setup Readiness | Reopened | Keep `setup status` as read-only state; hold `setup verify` out of approval until its behavior is researched. |
| Active Profile | Accepted | The active setup profile is the normal identity context for app commands; global `--profile` and `--workspace` are not the routine model. |
| App Container | Reopened | Use singular nouns and a reduced domain map; do not expose `receipts`, `calendar`, or `sessions` as approved app domains. |
| Ledger Name | Backend audit | Define ledger data keeping before approving commands: stable row references, categories, business classification, VAT/rate metadata, proportionality metadata, source-document references, model associations, and edit history. |
| Statement Imports | Reopened | Compare the old `ledger statements import` shape against `ledger import PATH --statement {provider|auto}`; v3 tests the latter. |
| Transactions | Backend audit | Replace over-nested transaction commands with `ledger list`, `ledger search`, and `ledger edit` unless backend audit proves another shape is better. |
| Documents | Rejected old shape | Receipts are ledger row metadata and part of sanitization, not a standalone app domain. |
| Calendar | Rejected old shape | Replace standalone `calendar` with `overview --calendar`. |
| Declaration Name | Accepted | Keep `declaration` as the tax calculation/export domain. |
| Calculation | Backend audit | Add human review gates: calculate, review, edit, approve. Validation/export must refuse unreviewed or stale calculations. |
| Validate Export | Conditional | Words are acceptable only after calculation/review gates and output-format behavior are explicit. |
| Rectification | Backend audit | Replace `--previous` with `--id` requiring the justificante number or audited AEAT equivalent. |
| Blocked Output | Rejected | Remove `blocker` and `blockers`; use pending review output and validation reports instead. |
| Evidence | Rejected | Remove `evidence` and `TX`; use `row`, `source document`, `supporting record`, and `filing package` candidates. |
| Sessions | Rejected | Remove session/workspace save-load for now; interrupted work is profile-scoped persistent app data until storage design is audited. |
| Safety | Accepted | Use `--help` and `--dry-run`; do not present bare `help` as the approved UX. |
| ADR Status | In progress | Record the ADR as nowhere near finished; no implementation approval. |

## V3 Wireframe Under Review

```text
aeat --help
aeat setup --help
aeat app --help
```

```text
aeat setup init
  Start a fresh complete-auth setup flow.

aeat setup auth import PATH --dry-run
  Validate authentication material before saving it.

aeat setup account show
  Show the AEAT account identity known to setup.

aeat setup profile create NAME --activity design
  Create a taxpayer profile.

aeat setup profile use NAME
  Select the active profile for app commands.

aeat setup status
  Show configured state without claiming full readiness verification.
```

```text
aeat app overview
  Show preparation state across profile, ledger, invoice, declaration, and imported AEAT history.

aeat app overview --calendar --from DATE --to DATE
  Show due dates and period state inside the overview flow.
```

```text
aeat app ledger import PATH --statement auto --dry-run
aeat app ledger import PATH --statement n26
  Validate and import bank statement rows.

aeat app ledger list --period PERIOD
  List ledger rows with stable row references.

aeat app ledger search --query TEXT --period PERIOD
aeat app ledger search --description TEXT --category CATEGORY --from DATE --to DATE
aeat app ledger search --regex PATTERN
  Find ledger rows. Regex is a backend-audit candidate.

aeat app ledger edit --row ROW_ID --category CATEGORY --business PERCENT --reason REASON
  Edit tax metadata for a ledger row.

aeat app ledger split --row ROW_ID --business AMOUNT --personal AMOUNT --reason REASON
  Split mixed spending.

aeat app ledger receipt attach --row ROW_ID --file PATH --dry-run
aeat app ledger receipt attach --row ROW_ID --file PATH --reason REASON
  Attach receipt/source document metadata to a ledger row.
```

```text
aeat app invoice import PATH --kind issued --dry-run
aeat app invoice import PATH --kind received --dry-run
aeat app invoice list --kind issued --period PERIOD
aeat app invoice match --period PERIOD
  Import, list, and match issued or received tax invoices.
```

```text
aeat app declaration calculate --period PERIOD --modelo MODELO
  Calculate values from reviewed ledger rows, invoice records, profile facts, filing history, and period state.

aeat app declaration review --period PERIOD --modelo MODELO --format table
  Present human-reviewable values, assumptions, warnings, and pending decisions.

aeat app declaration edit --period PERIOD --modelo MODELO --field FIELD --value VALUE --reason REASON
  Record a manual calculation value change.

aeat app declaration approve --period PERIOD --modelo MODELO --reason REASON
  Mark the reviewed calculation as approved by a human.

aeat app declaration validate --period PERIOD --modelo MODELO
  Validate only after human approval.

aeat app declaration preview --period PERIOD --modelo MODELO --format pdf
  Create a draft PDF preview where supported.

aeat app declaration export --period PERIOD --modelo MODELO --format boe --output PATH
  Export a local AEAT-compatible file where supported.

aeat app declaration verify --export PATH
  Verify the local export before manual AEAT upload.

aeat app declaration correct --period PERIOD --modelo MODELO --id JUSTIFICANTE --reason REASON
  Prepare a correction linked to the prior filing id.
```

## Explicitly Removed From Canonical V3

```text
aeat help
aeat app help
aeat setup verify
aeat app receipts
aeat app calendar
aeat app sessions
aeat app ledger statements import
aeat app ledger transactions categorize TX
aeat app declaration blockers export
aeat app declaration evidence export
aeat app declaration calculate --previous JUSTIFICANTE
```

`setup verify` is held for research rather than permanently rejected.
