---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-21-persona-fleet-bug-inventory-audit]]"
  - "[[2026-05-20-testimonial-driven-cli-verification-playbook-reference]]"
---

# Persona-fleet round 2 — tax-workflow findings

Second testimonial batch — 5 personas on the tax-workflow core
(transactions, modelo 130 / 303 / 100) plus one regression persona
re-verifying the round-1 remediation. Method: the testimonial
playbook. Round 1 is `[[2026-05-21-persona-fleet-bug-inventory]]`.

## Roster

| Persona | Task |
|---|---|
| Quim Ferrer | Regression - re-verify the round-1 fixes |
| Sergi Mas | Transaction import + ledger grooming |
| Inés Vázquez | Modelo 130 preparation end to end |
| Pau Riera | Modelo 303 preparation end to end |
| Lucía Moreno | Renta / Modelo 100 end to end |

## Regression - round-1 remediation HOLDS (Quim, corroborated)

Confirmed sound from a fresh operator's seat: delete-active never
locks the operator out (B1); the NIF error names the correct check
letter (confirmed independently by Sergi, Pau, Quim, Lucía - 4x);
`profile create` bare-name gives the clear two-path refusal;
`config repair` lists specific fields; no raw tracebacks anywhere.
The round-1 fixes landed and stay landed.

## A - DESIGN QUESTION (needs an ADR-level decision, not an ad-hoc fix)

### A1 - `work verify` blocked by `NO_PENDING_OBLIGATION` with no operator path
Reporters: Inés, Pau, Lucía (this batch) + Rosario (round 1) - **4**.
After a correct `work calculate`, `work verify` refuses with
`abort_code: NO_PENDING_OBLIGATION`. `modelo readiness` for the same
modelo reports `ready: True` - a direct cross-surface contradiction.
The deadline-engine gate makes `verify` require an open filing
window, so it is unusable for ordinary offline preparation of any
past or future period. The B2 fix cleaned the *message* (no raw
repr); the *semantics* remain: should `verify` validate a calculated
revision regardless of the filing-window state? This is a workflow-
semantics decision - it belongs in an ADR, cross-referenced from the
apex CLI ADR, not a quick patch. **Highest-priority follow-up.**

## B - Ledger import internals (in scope - Sergi)

- **B1** `ledger import --dry-run` always reports 0 entries imported -
  the preview is useless and misleading.
- **B2** Deduplication breaks after a transaction is edited: the
  edited row's fingerprint changes, so a re-import of the same
  statement re-adds it.
- **B3** No cross-format dedup - importing an OFX then a CSV of the
  same movements duplicates every row.
- **B4** `ledger list` corrupts accented characters (`à` -> `?`)
  while `ledger view` renders them correctly - a list-rendering
  encoding bug.

## C - Ledger UX residuals (in scope - residual to round-1 D/E)

- **C1** Opaque `command input failed validation, run config repair`
  still fires on `ledger classify` with an invalid input (e.g. a
  negative `--taxable-base`). Round-1 D fixed `add` and `review --id`
  but not `classify`.
- **C2** `ledger categories` output is `group<TAB>id`, which implies a
  compound `--category-id` key; only the bare id is accepted.
  Misled Sergi and Quim - 2 reporters.
- **C3** `overview status` still says "no business operations
  imported" after business-classified transactions exist.
- **C4** `--business-pct` exists on `ledger add` but not `ledger
  classify`; `ledger history` needs `--id` while `ledger view` takes
  it positionally - sibling-command inconsistencies.

## D - Modelo / bindings discovery (in scope - Inés, Pau, Lucía, Quim)

- **D1** Numeric BOE casilla numbers (`69`) and the short ids shown in
  the `casillas` `number` column are rejected by `work calculate` -
  only dot-path ids work. The `number` column is misleading.
- **D2** `bindings list --missing` returns the full binding set,
  identical to the unfiltered call - the filter does not consult the
  active profile (Lucía, Quim).
- **D3** `bindings list` without `--period` resolves the latest
  revision (2025) for `--year 2024`, returning `renta-2025-*` ids
  invalid for a 2024 work unit.
- **D4** `modelo work create --modelo 036` rejects every period token
  it lists as valid (`alta` / `baja` / `modificacion`).
- **D5** The `estimacion-directa` binding shows `typed_enum` in
  `bindings list` but rejects enum values and requires an
  undocumented Decimal (`1`).
- **D6** Period-token format hints disagree across `work create`,
  `bindings list`, and `describe` help text.

## E - Calculation engine - OUT OF SCOPE (the excluded ledger-calc bridge)

Lucía's Modelo 100 "calculates all-zero from a salary input" and the
negative-retención result are the ledger-to-calculation island /
registry-formula territory the project owner explicitly removed from
this agent's scope ("completely ignore the ledger and calculation
island bridge - craft ADRs"). Recorded here for the bridge ADR, not
actioned by the testimonial-remediation track.

## F - Polish

- `work calculate` dumps every casilla (2235 for Modelo 100) with no
  result summary - the key figures are unreadable without knowing the
  form by heart.
- `config repair` field labels render in English ("Disability grade",
  "Death date") in an otherwise-Spanish CLI - a locale gap in the
  field-label catalogue.

## Disposition

- **A1** - flagged for a workflow-semantics ADR; the highest-value
  follow-up. Not ad-hoc patched.
- **B, C, D, F** - in-scope CLI defects; dispatched as a round-2
  remediation (a ledger cluster and a modelo/bindings cluster).
- **E** - out of scope; carried to the ledger-calc bridge ADR.
