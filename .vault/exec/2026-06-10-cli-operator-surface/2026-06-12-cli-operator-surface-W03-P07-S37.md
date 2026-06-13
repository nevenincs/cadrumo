---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S37'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
  - '[[2026-06-10-cli-operator-surface-adr]]'
---

# W03.P07.S37 - profile-history bucket noun retirement

## Scope

- `src/aeat/entrypoints/cli/_config/_bucket_history.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`
- `docs/how-to/profile-setup.md`
- `docs/cli`
- `dev/docs/cli_reference.py`

## Description

- Changed `aeat config profile history` to expose a `PROFILE` argument instead of `BUCKET_ID`.
- Resolved the operator profile token through workflow profile lookup, then passed the resolved bucket id to `BucketEventHistoryRepository`.
- Kept the stable JSON envelope key `config.bucket.history` as a machine API carve-out while rendering text output as `config.profile.history`.
- Updated locale help and the profile setup guide so operators use profile names rather than bucket ids.
- Regenerated the generated CLI reference and taught the CLI reference generator the stable-token override.

## Outcome

`config bucket` remains retired. Operators now browse history with `aeat config profile history <profile-name>`, while internal event-history reads still use the immutable bucket id after application/workflow resolution.

## Notes

`python -m aeat.locales scaffold --check` and `python -m aeat.locales audit` still fail on the unrelated pre-existing extra key `cli.overview.warning.censo_enrolment_unverified` in all four locale catalogues. The profile-history locale keys themselves are present in all four catalogues.
