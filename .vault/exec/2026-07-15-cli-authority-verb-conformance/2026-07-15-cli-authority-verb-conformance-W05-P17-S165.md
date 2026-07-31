---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:b47b86012b40672107aad3fe28b8194587f36b1f735938b5134e975deea82edc'
step_id: 'S165'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Rewrite ledger evidence guidance to separate attach from invoice-only link

## Scope

- `docs/how-to/ledger-evidence.md`

## Description

- Read what `ledger link` and `ledger attach` each actually do from the live
  CLI.
- Retitle the attach procedure, which was headed with the other verb's name.
- State the distinction and the invoice-id trap at the point of confusion.

## Outcome

SATISFIED. The page separated the two operations in its prose but not in its
headings, which is the half a scanning reader acts on.

The section demonstrating `attach` was headed "Link an evidence record to a
transaction". An operator skimming for that heading would reach for
`aeat app ledger link`, a different verb with a required `--invoice-id` and no
evidence role at all. The heading now says Attach.

The distinction is stated where it can be acted on wrongly: `attach` carries
the evidence document, while `link` binds the transaction to an entry in the
enriched invoice catalogue. The CLI itself already makes this distinction - the
link verb's own help redirects to attach for purchase-invoice evidence - so the
page was the only surface where the two blurred.

One further trap is now documented because the live help warns about it and the
page did not: the `--invoice-id` that `link` requires comes from an imported,
reconciled, or `invoice catalogue create` entry, and is NOT the id that
`aeat app ledger invoice add` prints. Following the page without that sentence
produces a refusal an operator cannot diagnose.

Gates at HEAD `ec62e04591f495a4553abd9da23b0a28766938c8`:

- `uv run --no-sync pytest dev/docs/tests/test_sequence_contract.py
  src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py
  -m "" -n0` collected 362 cases and exited `362 passed in 7.89s`. The
  conformance suite resolves every command these pages cite against the live
  Click tree, so a spelling error here is a hard failure rather than a silent
  dead instruction.

## Notes

The page's other content was already accurate, including the positional path
argument on `evidence add` and the refusal behaviour for a second
purchase-invoice record.
