---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S165'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S165 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Rewrite ledger evidence guidance to separate attach from invoice-only link and ## Scope

- `docs/how-to/ledger-evidence.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
