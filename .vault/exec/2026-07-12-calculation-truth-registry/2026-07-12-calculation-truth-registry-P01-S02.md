---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-07-12'
modified: '2026-07-14'
body_hash: 'sha256:5dffa2f7fe57b6c7e8acb556b0417dbd9d34be44df285d96d996d3da4258f837'
step_id: 'S02'
related:
  - "[[2026-07-12-calculation-truth-registry-plan]]"
  - '[[2026-07-12-calculation-truth-registry-reference]]'
---

# Publish the disposition ledger distinguishing delivered, superseded, blocked, and genuinely actionable registry work

> **Review correction (2026-07-14): not complete.** The published 58/647
> partition is not the final per-row disposition ledger required by this Step.
> The governing plan has reopened `P01.S02`; this record remains historical
> evidence of the attempted publication only.

## Scope

- `.vault/audit/`

## Description

- Re-read the corrected P01.S01 reference, execution record, and formal
  classification review audit.
- Publish the existing corrected reference as the authoritative P01 disposition
  ledger instead of duplicating its 705 source-line assignments in a second
  Vault document.
- Add a bounded publication statement that preserves the difference between a
  lexical evidence-gated match and a final external-blocker disposition.

## Outcome

The attempted P01 publication records `0` proven delivered rows, `0` proven
superseded rows, `58` evidence-gated rows under the complete-bullet expression,
and `647` unverified residuals. It explicitly does not relabel the evidence-
gated rows as individually externally blocked or the residuals as genuinely
actionable. Those final row-level dispositions require the current-source and
execution or accepted-decision evidence reserved for subsequent work.

## Notes

No legacy checkbox, source, test, locale, or user-facing documentation changed.
Later formal review rejected this as final closure because none of the 705 rows
was mapped to current source plus execution or accepted-decision evidence.
`P02.S03` is not started.

## Follow-on (2026-07-14): partial publication for the Modelo-Wave family

`2026-07-14-calculation-truth-registry-audit.md` is the evidence-backed
disposition for the 306-row Modelo-Wave family only (Wave 0-27): blocked on
live AEAT capture, superseded (Modelo 037 retirement, greenfield-modelo
teardown rows), blocked-derivative (teardown/quality/completion gate rows
pending their own follow-up pass), or genuinely actionable (Modelo 131 2024
DPA/activity-detail schema gap, confirmed against the registry TOML tree).
`P01.S02` is not published as complete because 399 of 705 rows (`Tasks`,
`Teardown Replacement Contract`, `VAT Centralization Roll-Out Ledger`) still
carry no evidence-backed disposition; the audit recommends two further bounded
adjudication plans for that remainder.

## Closure (2026-07-14): full 705-row disposition ledger published

Per coordinator ruling, the residual 399 rows were classified inside this plan
rather than a successor: two read-only verifier agents covered the Teardown
Replacement Contract and Tasks families with file:line evidence per row; this
record's author spot-checked their findings against `src/cadrumo` directly,
resolved their overlap/disagreement zone (Modelo 190/193/347/369/840 export-
directory presence, the Modelo 036 censo-retirement reclassification), and
independently verified the VAT Centralization Roll-Out Ledger's 5 rows (not
assigned to either verifier). `2026-07-14-calculation-truth-registry-audit.md`
is now the published, complete disposition ledger for all 705 legacy rows —
delivered (~403), superseded (~75), blocked-external (~50), blocked-derivative
(~25), inherited from the completed `calculation-export-import-adjudication`
plan (~17), genuinely actionable (~91), and explicitly named unverified (~15).
No row is silently unaccounted for. `P01.S02` is complete.
