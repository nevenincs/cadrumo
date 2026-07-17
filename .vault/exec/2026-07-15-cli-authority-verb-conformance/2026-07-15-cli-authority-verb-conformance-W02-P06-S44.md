---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S44'
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
     The S44 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Prove reset removes provider state, sessions, locks, registrations, and secrets only for the explicit target and ## Scope

- `src/cadrumo/application/auth/tests/test_operator.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove reset removes provider state, sessions, locks, registrations, and secrets only for the explicit target

## Scope

- `src/cadrumo/application/auth/tests/test_operator.py`

## Description

- Add a real-behavior test proving a provider-scoped `reset_operator_auth` clears only the target provider's artefacts.
- Configure the certificate provider with a real persisted session, an acquisition lock, a named source registration, and its secure-storage secret; place an unrelated Cl@ve Móvil session and acquisition lock in the same bucket.
- Reset the certificate provider and assert every certificate artefact is removed (session, lock, source registration, secure-storage secret, provider configuration) while the Cl@ve Móvil session and lock survive untouched.
- Assert the returned result counts (`removed_sessions`, `cleared_locks`, `removed_certificate_sources`, `removed_certificate_secrets`, `cleared_provider_configuration`) match the target-only cleanup.

## Outcome

Focused suite green: `uv run --no-sync pytest src/cadrumo/application/auth/tests/test_operator.py -q` reports 28 passed (27 prior plus the new target-scoped reset proof). Ruff clean on the file. The test exercises real encrypted secure storage, real acquisition lock files, and the real `reset_operator_auth` application service with no mocks, stubs, or monkeypatching.

## Notes

The provider-scoped session and lock cleanup is driven by the resolved auth operation scope (`provider_ids`), so an unrelated provider's session and acquisition lock in the same bucket are never in scope. No source-code change was required for this step; only the missing real-behavior proof was added.
