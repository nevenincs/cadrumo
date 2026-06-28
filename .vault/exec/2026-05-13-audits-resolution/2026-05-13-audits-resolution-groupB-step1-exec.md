---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-schema-driven-wizard-ux-audit]]"
---

# audits-resolution group-b step-1

## scope

Plan row B1: route the wizard's tax-id widget through the existing
`validate_identity` checksum so every write surface rejects malformed
NIF / NIE / CIF values.

## change

`src/aeat/application/wizard/_widgets.py` imports
`validate_identity` and `IdentityError` from `aeat.core.identity`,
declares the closed set `_TAX_ID_QUESTION_IDS = {"tax-id",
"spouse-tax-id"}`, and extends `validate_text` so any question whose
id sits in that set additionally runs the Spanish identity checksum.
Failures raise `WizardValidationError` keyed on
`wizard.errors.invalid_tax_id` carrying the offending raw value and a
short detail string.

`config set tax.id <value>` already routes through
`validate_widget_answer` via the `tax-id` profile_key lookup in
`_question_for_profile_key`, so the same validation fires on the
post-setup mutation surface without additional wiring. The
quiet-mode entrypoint (`aeat config init --quiet --tax-id ...`)
runs the answer through `run_flow` over a scripted prompter, which
also calls `validate_widget_answer`.

`src/aeat/application/wizard/test_setup_runtime.py` updated to use a
valid checksum (`87654321X`) for the joint-declaration test that
previously asserted the wizard accepted the malformed `87654321Y`.

## verification

`pytest src/aeat/application/wizard/ -q`: 159 passed.

Quiet-mode probe with `AEAT_DATABASE_URL=sqlite:///tmp.db
AEAT_SECRET_STORE_BACKEND=unsecured AEAT_ALLOW_UNENCRYPTED=1
aeat config init --quiet --tax-id INVALID --activity design` exits
with code 2 and emits
`REFUSED: wizard.errors.invalid_tax_id ... not a valid NIF shape:
'INVALID'`.

`config set tax.id NOT_A_NIF` against the same sandbox exits with
code 2 and emits the same validation envelope.

The translation entry for `wizard.errors.invalid_tax_id` lands with
B5 (the missing-key sweep); the raw key currently surfaces verbatim
so renderers can map it at translation time.
