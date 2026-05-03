# AEAT CLI v6 approval review packet

Status: review candidate, not approved for implementation.

## What Changed Since V4

| V4 issue | V6 correction |
| --- | --- |
| Import was treated as a command domain. | Import is one action: `ledger import PATH --provider PROVIDER`. |
| Import verification, gaps, duplicates, exclude, and restore were subcommands. | Verification is `--verify`; skip decisions are `ledger edit --skip true|false`. |
| Ledger review used exclude/restore. | Skip and unskip are auditable edits. |
| Split examples used amounts. | Split examples use normalized shares that add to `1.0`. |
| Corrective filing used an amendment noun and CSV-code identity. | Declaration commands use a recalculated draft. |
| Verify accepted an export flag. | Export uses `--output`; verify uses `--file`. |
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
16. Correction recalculation
17. Safety and status

## Canonical V6 Surface

```text
aeat setup ...
aeat app overview ...
aeat app ledger import PATH --provider PROVIDER [--dry-run] [--verify] [--source PATH] [--verbose]
aeat app ledger review --filter KEY=VALUE
aeat app ledger review --id ROW --verbose
aeat app ledger edit --id ROW --set COLUMN=VALUE --reason REASON
aeat app ledger edit --id ROW --skip true|false --reason REASON
aeat app ledger edit --id ROW --split business=SHARE --split personal=SHARE --reason REASON
aeat app ledger edit --id ROW --split clear --reason REASON
aeat app invoice import PATH --kind issued|received
aeat app invoice review --filter KEY=VALUE
aeat app invoice review --id INVOICE --verbose
aeat app invoice edit --id INVOICE --set COLUMN=VALUE --reason REASON
aeat app invoice match --period PERIOD
aeat app declaration calculate --period PERIOD --modelo MODELO
aeat app declaration review --period PERIOD --modelo MODELO --format table
aeat app declaration status --filter status=pending --period PERIOD --modelo MODELO
aeat app declaration edit --id draft_MODELO_PERIOD --set COLUMN=VALUE --reason REASON
aeat app declaration approve --id draft_MODELO_PERIOD --by reviewer --reason REASON
aeat app declaration validate --id draft_MODELO_PERIOD
aeat app declaration export --id draft_MODELO_PERIOD --output PATH
aeat app declaration verify --id DRAFT_ID --file PATH
aeat app declaration calculate --period PERIOD --modelo MODELO
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
amendment subcommand
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
- Export verification against a local file.
- Recalculated declaration after late or corrected records.

## Backend Work Still Required

- Ledger schema cannot be manually approved.
- Import verification must be backend-owned.
- Skip state must be persisted and reflected in calculations.
- Split metadata must preserve source transactions and allow clearing.
- Invoice retention and IVA category need backend audit.
- Declaration calculate output needs a backend contract.
- Export and verify output need a backend contract.
- AEAT correction identity behavior must be confirmed per modelo.
