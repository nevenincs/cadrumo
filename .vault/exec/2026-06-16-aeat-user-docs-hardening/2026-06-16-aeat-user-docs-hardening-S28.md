---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S28'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace aeat-user-docs-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S28 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden review-queue.md and ## Scope

- `docs/how-to/review-queue.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden review-queue.md

## Scope

- `docs/how-to/review-queue.md`

## Description

- Verify-close: read `review-queue.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M18 (page promised JSON with legal_refs but offered none; unknown `--kind` gave a bare "value invalid"): JSON is now documented via the global `aeat --format json` flag placed before the command, and the page lists the accepted `--kind` tokens (`ledger_transaction`, `purchase_invoice_evidence`, `modelo_finding`, ...); the CLI now names the accepted set on a bad `--kind` (the instructive-gate fix per aeat-architecture-boundaries).
- Confirm finding m17 (`<profile-id>` placeholder literal in the Bucket cell) is resolved: the intentional paste-safety redaction is kept and the redundant column dropped.

## Outcome

- Page verified compliant at HEAD; findings M18 and m17 resolved (2026-06-19 documentation + app fixes). Delta: none required.

## Notes

- The global-JSON-flag position is the same S-DRIFT meta-finding fix shared with verification-reports (M8). CLI conformance gate green.
