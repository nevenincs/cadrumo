---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:3d875c0e92c8fef20af052210e3ac8d08870a7f6eb4354bea2fc7ee65755bd1c'
step_id: 'S55'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---
# Wire simplificada_requires_tax_id_for_domestic_issuer to an operator-facing Notice

## Scope

- `src/cadrumo/application/invoices`
- `src/cadrumo/entrypoints/cli`

## Description

- Confirm the blocking premise still held after the catalogue retirement closed.
- Widen the creation signatures to the shape the domain already accepted.
- Make the CLI option optional, with the default Typer actually requires.
- Wire the predicate to a WARNING notice at the emit site.

## Outcome

The predicate shipped exported, documented and tested with zero production
callers, so the fact it computes was discarded. Its own docstring instructed
callers to surface a positive result as a Notice; nobody did.

The deeper problem was that the state it evaluates could not be reached. The
domain has always accepted an ISSUED factura simplificada with no counterparty
tax id - the reglamento's relief is precisely that a simplified invoice need not
name the destinatario - while the application layer forced one. So a lawful
simplificada was unrecordable, and the advisory unreachable by construction.

The option is now optional on the direct create path and the predicate is wired
to a warning. The guided wizard keeps requiring an id: it assembles a complete
record field by field, where an absent id is an unanswered question rather than
the deliberate omission a simplificada represents.

Advisory, never a refusal. A domestic ticket with no identified customer is
ordinary practice, and the predicate rests on a residency approximation that is
over-strict for a Canarias, Ceuta or Melilla issuer.

## Verification

The wiring assertions:

    uv run --no-sync pytest -q -p no:randomly -n 0 src/cadrumo/entrypoints/cli/tests/test_invoice_simplificada_advisory.py
    4 passed in 7.02s

The option is genuinely optional on the live surface, which the widened type
alone did not achieve:

    uv run --no-sync aeat app ledger invoice add --help
    --counterparty-nif <str>

## Notes

The Step's stated blocker - that the creation flow accepted neither an invoice
class nor an optional tax id - was still true when this ran, so it was closed
here rather than assumed resolved by the catalogue retirement.

Tests pin the WIRING rather than the predicate's truth table, which is covered
beside the predicate: that the builder delegates instead of re-deriving the
rule, that it exits before any profile read when an id is present, and that it
degrades to silence rather than a false claim when no profile resolves.
