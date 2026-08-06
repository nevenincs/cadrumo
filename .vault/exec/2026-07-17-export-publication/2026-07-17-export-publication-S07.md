---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:274c10183b1d7bf32f7af4b178fc508b41a5989e1b95a9cdf1cd787f5e504575'
step_id: 'S07'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

# Route both config profile export and subject-access-request through the sole portable-export application service and remove direct serialization, target writes, completion events, and static SAR category ownership from the CLI

## Scope

- `src/cadrumo/entrypoints/cli/_config/_profile_export.py`

## Description

- Confirm both the profile export and the subject-access-request commands already route through the sole `export_profile_bundle` service and own no serialization, target write, or completion event; the lifecycle event write on the CLI is import-only.
- Rewrite the subject-access catalogue notice to stop enumerating a hand-maintained personal-data category list, pointing instead at the derived `data_categories` the export service computes from the bundle schema and carried registry namespaces (already carried on the response and in the notice context).
- Update the catalogue notice prose in the en, es, ca, and hu catalogues through the locales CLI.

## Outcome

The CLI no longer owns a static category list; the authoritative derived set rides on the response. Locale parity, honesty, drift-check, and the subject-access / export CLI suites pass. Committed in `c59e862ad7`.

## Notes

The plan's declared file `_profile_export.py` does not exist; the export and subject-access commands live in `_config/_profile_bundle.py` (with import). The substantive change was made there to avoid a file split touching the peer-hot `_config/__init__.py` registration wiring. The filename divergence was flagged to the coordinator.
