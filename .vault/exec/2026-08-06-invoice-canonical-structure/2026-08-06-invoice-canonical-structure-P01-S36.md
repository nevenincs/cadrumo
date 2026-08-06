---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:0600cbb6f4312dc0d8295818129997185ff9a0aa0bedaa0c37e2e6822000c01e'
step_id: 'S36'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Remove the ES counterparty-country default from both canonical entry verbs so an omitted country refuses or derives rather than silently stamping a domestic country on a foreign invoice, preserving the slim verb's derive-or-raise behaviour across the fold because country is the routing key for both informativas

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py`

## Description

- Made the counterparty country a required option on both canonical entry verbs by moving it into the undefaulted block, which is how this CLI already declares a required option.
- Rewrote the option help to say it is mandatory and why, so the operator meets the reason rather than a bare parse failure.
- Reconciled the nine existing tests that relied on the removed default, passing the domestic country explicitly.
- Added the refusal proof and a positive control.
- Updated all four locale catalogues through the locales CLI, because the English leaf documented the removed default in prose.
- Swept the whole tree, including the executable documentation sequences, for any remaining invocation that omits the option.

## Outcome

**The counterparty country is now stated, never assumed, on both canonical entry verbs.**

The asymmetry this closes is the one a field-list inventory cannot see. Both stores carry a counterparty country, so a field-presence comparison finds parity. The defaults differ in the direction that matters: the canonical verbs defaulted to `ES`, and the slim verb they are about to replace defaults to nothing and either derives the country from the EU VAT-ID prefix or raises. `P03.S11` would therefore have converted a derive-or-raise into a silent domestic assumption while appearing to preserve the field.

A silent domestic stamp is not cosmetic on this axis, because the country routes **both** informativas. The M347 projection filters on the counterparty country being `ES`, so a foreign invoice stamped domestic is pulled INTO M347 and can carry a party over the declaration floor; on M349 the same record declares the wrong member state. The governing ADR states that after the fold all four axes are refused. Three were. This one was masked by the default.

Requiring the option is the honest remedy rather than deriving a fallback, because the canonical record has no EU VAT-ID field to derive from and, per the preceding Step, should not gain one: for a non-`ES` country the counterparty tax id already IS the NIF-IVA.

**Nine existing tests relied on the default**, which is the measurement that the change bites rather than being cosmetic. Each is reconciled to state the domestic country explicitly, so their intent is unchanged and now visible.

The locale catalogues needed the same correction: the English leaf described the option as defaulting to `ES`, so leaving it would have shipped help text asserting behaviour the code no longer has.

## Verification

The RED, before the tests were reconciled, is what proves the option is genuinely load-bearing rather than decorative:

    uv run --no-sync pytest .../test_catalogue_invoice_lifecycle.py .../test_catalogue_invoice_link_flow.py .../test_invoice_retencion_aggregate_cli.py -m integration
    9 failed, 7 passed in 23.89s

After reconciliation, including the refusal proof and its positive control:

    uv run --no-sync pytest .../test_catalogue_invoice_lifecycle.py -m integration
    9 passed in 16.85s

    uv run --no-sync pytest .../test_catalogue_invoice_wizard.py .../test_m349_business_invoice_export.py -m integration
    14 passed in 22.88s

    uv run --no-sync pytest .../test_documented_command_conformance.py -m integration
    354 passed in 14.46s

    uv run --no-sync python -m cadrumo.locales scaffold --check
    ca.yml: ok / en.yml: ok / es.yml: ok / hu.yml: ok

    uv run --no-sync pytest src/cadrumo/locales
    34 passed in 147.98s

A tree-wide sweep of every Python and executable-sequence invocation of the two verbs returns exactly one that omits the option, which is the refusal proof itself.

## Notes

A marker trap is worth recording, because the first verification run of this Step was a false green. Running the affected CLI tests by path alone selected nothing: they carry the integration marker and the default expression deselected every one of them. The harness printed "NOTHING RAN" and stated plainly that a green result there means the selection matched nothing rather than that the code is sound. Without that warning the reconciliation would have been recorded as verified against zero executed tests. Every run quoted above therefore carries its marker expression.

The locale correction is the same defect class this campaign keeps meeting from a different direction: prose that was accurate when written and silently became false. Here it would have been shipped to operators as help text.
