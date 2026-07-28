---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S166'
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
     The S166 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Rewrite bank-import examples to separate evidence attach from invoice link and ## Scope

- `docs/how-to/import-bank-statements.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rewrite bank-import examples to separate evidence attach from invoice link

## Scope

- `docs/how-to/import-bank-statements.md`

## Description

- Check the bank-import page's treatment of invoice records against its
  treatment of evidence attachment.

## Outcome

SATISFIED by verification; no change needed.

The page already separates the two concerns structurally rather than only in
prose. Invoice records have their own section, which frames them as tracking
whether an invoice exists separately from the bank movement, distinguishes
received from issued, and cross-links to the evidence guide for the full
workflow. Evidence attachment has a separate section correctly titled "Attach
evidence to a transaction" and demonstrates the attach verb.

That heading is the detail worth recording, because the sibling evidence page
had the same content under a heading naming the OTHER verb, and that was a real
hazard: a reader skimming headings reaches for `ledger link`, which requires
`--invoice-id` and carries no evidence role. This page did not have that
defect. Fixing the sibling and confirming this one are the same check applied
twice, and only one needed work.

Gates at HEAD `1745d216608445450dedd61fdaa0a482d0ccb1e6`:

- `uv run --no-sync pytest dev/docs/tests/test_sequence_contract.py
  src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py
  -m "" -n0` collected 362 cases and exited `362 passed`. The page's captured
  sequences resolve, including the ledger import verb in its `--file`
  pull-and-file form and the invoice view with its `--kind` discriminator.

## Notes

Nothing to fix. Recorded with its evidence so the closure is checkable rather
than asserted.
