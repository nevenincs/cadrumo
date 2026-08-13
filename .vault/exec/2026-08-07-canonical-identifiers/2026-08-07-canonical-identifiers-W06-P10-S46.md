---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:6d81001003a4a7232784716b28a77a86467486a761b74d260fa62a724885d92c'
step_id: 'S46'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# counterparty-facing tax identity: `supplier_tax_id`, `customer_tax_id`, `party_tax_id`, `donor_tax_id` onto `TaxIdIdentityToken`

## Scope

- `src/cadrumo/application/ledger/_evidence_draft.py`
- `src/cadrumo/entrypoints/cli/_ledger_business_payloads.py`
- `src/cadrumo/llm/_suggestions.py`
- `src/cadrumo/domain/calculations/registry/_invoice_bindings.py`
- `src/cadrumo/domain/calculations/registry/_donativo_bindings.py`
- `src/cadrumo/llm/_invoice_field_grounding.py` (touched, then fully
  reverted — see Description)

## Description

- Checked `TaxIdIdentityToken`'s actual validator shape before assuming
  it carries the same risk profile `S45` found for `SubjectTaxId`:
  `tax_id_identity_token` is a `BeforeValidator` performing only
  trim-and-uppercase, never a rejection. Confirmed empirically against
  `""`, whitespace-only, `None`, a Spanish NIF, and a foreign VAT-shaped
  value — all construct without raising. None of `S45`'s
  empty-string-default blocking conditions apply to this bucket.
- Retyped `supplier_tax_id`/`customer_tax_id` in `_evidence_draft.py`
  (`InvoiceDraft`), `_ledger_business_payloads.py`, and `_suggestions.py`
  (`ExtractionPayload`); `party_tax_id` in `_invoice_bindings.py`'s two
  M349 recap-declaration accumulators
  (`_OperatorClaveAccumulator`/`_OperatorClavePeriodAccumulator`,
  confirmed genuinely counterparty-facing — the intra-EU operator the
  filer traded with); `donor_tax_id` in `_donativo_bindings.py`'s
  per-donor accumulator.
- Retyped `llm/_invoice_field_grounding.py`'s
  `_ExtractedInvoiceFieldClaims.supplier_tax_id`/`.customer_tax_id`
  FIRST, then ran the module's test suite before moving on — the
  discipline that caught the defect. `test_invoice_field_anchors.py`
  failed two tests: `'NIF CLIENTE: 12345678Z' == 'NIF cliente:
  12345678Z'`. `TaxIdIdentityToken`'s uppercase normalisation of the
  CLAIM value leaked into a downstream ANCHOR computation asserting the
  document's original printed case survives verbatim. The file's sibling
  class, `ExtractedRoleEvidence`, already documents the exact risk in its
  own docstring — "nothing is rejected or rewritten here, because the
  check that matters needs the document" — a warning this row read
  before editing but wrongly judged not to apply to the claims class
  too. Reverted both fields and the import, confirmed
  `git diff --stat` shows zero change against `HEAD`, re-ran the suite:
  38/38 green. Left the whole file untouched — both occurrences, 4
  sites — rather than only the one that failed, since the same
  verbatim-preservation concern plausibly reaches the untested one too
  and a passing test is not evidence of safety here, only of what this
  session's fixtures happened to exercise.
- `counterparty_tax_id` (scope-blocked, 5 parameters against 4 fields)
  and `member_tax_id` (already fully typed, zero enrollment) were
  excluded from this row's scope before execution — see the row's own
  re-sizing text — and neither was touched.

## Outcome

COMPLETE. 9 of the row's 13 re-sized sites retyped; 4 left bare after a
retype-then-revert cycle caught a real, test-confirmed regression rather
than an assumed one. `ruff check`, `ruff format --check` clean on all six
touched files; `ruff format --check` separately flags a PRE-EXISTING,
unrelated formatting issue in `_evidence_draft.py` at line 977
(confirmed present in the unmodified `HEAD` blob, nowhere near either
touched field). `basedpyright` clean on the three gated files
(`_evidence_draft.py`, `_invoice_bindings.py`, `_donativo_bindings.py`);
`_ledger_business_payloads.py`, `_suggestions.py`,
`_invoice_field_grounding.py` sit outside its configured `include`.

Real tests green: 1344 passed / 5 pre-existing unrelated failures across
the full `application/ledger/tests/` suite (confirmed unrelated — none
reference a tax-identity name, none of the four implicated files are
dirty); 22 passed across `test_invoice_bindings.py`; 103 passed across
the `llm/tests/` sweep (`-k "suggestion or grounding or invoice_field"`),
including the 38 that re-confirmed the revert; 75 passed / 1
pre-existing-unrelated (the already-flagged `matched_rule_id` pattern
mismatch, a different identifier concept) across the targeted CLI ledger
sweep.

## Notes

No incidents — the near-miss (retyping `_invoice_field_grounding.py`
without reading its own sibling class's explicit warning closely enough
the first time) was caught by running tests before moving to the next
file, not by a second review pass. Recorded plainly: reading a docstring
warning is necessary but the discipline that actually catches the defect
is running the tests for EVERY file immediately after editing it, not
batching edits across files before testing any of them.
