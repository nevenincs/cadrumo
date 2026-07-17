---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S52'
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
     The S52 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Prove register, select, check, status, test, and login consume the same resolved certificate bytes and ## Scope

- `src/cadrumo/application/auth/tests/test_certificate_sources_check.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove register, select, check, status, test, and login consume the same resolved certificate bytes

## Scope

- `src/cadrumo/application/auth/tests/test_certificate_sources_check.py`

## Description

- Confirm register, select, check, status, test, and login all consume the same resolved certificate bytes and the same secure-storage secret.
- Confirm a selected named source with no bound secret fails closed (resolves `password=None`) and never inherits an unrelated global Settings password across the resolver, central provider factory, status, test, preflight, and login surfaces.
- Confirm renewing the selected source and cross-bucket / cross-root routing keep every consuming surface on the same resolved bytes.

## Outcome

Verified complete against the committed tree. `test_certificate_sources_check.py` proves the active-credential resolver, `check`, `auth status`, `auth test`, the central provider factory, live preflight, and `login` all agree on the selected source's path and secure-storage secret, with a deliberately-wrong global password unable to open a named source and a secretless named source failing closed. The file is green in the focused run (part of the 99-passed application-auth suite).

## Notes

The shared-resolution parity proofs landed in the W02.P07 credential-unification wave (commits `f5273bda59`, `84c435bb94`, and the in-flight freeze snapshots); this step is closed as verified-complete with its real-behavior parity and fail-closed gates green.
