---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:74fb47ea38163f0ff1aea7f71d0007271fd6e7e426e304e5ccd0513ed901d21d'
step_id: 'S05'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Add explicit recargo, iva-category, invoice-class and series options to the canonical writer and both entry verbs so every regime is expressible without inferring one from operation-type, holding the peer totals identity grand_total equals base_total plus iva_total plus recargo_amount with retencion outside it

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py`

## Description

- Added the four regime options plus an explicit IVA-category option to both canonical entry verbs, typed on their enums.
- Made an explicitly stated IVA category win over the one derived from the M349 clave.
- Echoed all five axes back on the text surface, which they were not.
- Asserted the totals identity end-to-end through the CLI rather than only at the application boundary.
- Added five locale leaves with real values in all four catalogues.

## Outcome

**Every regime the aggregate models is now expressible by an operator.** The preceding phase gave the writer these axes; this reaches them from the command line, on both canonical entry verbs.

Three decisions beyond wiring:

**An explicit IVA category wins over the derived one.** The verb already derived a category from the M349 clave, so that an intracomunitaria would not be left ungrounded when the operator stated only the clave. That derivation is a FALLBACK. Letting it override a category the operator explicitly stated would invert its purpose — the operator would silently get a treatment they did not choose, on the field the renta lane grounds its calculation with.

**The five axes are echoed back on the text surface.** They were settable but unconfirmed. A setting the surface does not confirm is one the operator cannot tell they failed to apply, and on these axes that is not cosmetic: a rectificativa silently recorded as ordinaria is a filing error, not a display one.

**The totals identity is asserted through the CLI**, not only at the application boundary: a 1000 base with a 210 cuota and a 52 recargo renders a grand total of 1262.00 — the recargo INSIDE the total, the retención outside it. Proving that end-to-end matters because the identity is where an operator-facing surcharge option could most plausibly go wrong silently.

**An operator-facing inconsistency found and recorded rather than fixed.** The two closed enums on this verb render their accepted sets in different cases: invoice class as `ORDINARIA / SIMPLIFICADA / RECTIFICATIVA`, IVA category as `domestic_general_21 / intra_community_supply / ...`. So the same verb asks the operator for uppercase on one option and lowercase on the next. That is a real wart, and it is NOT fixed here: aligning it means changing enum member values, which requires reconciling every validation, schema, fixture and test consumer into one accept-or-reject state. Doing that inside a CLI-surface Step would bury a cross-cutting change in an unrelated commit.

## Verification

    uv run --no-sync python -m cadrumo.locales scaffold --check
    ca.yml: ok / en.yml: ok / es.yml: ok / hu.yml: ok

    uv run --no-sync pytest src/cadrumo/locales -q --no-header
    34 passed in 173.80s (0:02:53)

    uv run --no-sync pytest .../test_documented_command_conformance.py -m integration -q --no-header
    354 passed in 17.62s

    uv run --no-sync pytest .../test_catalogue_invoice_lifecycle.py .../test_catalogue_invoice_wizard.py .../test_catalogue_invoice_link_flow.py -m integration -q --no-header
    28 passed in 20.96s

The refusal proof asserts the accepted set appears in the output, so the closed axis instructs the operator rather than failing bare.

## Notes

**A locale write failed mid-run with `OSError: [Errno 22] Invalid argument`** against the catalogue file. That is the known concurrent-I/O failure mode of this filesystem, not a fault in the locales tooling: the same command succeeded on retry, and the remaining leaves were written through a retry wrapper. Recorded because the failure is silent in aggregate — four of five leaves had landed and only a per-key check revealed the gap. A locale change on this machine should be verified per key, not by the command's exit status alone.

**A code edit also failed silently earlier in this Step.** A scripted string replacement against the text-line builder did not match, reported success, and the resulting test failure read as though the emitted output were being cached. It was not — the edit had simply never landed. The fix was to use an exact-match editor, and the lesson is that a scripted replacement must be verified by re-reading the target rather than by the script's own exit code.
