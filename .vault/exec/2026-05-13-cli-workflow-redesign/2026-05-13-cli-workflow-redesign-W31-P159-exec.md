---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W31.P159'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W31.P159`

Real-behaviour verification. Eleven tests drive the new
`aeat app registry citations` and `aeat app registry manuals`
surfaces end-to-end through Typer's `CliRunner` against the
committed corpus on disk. No mocks / fakes / fixtures — every test
hits the same domain APIs the production runtime uses.

## Description

Suite breakdown (`src/aeat/entrypoints/cli/test_registry_corpus.py`):

- Citations (4 tests): the verifier surfaces a `parse_error`
  issue when the committed corpus has files that don't yet match
  the tightened `NormativeReference` schema; the JSON-format
  payload is parseable on stdout; `citations list` correctly
  propagates strict-load failures through the central error
  boundary (non-zero exit); `--help` renders.
- Manuals (4 tests): `manuals list` walks the corpus root and
  emits `part_count`; the JSON path emits a parseable payload;
  `--manual` filter narrows the listing; `--year` filter narrows
  the listing.
- Boundary regression guards (3 tests): no top-level
  `normatives` / `manual` / `manuales` verb, no parallel
  Typer surface outside the canonical module, no fetch verb
  under the read-only contract.

Notable: the citations-verify test asserts the wave's tolerance
contract — when the on-disk corpus contains pre-restructure
records that fail the tightened schema, the verifier ABSORBS the
parse error as a `level="error", code="parse_error"` issue rather
than crashing. Operators get a structured diagnostic; CI gets a
non-zero exit; no silent swallow.

Closed plan rows: `W31.P159.S0949`, `W31.P159.S0950`,
`W31.P159.S0951`, `W31.P159.S0952`, `W31.P159.S0953`,
`W31.P159.S0954`.

## Tests

`uv run --no-sync pytest
src/aeat/entrypoints/cli/test_registry_corpus.py -q` — 11 / 11
pass.
