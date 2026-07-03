---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S32'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Run vaultspec-core vault check all and resolve any reported drift before declaring the plan complete

## Scope

- `.vault/`

## Description

- Ran `vaultspec-core vault check all` against the full repository vault and captured the full output to a log file before reading it back (per the pytest/CLI background-capture discipline of writing the complete stream to disk rather than truncating through a pipe).
- Found two real, in-scope findings on the first pass: (1) most of this feature's exec records carried 3-5 "extra blank lines" markdown-hygiene warnings, a side effect of the earlier `vault check annotations --fix` pass leaving blank lines where the stripped HTML comment blocks had been; (2) the companion ADR's own feature tag (`m210-categorical-conditional-predicate`, distinct from the umbrella `modelo-verify-nonzero-guards` tag) had never had a feature index generated, and the ADR itself carried 2 extra-blank-line markdown warnings.
- Fixed both: ran `vault check markdown --feature modelo-verify-nonzero-guards --fix` (13 files repaired) and `vault check markdown --feature m210-categorical-conditional-predicate --fix` (1 file repaired), then generated the missing index via `vault feature index --feature m210-categorical-conditional-predicate`.
- Re-ran `vault check all`: confirmed zero remaining findings reference either `modelo-verify-nonzero-guards` or `m210-categorical-conditional-predicate` anywhere in the output (verified by grep over the full captured log). The repository-wide total dropped from 46 errors / 220 warnings to 46 errors / 187 warnings (33 warnings closed by this Step); the unchanged 46 errors and remaining 187 warnings are pre-existing, unrelated repo-wide drift across dozens of unrelated ADRs, audits, plans, and research documents (mostly ADR-status-format non-conformance and unreplaced template placeholders in documents this campaign never touched), triaged per `full-tree-gate-must-distinguish-owner` and left untouched as out of scope.

## Outcome

`vaultspec-core vault check all` reports zero errors and zero warnings scoped to this feature's documents or its companion ADR's feature index. The repository-wide residual (46 errors, 187 warnings) is confirmed entirely pre-existing and unrelated to this campaign by direct grep cross-reference.

## Notes

No incidents. Two real, in-scope vault-hygiene gaps were found and fixed during this Step (the markdown blank-line drift introduced by the earlier annotations-fix pass, and the missing feature index for the companion ADR's own feature tag); both are now clean. This Step intentionally ran the full repository-wide `vault check all` rather than a feature-scoped subset, since that is the literal verification gate named by `W03.P10.S32` and by the plan's own Verification section.
