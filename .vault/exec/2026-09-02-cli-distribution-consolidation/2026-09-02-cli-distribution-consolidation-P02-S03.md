---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:a0f859fd4863c3b6ceaca71df9f614bc6d77fd1e6cf68f5389cbdf75eeacddfb'
step_id: 'S03'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Publish an initial reservation for the primary distribution name

## Scope

- `pyproject.toml`

## Changes

- `verify:` `curl -s -o /dev/null -w '%{http_code}' https://pypi.org/pypi/cadrumo/json` -> `404`

## Notes

The reservation is held by a PyPI pending publisher rather than by an uploaded
distribution, so no path in this tree changed and the index still reports 404 for the
name - the expected observable state, because a pending publisher reserves a name
without creating a project. The binding claims owner `nevenincs`, repository `cadrumo`,
workflow `publish.yml` and environment `pypi`. The `pypi` deployment environment was
absent from the repository and was created; without it the publish job claims an
environment the OIDC token cannot attest.
