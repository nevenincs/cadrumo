---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:f0c34838dc70819536022642ac6379fa698c312c5b286bf25d7d06800be6e8b8'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-09-04-clitui-ledger-W01-P03-S09]]"
---

# `clitui-ledger` audit: `S09 governance reconciliation review`

## Scope

Reviewed S09's reconciliation of the live predecessor TUI plan against the
clitui-ledger ownership and implementation hold. The review inspected the four
named commits, predecessor and campaign plans, S09 execution record, current
reference and generated indexes, then independently counted dispositions and
checkboxes and challenged removal, duplication, reclassification, and target
mapping behavior. Vaultspec-RAG was attempted first; the local vault index
returned no results, so exact source reads and mechanical census checks supplied
the evidence.

## Findings

**Ruling: NOT ACCEPTED.** Two HIGH findings remain.

The live predecessor plan contains exactly 33 disposition annotations: 27
checked `RETAINED_PREDECESSOR_EVIDENCE` rows, the open S73
`RETAINED_RETIRED_PREMISE_MARKER`, and the five open S390, S395, S396, S411,
and S424 `DISPLACED_AND_HELD_UNTIL_G3` rows. Its completion remains 408 of 426
Steps. The mixed rows retain their non-Ledger scope, S73 remains explicitly
open without claiming parity implementation, S09 is checked, S10 is next, and
G0 remains OPEN. Commit inspection found documentation and index changes only;
no production or TUI implementation was introduced.

### disposition-census-has-no-detector | high | Sole ownership and hold annotations can silently drift

No production, development, or test code parses `CLITUI_LEDGER_DISPOSITION`.
The exact 33-row population, the three allowed tokens, the required checkbox
state for each token, the known overlap identities, and the one-token-per-row
rule exist only as prose in the predecessor plan. Removing an annotation,
duplicating one, applying an unknown token, changing a retained row to
displaced, or introducing a new Ledger-overlapping row without annotation is
not rejected by a campaign-specific detector; the generic Vault checks remain
green. That makes the sole-owner and G3 hold boundary silently
under-declarable.

### s411-target-is-the-record-step-not-the-navigation-owner | high | Substantive selection handoff is routed to the wrong campaign Step

S411 says its unresolved remainder is navigation: carry a selected transaction
from entries or review into classification and return a prepared import to its
area. Its annotation points to `W05.P19.S128`, which only records the reconciled
disposition of held predecessor rows before work resumes. The exact
implementation owner is `W05.P21.S136`, whose text carries selected
transaction, prepared import, review change-set, and artifact-plan identities
through Ledger navigation. The current pointer therefore sends substantive
work back to a governance-record Step and can let the navigation obligation be
missed.

## Recommendations

- Add a focused governance detector under `dev/quality/tests/` that parses the
  predecessor plan and pins the exact 27 retained IDs, open S73 marker, exact
  five displaced IDs, allowed stable tokens, checkbox/token relationships,
  one disposition per overlap, and refusal for missing, duplicate, unknown, or
  unannotated Ledger overlap. Mutation tests must prove each refusal.
- Change S411's clitui-ledger destination to `W05.P21.S136`; retain S128 only as
  the later governance reconciliation checkpoint.
- Re-run the predecessor-plan census and plan/feature Vault checks before
  closing S09 again. Do not change the 408/426 completion state or implement
  any TUI work.

## Verification

The independent census reproduced 33 dispositions as 27 retained, one retired
premise marker, and five displaced-and-held rows, with 408 checked and 18 open
Steps. Named commit inspection confirms the plan mutations were performed by
Vault documentation commits and that S09's record accurately names the shared
worktree commits. Feature Vault checks pass, but there is no focused S09
detector to run; that absence is the first HIGH finding rather than positive
evidence.

## Remediation review

**Ruling: NOT ACCEPTED.** The new detector closes the fixed-census and S411
findings, but one HIGH under-declaration path remains.

The detector pins the exact 27 retained IDs, open S73 retired marker, five open
held IDs, all token and checkbox relationships, unique Step identities, one
annotation per known row, mixed-scope wording, and predecessor completion at
408/426. It rejects missing, duplicate, unknown, reclassified, outside-known,
checkbox, completion, mixed-scope, and exact-word new-overlap mutations. S411
now correctly names `W05.P21.S136` as the selection-handoff implementation
owner and `W05.P19.S128` only as the held-row disposition checkpoint.

