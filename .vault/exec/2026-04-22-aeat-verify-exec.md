---
tags:
  - '#exec'
  - '#aeat-verify'
date: '2026-04-22'
modified: '2026-04-22'
related:
  - "[[2026-04-24-aeat-verify-plan]]"
  - "[[2026-04-25-aeat-verify-exec]]"
  - "[[2026-04-25-aeat-verify-audit]]"
---



# `aeat-verify` `cleanup` `manuals-stub-cleanup`

Final stub-cleanup pass for `aeat.domain.manuals`: the rebase-swap placeholders in
`src/aeat/domain/manuals/_stubs.py` outlived their sibling branches. `aeat.corpus`
was demolished in this PR and never rejoined the tree, and the four
Protocols inside `_stubs.py` were never imported anywhere — the only live
symbol was `MODELO_CASILLA_PATTERN`, anchored to a hardcoded three-digit
regex instead of the real `aeat.domain.modelos.ModeloCode` enum. This pass deletes
the dead code and re-anchors the casilla cross-reference pattern to the
canonical modelo registry.

- Deleted: `src/aeat/domain/manuals/_stubs.py` (102 lines: four Protocols, one
  unused `stub_extracted_at()` helper, and the hand-rolled
  `MODELO_CASILLA_PATTERN` regex constant).
- Deleted: `src/aeat/corpus/` (empty residual directory left after the
  earlier deletion of the speculative subpackage).
- Modified: `src/aeat/domain/manuals/_schema.py` (folded the casilla
  cross-reference pattern inline as the private
  `_MODELO_CASILLA_PATTERN`; the `MODELO_NNN` prefix is now derived
  from `aeat.domain.modelos.ModeloCode` member values, so a new modelo cannot
  be cited from a manual rule without first being registered in
  `aeat.domain.modelos`).
- Modified: `src/aeat/domain/manuals/_fetch.py` (dropped the docstring passage
  about being rewired to `aeat.corpus.Fetcher` once `#17` lands; the
  fetcher is now described as the production path that it actually is).
- Modified: `src/aeat/domain/manuals/__init__.py` (removed the `_stubs` mention
  from the private-module enumeration in the package docstring).

## Description

The investigation traced four classes of stub:

`FetcherProtocol` — described as a placeholder for `aeat.corpus.Fetcher`.
The `aeat.corpus` subpackage was deleted earlier in this PR's
discovery-driven rewrite (recorded in the master exec summary) and is
not coming back. `FetcherProtocol` was never imported anywhere in
`src/`; deleting it is purely subtractive.

`LLMClientProtocol`, `TranslatorProtocol`, `BulkTranslatorProtocol` —
described as placeholders for `aeat.adapters.outbound.llm`. The real subpackage exists and
ships `LLMClient`, `Translator`, `BulkTranslator` — but with
fundamentally incompatible signatures (async, structured pydantic
request/response models versus the Protocols' synchronous string-only
shapes). The user mandate explicitly said "if shapes mismatch, keep the
local Protocols but drop the framing"; however, none of the three
Protocols were imported anywhere in `src/` either, so they are dead
code irrespective of compatibility. Deletion is safe.

`MODELO_CASILLA_PATTERN` — the only live symbol from `_stubs.py`,
consumed by `_schema.py` to validate `Rule.references_casillas`
entries (`MODELO_NNN[:CASILLA]` strings). The previous shape allowed any
three-digit modelo number, which would silently accept references to
modelos the project does not track. The replacement builds the
alternation group from `aeat.domain.modelos.ModeloCode` member values, so the
regex is now strictly anchored to the closed twenty-one-modelo registry.
The casilla suffix remains a free-form alphanumeric token because
casillas may be cited from a manual before the casilla catalogue is
populated. The constant is also renamed to the underscore-prefixed
`_MODELO_CASILLA_PATTERN` since it is purely an implementation detail
of `_schema.py` and no other module references it.

`stub_extracted_at()` — a deterministic UTC datetime helper documented
as "kept for follow-up tests". The phase-1 review record explicitly
flagged it as never invoked. Deleted.

The `_fetch.py` and `__init__.py` docstring updates align the prose
with the new tree shape: there is no future rewire to
`aeat.corpus.Fetcher`, and there is no `_stubs` private module to
warn callers about.

## Tests

Quality gates after the cleanup:

- `uv run ruff check src/aeat/domain/manuals/` — clean.
- `uv run ty check src/aeat/domain/manuals/` — clean.
- `uv run pytest src/aeat/domain/manuals/ -m unit -q` — 38 / 38 pass.
- `uv run pytest src/aeat/entrypoints/cli/test_manual_cli.py -m unit -q` — 5 / 5
  pass (the CLI integration tests that exercise `aeat.domain.manuals` exports
  still go green).
- `uv run ruff check src/aeat/` — clean.
- `uv run ty check src/aeat/` — clean.
- Forbidden-phrase grep over `src/aeat/domain/manuals/`
  (`aeat\.corpus|rebase-swap|in flight|when.*lands`) returns zero hits.

The casilla-pattern narrowing is non-breaking: every existing fixture
casilla reference (`MODELO_303:01`, `MODELO_130:01`, `MODELO_130:07`
in `test_loader.py` and `test_schema.py`) continues to validate
because all three modelo codes are members of the canonical
`ModeloCode` enum. The pattern's negative test
(`test_schema.py::"not-a-modelo-id"`) still rejects, because the
new alternation still requires the `MODELO_` prefix.

Cross-reference: `[[2026-04-25-aeat-verify-exec]]` records the broader
PR-wide stub demolition; this step is the manuals-only follow-up
identified during the `[[2026-04-25-aeat-verify-audit]]` pass.
