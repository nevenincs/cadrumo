---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:ff96f60e8b1e61c4dd3f1f22675d2b8e032e7cc1dfbe853198c8dc59d9ce81b4'
step_id: 'S131'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Merge the two Spanish identity validators onto one AEAT leader policy, keeping the richer refusal payload and correcting the test that asserted the laxer reading

## Scope

- `src/cadrumo/core/identity/_documents.py`
- `src/cadrumo/core/identity/_tax_id.py`
- `src/cadrumo/core/identity/tests/`
- `src/cadrumo/domain/invoices/tests/test_validators.py`

## Changes

- `M` `src/cadrumo/core/identity/_documents.py`
- `M` `src/cadrumo/core/identity/_tax_id.py`
- `M` `src/cadrumo/core/identity/tests/test_documents.py`
- `M` `src/cadrumo/core/identity/tests/test_tax_id.py`
- `M` `src/cadrumo/domain/invoices/tests/test_validators.py`
- `verify:` `pytest src/cadrumo/core/identity/tests src/cadrumo/domain/invoices/tests/test_validators.py -n 0 -m ""` -> `pass` (136)
- `verify:` `pytest src/cadrumo/domain/{invoices,iva,censo} -n 0 -m ""` -> `pass` (1070)
- `verify:` `pytest src/cadrumo/application/auth src/cadrumo/application/ledger/tests/test_{counterparty_tax_id_agreement,identity_roles}.py -n 0 -m ""` -> `402 pass, 1 unrelated fail`
- `verify:` `pytest src/cadrumo/core/tests -k "redaction or identity" -n 0 -m ""` -> `pass` (382)

## Notes

Two validators, one question, different answers: `validate_identity("A1234567D")`
refused where `validate_spanish_tax_id("A1234567D")` accepted. Both computed the
same CIF check value; they disagreed only on whether an `ABEH` kind letter may
carry a letter control. Each carried a comment calling the divergence
deliberate, and one contradicted its own module docstring, which stated the AEAT
rule correctly.

The merge direction was determined, not chosen. AEAT partitions the kind letters
three ways and `ABEH` is the digit-only class, so the accepting side admitted an
identifier the sede refuses -- with the declaration already built around it.
`_tax_id`'s four restated validators are deleted (140 lines) and
`validate_spanish_tax_id` delegates; the return shape is now the only difference
between the surfaces.

The refusal payloads also diverged, and that was resolved the other way: the
surviving validator raised with the translation key alone, so `str(exc)` was
`errors.identity.nif_check_letter_mismatch` rather than a sentence. The deleted
surface's plain-English messages were moved onto all twelve raises before it
went, so the merge kept the richer half of each half.

`test_validate_spanish_tax_id_accepts_abeh_letter_form` asserted the defect as
the contract, name and docstring included. Corrected rather than deleted, and it
now pins the refusal. `B1234567D` was the only such literal in the tree.

`_compute_cif_check` was orphaned by the merge and is deleted.
