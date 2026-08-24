---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:d411dc7561e15c0da0f6e50242361c65fc98a6ed4ea353f3570dfc43e381ddac'
step_id: 'S239'
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
     The S239 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Add a central path-specific golden mask for only the profile-delete result fingerprint digest, retain generic digest visibility, and prove the mask is exactly the fresh-sandbox residual through real sequence replay and ## Scope

- `src/cadrumo/core/observability/ and dev/docs/sequences/ and dev/docs/tests/test_sequence_goldens.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a central path-specific golden mask for only the profile-delete result fingerprint digest, retain generic digest visibility, and prove the mask is exactly the fresh-sandbox residual through real sequence replay

## Scope

- `src/cadrumo/core/observability/ and dev/docs/sequences/ and dev/docs/tests/test_sequence_goldens.py`

## Description

- Add a command-bound, exact-path golden mask for the destroyed profile fingerprint digest.
- Preserve generic digest and sibling fingerprint visibility through direct substrate tests.
- Execute the real documented logout/delete sequence twice in fresh sandboxes and pin its sole residual path.
- Prove file-count and byte-count tampering remains a comparison failure.
- Run focused observability, comparison, real replay, Ruff, ty, and independent formal review gates.

## Outcome

The central golden substrate now masks only `config.profile.delete` at
`result.fingerprint.digest`. The profile-delete sequence refreshes and checks
cleanly even though every fresh encrypted sandbox produces different destroyed
bytes, while every sibling field remains under exact comparison. Formal review
passed with no findings.

## Notes

The first unmasked refresh correctly exposed this digest as the only remaining
fresh-sandbox flap. No per-sequence mask parameter was added, and the committed
golden remains owned by the sequence refresh CLI.
