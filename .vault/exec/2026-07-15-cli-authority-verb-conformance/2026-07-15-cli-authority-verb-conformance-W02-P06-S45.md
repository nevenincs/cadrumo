---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S45'
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
     The S45 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Prove provider and all-provider deletion leave unrelated bucket session files byte-identical and ## Scope

- `src/cadrumo/application/auth/tests/test_sessions_storage_state_paths.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove provider and all-provider deletion leave unrelated bucket session files byte-identical

## Scope

- `src/cadrumo/application/auth/tests/test_sessions_storage_state_paths.py`

## Description

- Add two real-behavior tests proving a provider-scoped logout and an all-provider reset in one bucket leave an unrelated bucket's on-disk session storage byte-for-byte identical.
- Create two independent profiles, each with the certificate provider configured and a real persisted browser session in its own encrypted bucket storage.
- Fingerprint the unrelated bucket's entire on-disk directory tree, run the auth deletion in the first bucket, and assert the unrelated bucket's tree hash is unchanged while the first bucket's own session was actually removed.
- Reconfirm the unrelated bucket's session still resolves after the operation.

## Outcome

Focused suite green: `uv run --no-sync pytest src/cadrumo/application/auth/tests/test_sessions_storage_state_paths.py -q` reports 8 passed (6 prior path-composition tests plus the two new cross-bucket byte-identity proofs). Ruff clean. The tests use real isolated profile storage roots, real encrypted secure-object session persistence, and the real `logout_operator_auth` / `reset_operator_auth` services with no mocks.

## Notes

Sessions persist as encrypted secure objects inside each bucket's own storage, so the durable byte-identity claim is expressed as an unchanged fingerprint of the unrelated bucket's whole on-disk tree. The wizard catalogue import is required in the test module to seed the profile-key registry before `register_minimal_profile`. No source-code change was required; only the missing proof was added.
