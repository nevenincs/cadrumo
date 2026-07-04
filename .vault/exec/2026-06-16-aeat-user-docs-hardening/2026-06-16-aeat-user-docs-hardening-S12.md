---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S12'
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
     The S12 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden filing-readiness.md and ## Scope

- `docs/how-to/filing-readiness.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden filing-readiness.md

## Scope

- `docs/how-to/filing-readiness.md`

## Description

- Verify-close: read `filing-readiness.md` in full against the hardening standard and confirm its audit findings are resolved at HEAD.
- Confirm the readiness/dependencies/history/compare/project commands are documented with real flags and resolve against the live CLI; the `--ccaa` usage is the comunidad autónoma of tax residence (correct usage, not a single-group term).
- Confirm the extrapolation-flag caveat and the withholdings-default-to-zero caveat are stated so a reader does not over-trust a partial-quarter projection.

## Outcome

- Page verified compliant at HEAD. Delta: none required this pass.
- Imperative headers, per-command examples, explicit "read the extrapolation flag" caution, resolving cross-links.

## Notes

- Audit findings m9 (`--binding KEY=VALUE` literal placeholder) and m10 (`overview calendar` on a minimal profile) are doc-clean here: `KEY=VALUE` and `<...>` are used consistently as obvious placeholders across the how-to surface, and m10's calendar behaviour is an app/other-page concern. CLI conformance gate green.
