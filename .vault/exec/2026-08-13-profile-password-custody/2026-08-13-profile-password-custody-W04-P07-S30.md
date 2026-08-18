---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:ffcc2fd5e0a3d1fc6bb5233e84cc8dc8c766b1d91bc9b33aace40be460824798'
step_id: 'S30'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S30 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Have Terra XHigh collapse the forwarding profile-custody port into one canonical route to the session and custody surface, making that route exclusive so no application module reaches the adapter package by a second path, and removing the mirror protocols and delegate wrappers that duplicate names already owned elsewhere and ## Scope

- `src/cadrumo/application/profile_custody/ and src/cadrumo/application/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Terra XHigh collapse the forwarding profile-custody port into one canonical route to the session and custody surface, making that route exclusive so no application module reaches the adapter package by a second path, and removing the mirror protocols and delegate wrappers that duplicate names already owned elsewhere

## Scope

- `src/cadrumo/application/profile_custody/ and src/cadrumo/application/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

The forwarding port is dissolved in one atomic relocation (commit `3f1a947674`): all seventy-five names the port exported now live in `application/user_profile/_custody_ports.py` (protocols, the local-record delegates and factories, the pure helpers, the composition ops and the session forwards), promoted through the user-profile facade `_LAZY_EXPORTS`. The five dynamic `import_module("cadrumo.adapters.persistence.storage.custody")` reaches became static facade imports; the thirty-three consumer files repoint at the facade; the port package, its tests and its API stub are deleted; the hard-cutover absence gate's declared open violation moved from `profile_custody/__init__.py` to `user_profile/_custody_ports.py` (one static master-key import, reason text updated) and the gate passes 12/12. The error registry binds `ProfileRecordCryptoError` under its new module path.

Two executor runs died mid-step (prompt overflow) after converting the dynamic imports and moving the first helper tranche; the sweep, facade promotion and deletion were completed by the lead session.

## Notes

Gates: ruff clean on the touched set; collect-only on `src/cadrumo/application/` clean (8703 collected, 0 errors); affected suites green except two pre-existing classes: the concurrent authority-grade registry sweep's tree-wide `RegistryValidationError` red (S195's documented external blocker), and the UUID-harness fixture errors from commit `58cd742301` (readable bucket ids through `UUID(str(profile_id))` in `profile_capsule.py:300`) — routed to S106. `_custody_ports.py` was rebuilt by concatenation and re-linted; facade duplicate keys deduplicated against the pre-existing entries (`export_profile_recovery_artifact` stays on `._recovery_custody`).
