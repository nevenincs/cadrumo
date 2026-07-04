---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S07'
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
     The S07 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden classify-with-llm.md and ## Scope

- `docs/how-to/classify-with-llm.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden classify-with-llm.md

## Scope

- `docs/how-to/classify-with-llm.md`

## Description

- Verify-close: read `classify-with-llm.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding m19 (documented LLM preview fields not surfaced): the page documents the text preview fields (classification, category, confidence, reason) AND the machine-readable record - provider, `provenance` (`llm:<provider>`), `persisted` (`false` in preview) - via the global `aeat --format json` flag placed before the subcommand.
- Confirm finding m18 (`--nif` silently ignored) is not applicable to this page: it addresses the transaction by the positional id and never documents `--nif`; the real identity flag is `--tax-id` (re-diagnosed as an app-side no-code-change concern).
- Confirm the single-transaction limit, the `--saturate` tax-field flow, the passphrase prereq, and the never-contact-AEAT boundary are documented.

## Outcome

- Page verified compliant at HEAD; finding m19 resolved via the documented global-JSON provenance/persisted fields. Delta: none required.

## Notes

- Residual m18 is APP-side (no-profile generic "No such option" does not suggest `--tax-id`) - a CLI-global concern, out of documentation scope. CLI conformance gate green.
