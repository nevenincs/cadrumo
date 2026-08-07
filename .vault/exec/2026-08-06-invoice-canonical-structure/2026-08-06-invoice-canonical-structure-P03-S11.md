---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:47a3350c6f6849f78e500b2c17915cb013e0af95ba2c0ffdaa37958464cb8d45'
step_id: 'S11'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Repoint the five bare invoice verbs add, view, list, update and remove at the canonical aggregate and retire the catalogue sub-noun, keeping the operator noun and the kind issued-or-received flag exactly as the superseded ADR established them

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py`

## Description

- Delete the five slim-backed verbs and promote the catalogue verbs onto the bare `invoice` noun.
- Rename the `create` verb to `add`, matching the CRUD spine the operator contract declares.
- Remove the `catalogue` Typer sub-app and its mount, so the sub-noun no longer exists.
- Rewrite every envelope identifier from the catalogue form to the bare `ledger.invoice` form.
- Add an `update` verb over the canonical patch service, which the sub-noun never exposed.
- Drop the dead helpers the slim verbs owned: the per-kind service selector, the slim payload and text-line builders, and the EU IVA-ID validator.
- Sweep the surfaces the gates do not scan together: the runtime write-policy allowlist, the risk table, the documented-command sequences, and the operator-surface contract.

## Outcome

The group exposes `add`, `import`, `list`, `remove`, `update`, `view` and `wizard`, with no sub-apps. One aggregate sits behind every verb, so the documented add-then-link chain resolves end to end. It previously dead-ended, because `add` wrote the store without linked transaction ids and `link` read the other one.

Two capability gaps surfaced while repointing and were closed rather than accepted. The canonical text surface printed only the grand total, dropping the base and cuota breakdown the slim surface showed; an operator reconciling a recargo or a reverse-charge line cannot check a total against a factura without them. And the risk table carried duplicate entries for the collapsed verbs, deduplicated to the seven the surface actually mounts.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_business_invoice_verbs.py src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_bulk_import.py src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_lifecycle.py src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_link_flow.py src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_payloads.py src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_wizard.py src/cadrumo/entrypoints/cli/tests/test_ledger_interface_contract_payloads.py -m "unit or integration"
    82 passed in 16.80s

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -m "unit or integration"
    352 passed in 17.32s

## Notes

The verb suite was repointed rather than retired, so each capability it asserted survives on the canonical surface. The silent-zero guard moved from the total-amount option to the taxable-base option, which is the stronger form: the canonical aggregate derives the grand total from a required base, so an operator-omitted amount cannot default to zero and drop a counterparty from a Modelo 347 threshold check.

One test was inverted rather than deleted. It asserted that linking must REFUSE an id minted by `invoice add` -- true while two stores existed, false once they collapsed. It now asserts the chain resolves, which guards the fix instead of the defect.

The country-code option is required with no default. The plan flagged a silent domestic assumption on the canonical verbs as a blocking gap; the canonical surface refuses the omission instead of assuming Spain.
