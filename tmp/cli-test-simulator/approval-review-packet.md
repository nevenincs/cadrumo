# AEAT CLI v5 approval review packet

Status: review candidate, not approved for implementation.

## What Changed Since V4

| V4 issue | V5 correction |
| --- | --- |
| Import was treated as a command domain. | Import is one action: `ledger import PATH --provider PROVIDER`. |
| Import verification, gaps, duplicates, exclude, and restore were subcommands. | Verification is `--verify`; skip decisions are `ledger edit --skip true|false`. |
| Ledger review used exclude/restore. | Skip and unskip are auditable edits. |
| Split examples used amounts. | Split examples use normalized shares that add to `1.0`. |
| Corrective filing used an amendment noun and CSV-code identity. | Declaration commands use `--amend --id JUSTIFICANTE_ID`. |
| Verify accepted an export flag. | Export uses `--output`; verify uses `--format json --output`. |
| Calculate output was ambiguous. | Bare calculate prints a summary, blockers, warnings, and next action. |
| Safety missed verbose diagnostics. | `--verbose` is a global diagnostic requirement. |

## Sections For Review

1. Root boundary
2. Setup auth
3. Setup profile
4. App domains
5. Ledger backend contract
6. Ledger import action
7. Ledger inspection
8. Ledger edit, skip, split
9. Record files
10. Invoice backend contract
11. Invoice review
12. Overview and resume
13. Declaration calculate
14. Declaration review gates
15. Declaration export and verify
16. Amend flag
17. Safety and status

## Canonical V5 Surface

```text
aeat setup ...
aeat app overview ...
aeat app ledger import PATH --provider PROVIDER [--dry-run] [--verify] [--original PATH] [--verbose]
aeat app ledger list --filter KEY=VALUE
aeat app ledger show --id ROW --verbose
aeat app ledger edit --id ROW --set COLUMN=VALUE --reason REASON
aeat app ledger edit --id ROW --skip true|false --reason REASON
aeat app ledger split --id ROW --business SHARE --personal SHARE --reason REASON
aeat app ledger split --id ROW --clear --reason REASON
aeat app invoice import PATH --kind issued|received
aeat app invoice list --filter KEY=VALUE
aeat app invoice show --id INVOICE --verbose
aeat app invoice edit --id INVOICE --set COLUMN=VALUE --reason REASON
aeat app invoice match --period PERIOD
aeat app declaration calculate --period PERIOD --modelo MODELO
aeat app declaration review --period PERIOD --modelo MODELO --format table
aeat app declaration status --filter status=pending --period PERIOD --modelo MODELO
aeat app declaration edit --period PERIOD --modelo MODELO --set COLUMN=VALUE --reason REASON
aeat app declaration approve --period PERIOD --modelo MODELO --reason REASON
aeat app declaration validate --period PERIOD --modelo MODELO
aeat app declaration export --period PERIOD --modelo MODELO --format boe --output PATH
aeat app declaration verify --period PERIOD --modelo MODELO --format json --output PATH
aeat app declaration calculate --period PERIOD --modelo MODELO --amend --id JUSTIFICANTE_ID
```

## Rejected Forms To Watch For

```text
aeat app ledger import verify ...
aeat app ledger import gaps ...
aeat app ledger import duplicates ...
aeat app ledger import exclude ...
aeat app ledger import restore ...
aeat app ledger exclude ...
aeat app ledger restore ...
aeat app declaration amendment create ...
aeat app declaration verify --export PATH
--amendment
--csv-code
```

## Required Tape Coverage

- Invalid file import.
- Incomplete import and source PDF verification.
- Duplicate import diagnostics.
- Wrong-account import and skip/unskip revision.
- Manual categorization and document path linking.
- Split, clear, and corrected split.
- Invoice import, metadata enrichment, retention, IVA category, and matching.
- Multi-period backlog and late period review.
- Declaration calculate summary output.
- Export refusal until review and approval gates pass.
- Local export with explicit output path.
- Verification JSON output.
- Amended declaration with AEAT justificante id.

## Backend Work Still Required

- Ledger schema cannot be manually approved.
- Import verification must be backend-owned.
- Skip state must be persisted and reflected in calculations.
- Split metadata must preserve source transactions and allow clearing.
- Invoice retention and IVA category need backend audit.
- Declaration calculate output needs a backend contract.
- Export and verify output need a backend contract.
- AEAT justificante id behavior must be confirmed per modelo.
