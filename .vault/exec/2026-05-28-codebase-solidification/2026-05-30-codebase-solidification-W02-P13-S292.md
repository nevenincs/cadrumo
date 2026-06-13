---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
step_id: 'S292'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# `codebase-solidification` `W02.P13.S292`

Landed eight Steps in P13 closing the EncryptedPayload/EnvelopeDocument typed-boundary
sweep, the COLUMNS context-manager scope, and DEFAULT_CURRENCY enrollment.

- Modified: `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py`
- Modified: `src/aeat/adapters/persistence/storage/crypto/__init__.py`
- Modified: `src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py`
- Modified: `src/aeat/adapters/persistence/storage/master_key/_master_key.py`
- Created: `src/aeat/adapters/persistence/storage/master_key/test_envelope_document.py`
- Modified: `src/aeat/entrypoints/cli/_stdio.py`
- Modified: `src/aeat/entrypoints/cli/test_stdio.py`
- Modified: `src/aeat/adapters/inbound/financial/providers/_pdf_n26.py`
- Modified: `src/aeat/adapters/inbound/financial/providers/test_pdf_n26.py`

## Description

S292: Added `EncryptedPayload(BaseModel)` with a `data: object` field to `_encrypted_columns.py`.
`EncryptedJSON.process_result_value` wraps the `json.loads` result and returns `.data`.

S293: Extended `TestEncryptedPayload` with real SQLAlchemy roundtrip, direct model construction
for all JSON-compatible types, missing-field rejection, and anti-tautology disk inspection.

S294: Defined `_EnvelopeFact`, `_EnvelopePayload`, and `EnvelopeDocument` in `_master_key.py`.
Replaced the `json.loads + dict.get` chain in `_extract_profile_tax_ids` with
`EnvelopeDocument.model_validate_json`.

S295: Created `test_envelope_document.py` with 15 tests covering all envelope shapes and
`_extract_profile_tax_ids` edge cases including malformed bytes, truncated JSON, and non-string
tax-id value filtering.

S305: Converted `_ensure_help_render_width` to `@contextlib.contextmanager`. Saves original
COLUMNS, sets the floor inside the block, restores unconditionally on exit.

S306: Added three scoping tests confirming env state before == after for help and non-help
invocations. Updated existing call sites to `with _ensure_help_render_width():`.

S313: Added `DEFAULT_CURRENCY` import in `_pdf_n26.py`; replaced both `"EUR"` literals in
`_extract_statement_currency` with `DEFAULT_CURRENCY`.

S314: Added `test_extract_statement_currency_uses_default_currency` and
`test_extract_statement_currency_raises_on_missing_currency`.

## Tests

113 tests collected, 113 passed in 2.03 s. No mock, skip, xfail, or tautological assertions.
Commit: `8576da94c` on `chore/eliminate-shims`.
