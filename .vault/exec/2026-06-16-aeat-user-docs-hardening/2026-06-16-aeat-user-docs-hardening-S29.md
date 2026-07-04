---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S29'
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
     The S29 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden review-with-google-sheets.md and ## Scope

- `docs/how-to/review-with-google-sheets.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden review-with-google-sheets.md

## Scope

- `docs/how-to/review-with-google-sheets.md`

## Description

- Verify-close: read `review-with-google-sheets.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M19 (`config google login` hangs silently in a non-interactive shell; verify/push mis-framed as offline): the login is now documented as an interactive browser gate, and the app refuses fast with an instructive typed message on non-interactive stdin (the blocking local-server wait is bounded to 300s); the Google-session requirement for verify / push --dry-run is stated rather than framed as offline.
- Confirm the OAuth login/namespace/push flow and its auth-gated behaviour are documented.

## Outcome

- Page verified compliant at HEAD; finding M19 resolved (google login hang fixed 2026-06-19, `_oauth_flow.py` + typed error + doc clarification). Delta: none required.

## Notes

- The retained OAuth client (so a later `config google login` reconnects) is documented on purpose. CLI conformance gate green.
