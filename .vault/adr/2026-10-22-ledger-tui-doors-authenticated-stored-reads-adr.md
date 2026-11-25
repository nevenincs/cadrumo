---
tags:
  - '#adr'
  - '#ledger-tui-doors'
date: '2026-10-22'
modified: '2026-10-22'
body_schema: 'body-v2'
body_hash: 'sha256:41d06b2eb8b3137617126e6531559c68f7e28ab03c3c530622f905478c5fd8fc'
related:
  - "[[2026-07-05-ledger-latency-budget-adr]]"
  - "[[2026-07-06-ledger-perf-optimization-adr]]"
  - "[[2026-08-22-secure-storage-performance-hardening-adr]]"
  - "[[2026-06-10-ledger-amount-direction-adr]]"
  - '[[2026-10-22-ledger-tui-doors-ledger-read-cost-audit]]'
---

# `ledger-tui-doors` adr: `authenticated stored ledger reads` | (**status:** `accepted`)

Accepted 2026-10-22 on the user's instruction in conversation: skip the re-admission checks for rows the store already authenticated, remove duplicated validation, and move to pydantic-native coercion.

## Problem Statement

Every read of a stored ledger record re-runs the full admission validation that first admitted it. At 30,000 transactions one whole-ledger read costs about 6.4 CPU-seconds, about 74% of it re-validating rows: 78 wrapped validator calls per row, including re-deriving each transaction id by hashing its raw record, reconstituting gross from base, IVA and recargo, and re-resolving dated registry vocabulary. Records screens that read the whole ledger (unfiltered entries, review, classifier diagnostics, the workbench projection) cannot load in usable time while every read repeats admission. The invoice catalogue has the same shape: showing one invoice validates all of them. Evidence: the P04.S12 and P04.S11 measurements recorded in the `ledger-tui-doors` execution ledger.

## Considerations

- The secure store authenticates each record with AEAD bound to its namespace, object key, schema version and revision; a stored record cannot be altered or substituted without decryption failing (`2026-08-22-secure-storage-performance-hardening-adr`).
- The transaction id is the object key the store binds, so a re-hash on read re-proves what the binding already proves.
- Admission rules can tighten over time, and the registry's dated vocabulary changes by generation; a record written under older code or an older generation may no longer satisfy current admission.
- `2026-06-10-ledger-amount-direction-adr` requires a reload of a stored negative amount to raise a validation error.
- `2026-07-05-ledger-latency-budget-adr` names cheaper per-row validation as the follow-up lever and forbids plaintext caches and index widening.

## Considered options

- **Keep full re-admission on every read.** Correct and simple; leaves whole-ledger reads at about 6-7 CPU-seconds and invoice view decoding every invoice. Rejected by the user.
- **Cache decoded records across reads.** Removes repeat cost but keeps plaintext beyond a call; rejected by the storage hardening decision.
- **Skip all validation on read.** Fastest, but loses type and structural guarantees and the amount-direction refusal. Rejected.
- **Skip only admission re-derivations for authenticated current-schema records, keep structural typing, remove duplicates, coerce natively.** Chosen.

## Constraints

- Applies only to a record the secure store decrypted and authenticated in the same call, written under the current row schema version. A record with an older schema version, or read through any path that did not authenticate it, receives full validation.
- On such a record, the read skips only re-derivations the store's authentication already proves: the derived-id re-hash for transactions and the derived invoice-id check for invoices, because the AEAD binds the object key and the repository asserts the addressed id. It keeps structural typing and field-level constraints, including enum membership, decimal and UTC typing, and the non-negative amount, so the amount-direction refusal still fires.
- The dated registry vocabulary and rule checks and the gross and totals reconstitution stay on every read. Several filing consumers do not refuse an out-of-vocabulary value at use: an unknown income concept counts as ordinary income (`src/cadrumo/domain/transactions/volumen_ingresos.py`), any Art. 104.tres tag leaves the prorrata volume (`src/cadrumo/application/aggregation/iva_ledger.py`), an undeclared cash-accounting token reads as cash accounting (`src/cadrumo/domain/iva/schema.py`), and an undeclared identification state passes the intracommunity exemption gate (`iva_ledger.py`). The gross relaxations read registry category sets that change by generation, and a stored row does not record its generation. Moving any of these checks off the read requires those consumers to refuse at use first, and a further decision.
- Writes, imports, edits and every other admission path keep full validation unchanged.
- An explicit full re-validation path stays available to operators (the ledger check), so drift between stored records and current rules remains detectable.
- Consumers that apply registry rules at use (calculation, filing, export) keep refusing a value the pinned authority does not accept; skipping load-time checks must not let an unaccepted value reach a filing silently.
- Duplicated validation is removed where one check subsumes another, with identical accepted inputs and refusals.
- The `Transaction` model moves from strict types plus before-coercers to pydantic-native coercion only after every Python-mode constructor is inventoried and converted; accepted inputs for real callers stay identical.
- The same rule covers the invoice catalogue: an authenticated current-schema catalogue may validate only the invoices a read returns, each with the checks this record keeps.
- No plaintext cache, no new index column and no change to stored formats.

Amended wording in prior records:
- `2026-08-22-secure-storage-performance-hardening-adr`: the commitment that performance work preserves refusal semantics and authoritative validation now carries a scoped exception for authenticated current-schema ledger reads under this record.

## Implementation

We will add a trusted-read decode path for authenticated current-schema transaction rows and invoice catalogues that skips the id re-derivation the store already proves, behind an explicit skip set, while keeping structural typing and the registry and arithmetic admission this record keeps; remove duplicated validators; and move the transaction model to pydantic-native JSON-mode coercion after converting Python-mode constructors. The exact split between structural checks kept on read and admission checks skipped is an implementation detail within the constraints above, proven by parity tests that compare trusted reads with full validation over varied seeds and by refusal tests for the paths still in force.

## Rationale

The store's authentication already proves a record is the one this profile wrote under this schema; re-proving its admission on every read spends most of a whole-ledger read on work that cannot change the outcome for such records. Keeping structural typing, write-time admission, schema-version gating, an explicit re-validation path and use-time registry refusal preserves every guarantee a filing depends on while removing the repeated cost.

## Consequences

Most of the per-row saving comes from removing duplicated validation and from native coercion; the trusted read removes the id re-derivation, and invoice views validate one invoice instead of the catalogue. Registry and arithmetic admission stays on read because the filing consumers named above rely on it. Reconsider the kept checks once those consumers refuse unaccepted values at use, or if a stored record is ever found to have bypassed write-time admission.
