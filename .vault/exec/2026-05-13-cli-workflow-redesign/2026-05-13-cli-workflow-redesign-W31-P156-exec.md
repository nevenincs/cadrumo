---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W31.P156'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W31.P156`

Landed the backend wiring for the domain-harvest-normatives ADR.
Two thin Typer adapters expose the already-shipped
`aeat.domain.normatives` and `aeat.domain.manuals` APIs under
`aeat app registry`.

- Created: `src/aeat/entrypoints/cli/_registry_corpus.py`
- Modified: `src/aeat/entrypoints/cli/registry.py`
- Modified: `src/aeat/entrypoints/cli/_stdio.py`

## Description

Public CLI surface added to `aeat app registry`:

- `aeat app registry citations list [--tag TAG]` — list the
  normatives codified in the legal corpus, with an optional
  tax-domain tag filter.
- `aeat app registry citations show NORMATIVE_ID [--articulo NUM]`
  — show one normative's metadata and, optionally, one cited
  article rendered through `cite()`.
- `aeat app registry citations verify` — run
  `verify_catalogue()` and emit the structured issue report.
  Resilient against corpus drift: a strict-schema load failure
  surfaces as a `parse_error` issue rather than crashing.
- `aeat app registry manuals list [--manual ID] [--year YYYY]`
  — walk the manuals corpus root and list discovered parts.
- `aeat app registry manuals show --manual --year --part
  [--section ID]` — show a manual structure and optionally one
  section by id.
- `aeat app registry manuals rules --manual --year --part
  [--kind KIND]` — list `Rule` records, optionally filtered by
  `RuleKind`. The CLI validates `--kind` against the closed
  `RuleKind` Literal alphabet at the boundary, raising
  `typer.BadParameter` on unknown values.
- `aeat app registry manuals verify --manual --year --part` —
  run `verify_manual_dir()` and emit the issue report.

Every command honours the root `--format json|text` contract via
`_emit(ctx, payload, lines)`. Reads-only — no bucket events, no
persistence side-effects.

Logging discipline: the strict-load fallback in
`verify_citations_cmd` uses `_LOGGER.warning(...)` with structured
`extra` context so the swallow is observable. Similarly, the
`_stdio.py` reconfigure helpers now emit `_LOGGER.debug(...)` when
a stream declines mid-run encoding changes — never a silent
`except Exception: pass`.

Closed plan rows: `W31.P156.S0931`, `W31.P156.S0932`,
`W31.P156.S0933`, `W31.P156.S0934`, `W31.P156.S0935`,
`W31.P156.S0936`.

## Tests

`uv run --no-sync pytest
src/aeat/entrypoints/cli/test_registry_corpus.py
src/aeat/entrypoints/cli/test_stdio.py -q` — 16 / 16 pass.
