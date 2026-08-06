---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:3f2c87c4fef46aa7fcb2f2dcd3c67928613f3aecbb39cb69653c9b257f5e2dad'
step_id: 'S39'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

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
