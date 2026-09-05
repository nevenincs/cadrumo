---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:8e6abf895e046a33f84fcb752fd560f006979b902e8cd41ed9201a626f112c3f'
step_id: 'S25'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Establish whether the enum-member tier is dead code or an instrument gap: 204 of 305 enum-member findings carry a literal value present in shipped registry declarations, 174 of them in one module bound by value in the Modelo 200 projection_endpoints declarations, and fix the binding rule tightly enough that it cannot suppress a real finding

## Scope

- `dev/audit/unreachable_code.py`

## Changes

- `M` `dev/audit/unreachable_code.py`
- `M` `dev/audit/tests/test_unreachable_code.py`
- `verify:` `uv run --no-sync pytest -q dev/audit/tests/test_unreachable_code.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --json` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/audit` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unconsumed_export_ratchet` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_ratchet` -> `fail, peer-owned`

## Notes

The tier was an instrument gap, not dead code. `_DATA_SHAPED_KINDS` already
admitted enum members and the data consult already read the registry and locale
payloads, but it matched the member NAME while a declaration addresses a StrEnum
member by its VALUE, so no binding could ever be seen. The member's declared
literal is now carried on the definition record and consulted.

The binding rule is deliberately stricter than the existing token match and
kept separate from it, so the name match keeps its reach. A first attempt reused
the loose regex tokens over the raw payload text and cleared 191 findings, but
inspection showed 15 of those rested on a single short word and at least seven
were prose: `flows.BACK` cleared because a registry sentence reads "created and
read back", `capabilities.PROCESS` because another reads "Another process is
acquiring AEAT", and `records.CONTRACT` on a comment. Suppressing a live finding
is worse than over-reporting it, so the accepted rule parses the payload and
counts only a complete mapping key or a complete string value. That clears 175
with no single-short-word clear remaining.

Symbol findings fall 1322 to 1147. The reduction is in the UNGATED population:
`dev/quality/unused_symbol_ratchet.py` ratchets the `exact` tier only, and enum
members are `name-match-data`, so no baseline moved and none was rewritten. No
threshold, exclusion, baseline, skip or allowlist was changed.
