---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:834ef63e8898d9c33bd893a946d63258b407dfff30f2f92f091bdc81c68e7e03'
step_id: 'S47'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# a roundtrip regression proving a non-Spanish-shaped counterparty tax id validates under `TaxIdIdentityToken`

## Scope

- `src/cadrumo/core/identity/tests/`

## Description

- Searched for an existing test of the `TaxIdIdentityToken` pydantic type
  alias itself before writing one: `test_tax_id_comparison.py` tests the
  bare `tax_id_identity_token()` normalisation function, not the alias on a
  model field, and no test file names the alias at all. New file, not a
  duplicate.
- Reused the established German VAT-shape example
  (`"DE123456789"`, `^DE\d{9}$`) already carried as the canonical worked
  case in `core/identity/_nif_iva.py`'s own prefix specification table,
  rather than inventing a fixture value.
- Reused the shared `single_field_holder` fixture helper
  (`tests/fixtures/identity_holder.py`) already used by every sibling
  scalar-alias test in this directory (`test_snapshot.py`,
  `test_invoice_id.py`), rather than hand-rolling a one-off model.
- Four tests, in order of what each proves:
  - The EU-VAT-shaped id validates under `TaxIdIdentityToken` — the row's
    core ask.
  - The alias trims and uppercases (a lowercase, padded variant of the same
    id normalises to the canonical form) but this is normalisation, not a
    checksum gate.
  - THE TEETH: the identical value is REFUSED by `SubjectTaxId`
    (`pytest.raises(ValidationError)`). Named directly in its own docstring
    as the regression this guards — a fixture proving only that the token
    alias accepts the value stays green even if a future edit swaps a
    counterparty field from `TaxIdIdentityToken` onto `SubjectTaxId` (the
    split applied backwards), because that swap would not fail any of the
    other three tests.
  - A JSON serialise/deserialise roundtrip on a small wire-shaped payload
    model, since every `TaxIdIdentityToken` field this campaign actually
    retyped (`_ledger_business_payloads.py`, `_suggestions.py`,
    `_evidence_draft.py`) sits on a wire-facing payload, not a
    construction-only model — proves the alias survives the boundary these
    fields actually cross, not only in-process construction.

## Outcome

COMPLETE. New file
`core/identity/tests/test_tax_id_identity_token_type.py`, 4 tests, all
green (`pytest -v`: 4 passed). `ruff check`, `ruff format --check`,
`basedpyright` all clean with zero findings on the new file. Full
`core/identity/tests/` suite re-run to confirm no interaction with the 105
pre-existing tests: 109 passed.

## Notes

No incidents.
