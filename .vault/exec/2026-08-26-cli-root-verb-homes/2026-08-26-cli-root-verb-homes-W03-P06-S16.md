---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:67177c10ac16951e83d3be0e7370f0f636df84f1ce69ee4b5f3343cee722977d'
step_id: 'S16'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Update the bootstrap-exempt and login-gated verb paths and resolve the stale config profile export entry

## Scope

- `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_login_gated_verbs_never_exempt.py`
- `verify:` `pytest bootstrap-exempt + login-gated gates` -> `pass`