### overlap-discovery-misses-common-ledger-wording | high | Identifier and plural variants can silently convert an existing row into Ledger scope

Unannotated overlap discovery uses only the natural-word expression
`\bledger\b`. Exact total-row pinning catches an appended Step, but it does not
protect an existing non-overlap Step whose scope changes. Independent
same-count mutations of S408 to `Retire the ledger_binding_resolution facade`
and `Render accounting ledgers in AEAT Sync` were both accepted. The underscore
keeps `ledger` inside one regular-expression word and the plural has no trailing
word boundary. Meanwhile `Record the audit ledger for AEAT Sync` is rejected,
demonstrating the converse false positive for a generic ledger rather than the
Ledger product. The exact 33-ID table protects today's rows but does not make
future semantic overlap discovery complete.

Derive overlap from stable reviewed signals rather than one natural-language
word: scoped `/ledger/` paths, `ledger_` identifiers, Ledger-prefixed product
symbols, and explicit reviewed include/exclude decisions for ambiguous generic
or plural wording. Add same-row mutations for underscore identifiers, paths,
symbols, plurals, and generic accounting/audit-ledger exclusions. A newly
Ledger-scoped existing Step must fail until explicitly adjudicated without
turning unrelated uses of the common noun into campaign ownership.

The focused detector reports 12 passed. Ruff format/check, scoped `ty`, and the
feature Vault check pass. Commit inspection still shows no production or TUI
changes attributable to S09; S09 remains checked, S10 next, and G0 OPEN.

## Final classifier review

**Ruling: NOT ACCEPTED.** The final classifier closes the previously reported
identifier, path, symbol, plural-context, and generic audit-ledger cases, but a
HIGH semantic underreach remains.

The current 33-row authority is stable at 27 checked retained rows, open S73,
and five open held rows; tokens, uniqueness, mixed scope, 408/426 completion,
and S411's S136 implementation plus S128 checkpoint mapping remain correct.
The requested `ledger_binding_resolution`, `_ledger` suffix, `/ledger/` path,
`LedgerWorkspace` symbol, accounting-ledgers context, and audit-ledger
exclusion mutations behave correctly.

### product-ledger-domain-list-remains-incomplete | high | Ordinary capability phrases bypass overlap adjudication

The domain classifier recognizes capitalized product `Ledger` only when its
neighbor appears in a hand-enumerated noun-stem list. Independent same-row S408
mutations `Export Ledger data for review`, `Add Ledger notes to the workbench`,
`Download Ledger attachments`, and `Edit Ledger fields` were all accepted
without a disposition. These are direct campaign capabilities, not ambiguous
uses of the common noun. The reviewed include set protects only the current 33
IDs, so it cannot detect an existing non-overlap Step acquiring this new scope.

Recognize capitalized product `Ledger` as an overlap signal generically, with
explicit reviewed exclusions for genuine common-noun contexts, or require an
explicit include/exclude adjudication for every ambiguous occurrence. Add the
four same-row mutations above so extending the noun vocabulary cannot silently
escape ownership.

The focused suite passes all 19 committed tests. Ruff format/check, scoped
`ty`, and feature Vault checks pass. G0 remains OPEN and no S09 production or
TUI edits were found.

## Product-signal remediation review

**Ruling: ACCEPT.** No HIGH or CRITICAL findings remain. Capitalized `Ledger`
is now a generic product signal, while the explicit audit-ledger exclusion and
lowercase common-noun behavior remain bounded. The four previously escaped
export, note, attachment, and field mutations now refuse. Independent
punctuation and possessive variants also refuse, and an excluded audit-ledger
phrase placed beside a separate `Ledger` product phrase does not mask the
product overlap.

Existing `ledger_` prefix, `_ledger` suffix, `/ledger/` path,
`LedgerWorkspace` symbol, domain phrase, and reviewed plural signals continue
to refuse unannotated overlap. Generic lowercase `ledger data` and audit
ledger wording do not false-positive. The live plan remains exactly 33
adjudicated rows: 27 checked retained, one open retired marker, and five open
held rows, with 408/426 completion, mixed-scope retention, and S411's S136
implementation owner plus S128 checkpoint intact.

All 25 focused detector tests pass. Ruff format/check, scoped `ty`, and feature
Vault checks pass. S09 introduces no production or TUI edits; G0 remains OPEN,
S09 is checked, and S10 remains next.
