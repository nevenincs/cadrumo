---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S07'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-evidence-atomicity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-07-17-ledger-evidence-atomicity-plan placeholders are machine-filled by
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
     The Restrict ledger link to invoice-only linkage, route it through the atomic application writer, and remove evidence-id and evidence-update result paths and ## Scope

- `src/cadrumo/entrypoints/cli/_ledger.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Restrict ledger link to invoice-only linkage, route it through the atomic application writer, and remove evidence-id and evidence-update result paths

## Scope

- `src/cadrumo/entrypoints/cli/_ledger.py`

## Description

- Remove the `--evidence-id` option from `aeat app ledger link`; make `--invoice-id` required and route the bidirectional link through the atomic `link_manual_transaction_invoice` writer landed in S01.
- Remove the evidence-update result paths: trim `LedgerLinkResult` to invoice-only metadata (operation/bucket/transaction/invoice/actor) and delete the orphaned `LedgerLinkEvidenceUpdatePayload`; update its payload contract test to assert the invoice-only shape.
- Keep the CLI's pre-write instructive invoice missing/cross-bucket gate (the operator's first instructive surface) ahead of the writer.
- Update the import-bank-statements how-to (evidence is `attach`-only; `link` is invoice-only) and delete the redundant `import-link-evidence.seq` documented-command contract (superseded by `import-attach-evidence.seq`), per the ADR's atomic doc-with-code rule.
- Land the two reviewer LOW findings in the same P03 window (separate commit `b3d8ab6b76`): builder-level split-child id-stability assertion (LOW-2) and the `BULK_CLASSIFY_ALLOWED_COLUMNS` ∩ evidence-fields = ∅ gate (LOW-1).

## Outcome

- `ledger link` is now invoice-only and routed through the single atomic writer; evidence assignment is solely `aeat app ledger attach`. Link/check verb + payload-contract suites green (11 + unit); full ledger application suite 398 passed; sequence contract/directive/build gates green; documented-command conformance green on my surface. Commit `4f8e3b0685`; findings `b3d8ab6b76`.

## Notes

- DEFERRED (locale, door-blocked): dropping the orphaned `cli.ledger.link.evidence_id_help` / `cli.ledger.link.errors.missing_target` keys and updating the `invoice_not_found` / `help` values still referencing `--evidence-id`. The four `en/es/ca/hu.yml` files carry the OPERATOR's live uncommitted P04-door (passphrase/recovery) locale WIP — disjoint keys, but the locales CLI does a whole-file read-modify-write, so a naive edit would sweep the operator's WIP. This cleanup is HELD own-keys-only until the operator commits the P04 door and the `.yml` goes clean; it then lands via `python -m cadrumo.locales`, git-diff-cached-gated to the link keys only. Until then the codebase-to-locale parity gate carries two extra owner-attributed link keys on top of the pre-existing 9-missing-key drift — a KNOWN temporary door-blocked delta, not a regression; it clears when the held cleanup lands.
