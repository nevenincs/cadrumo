---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:cafbbc8a9224fa6fb22bb42dce28a4cb90f17cdc7f8f39db6d527575f8b15af9'
step_id: 'S09'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Move the sync calc locale keys to the new namespace in all four catalogues

## Scope

- `src/cadrumo/locales/`

## Changes

- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `M` `src/cadrumo/entrypoints/cli/_config/_google.py`
- `M` `src/cadrumo/application/export/_google_operation.py`
- `verify:` `dev.locales scaffold --check` -> `pass`

## Notes

The parity gate surfaced three reference classes the moved files did not carry:
four orphaned shared option constants in `_google_command_specs.py`, a live
cross-family reuse of the export capability key by `sync probe` and `sync push`
(rehomed to `cli.config.google.export_capability_disabled`), and two prose
references in `application/export/_google_operation.py`.
