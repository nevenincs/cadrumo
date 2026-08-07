---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:367e5b8f70e4f7642874990051b4025ccd4def6cca3c6d1685f63422385d524b'
step_id: 'S06'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Accept operation-date on every entry verb including the guided one, so a guided entry can reach a declared devengo rank rather than only the proxy rank

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py`

## Description

- Added the operation-date parameter to the guided-entry service and the option to the guided verb.
- Gave it its own field-named validator rather than reusing the invoice-date one.
- Proved it against the GUIDED verb specifically, and proved the refusal names the right field.

## Outcome

**A guided entry can now reach a declared devengo rank.** The direct verb has always accepted an operation date; the guided verb had neither the option nor a service parameter, so a record entered that way could only ever reach the proxy rank — period attribution resting on when the invoice was *written* rather than on when the operation was *performed*.

Those two dates coincide often enough that the difference is invisible until it is not, which is exactly why the gap survived: nothing was obviously wrong, it was just weaker evidence than the record could have carried.

**The operation date gets its own validator rather than sharing the invoice-date one**, and that is not tidiness. The guided verb's whole contract is that every field failure is attributed and accumulated in one refusal — a malformed NIF and a malformed date both reported together. A shared validator would report a malformed operation date under `invoice_date`, sending the operator to correct a value that was already correct, in the one verb whose selling point is precise attribution.

**The proof drives the guided verb specifically.** The Step's criterion is explicit that a test driving the non-guided verb would be green already and prove nothing — the vacuous shape this plan was rewritten to remove. It also asserts the stored operation date differs from the issue date, so a wiring that silently fell back to the issue date would fail rather than pass.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_wizard.py -m integration -q --no-header
    14 passed in 31.63s

    uv run --no-sync pytest .../test_documented_command_conformance.py -m integration -q --no-header
    354 passed in 17.94s

    uv run --no-sync ruff check <the three changed files>
    All checks passed!

The stored record is read back from the encrypted repository rather than asserted from the response payload, matching how the sibling wizard proofs in that module verify persistence.

## Notes

No locale leaf was added: the option reuses the existing operation-date help key, which the direct verb already carries in all four catalogues. Adding a second key for the same option text would have been a duplicate translation to keep in step, which is the shape this campaign is retiring elsewhere.

With this Step closed, the remaining `P02` work is the confirm boundary. One of those two Steps is gated on a sibling campaign's draft-side field rather than on anything here.
