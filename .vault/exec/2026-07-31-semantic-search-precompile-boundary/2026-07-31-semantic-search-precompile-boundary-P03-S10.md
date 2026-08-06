---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:efe5b34fc667017b18789027c180669e11a709cee9ade0397fc4d52d12cd5740'
step_id: 'S10'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
---

# Sweep every remaining install hint naming the retired extra from production strings, the extras-reporting half of this step being vacated by ADR Update 1 because config check never named a search extra

## Scope

- `src/cadrumo/`

## Description

- Sweep production strings under `src/cadrumo/` for install hints naming the retired `search` extra (`pip install`/`uv add` guidance, package-name references).
- The original row also instructed dropping the search capability from the `config check` extras-reporting surface; that half is vacated (ADR Update 1, point 1): `_check_cli.py` and `_check_payloads.py` never named a search extra, confirmed independently three times at HEAD (an executor read, a read-only inventory, and the ADR's own probe). The row was re-worded to its real half (the install-hint sweep) so no future reader fabricates the missing work or falsely marks it done under the original wording.

## Outcome

Landed as part of commit `13935ef3a2` "build(search): drop the search extra and its dependency refusal" (`THIRD_PARTY_NOTICES.md`, `dev/packaging/smoke_core.py`, and the deleted install-hint-bearing surfaces named there). Independently re-confirmed at current HEAD by this record: `rg -i "search"` over `src/cadrumo/entrypoints/cli/_config/_check_cli.py` and `_check_payloads.py` returns no match, and a broader `rg` for `cadrumo[search]` / `[search]` install-hint patterns and `extra.*=.*"search"` across `src/cadrumo/` returns no match. The step, as re-worded by ADR Update 1, is fully satisfied.

## Notes

None. The step's original wording named a subject (`config check` extras-reporting) that never existed in the codebase; ADR Update 1 vacated that half and re-scoped the row rather than the row being silently marked done against a fabricated action.
