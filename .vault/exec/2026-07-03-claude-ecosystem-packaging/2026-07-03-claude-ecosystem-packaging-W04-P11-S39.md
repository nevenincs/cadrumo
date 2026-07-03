---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S39'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace claude-ecosystem-packaging with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S39 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Add a LOCAL-ONLY HUMAN-GATED just publish recipe over uv publish with a scoped PyPI token, refusing to run in CI and mirroring the release-please discipline and ## Scope

- `justfile` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a LOCAL-ONLY HUMAN-GATED just publish recipe over uv publish with a scoped PyPI token, refusing to run in CI and mirroring the release-please discipline

## Scope

- `justfile`

## Description

- Add LOCAL-ONLY, HUMAN-GATED `publish` and `publish-data` recipes over `uv publish` in unix and windows variants, matching the release recipes' house style.
- Gates, each proven to exit 1: refuse when `CI`/`GITHUB_ACTIONS` is set; refuse without the literal `yes-publish-to-pypi` confirmation argument; refuse without `UV_PUBLISH_TOKEN`; refuse on a dirty tree; `publish` additionally requires HEAD to carry the `v<version>` tag matching `pyproject.toml`.
- Fresh `uv build` into `var/release/dist` (`dist-data` for the companion) before upload.
- Commit `e6027f813a`.

## Outcome

- Publication exists as a policy-clean lane: no CI, no stored tokens, human confirmation mandatory — extending the accepted release-please LOCAL-ONLY discipline to PyPI upload.

## Notes

Executed inline by the coordinator during the account rate-limit window (executor fleet paused); all three refusal gates verified live (`exit=1` each).
