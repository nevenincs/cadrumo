---
tags:
  - '#research'
  - '#docs-tooling-separation'
date: '2026-06-14'
modified: '2026-06-14'
related:
  - '[[2026-06-04-aeat-cli-userdocs-hardening-plan]]'
  - '[[2026-06-14-aeat-cli-userdocs-hardening-audit]]'
---

# `docs-tooling-separation` research: `terminology package separation from production`

## Problem

The userdocs-hardening step `W07.P14.S59` calls for moving documentation
generators, build helpers, and documentation verifier tests out of the
production `src/aeat/` package (and any unsupported `scripts/` path) into
supported contributor tooling. Most of that separation already holds: the doc
generators and build helpers live under `dev/docs/` (the CLI-reference
generator, pagefind, glossary, apidocs, the single-page build, the
sphinx-autobuild serve recipe), and no `scripts/` path exists. The peer-relocated
`_doc_reference.py` is already at `dev/docs/cli_reference.py`.

One residual remains in the production package: the `src/aeat/terminology/`
package and its `src/aeat/_data/terminology/` authoring tree. The terminology
package is doc-build tooling (it compiles the Terminology Handbook that feeds the
offline docs search and the generated glossary) with zero production runtime
importers, yet it ships inside the production wheel.

## Findings

### F1 - No production runtime importer (separation is import-safe)

No module under `src/aeat/` outside the terminology package and outside tests
imports `aeat.terminology`. The runtime CLI entrypoint tree
(`src/aeat/entrypoints/`) does not import it. Every tree-wide `aeat.terminology`
reference is an authoring-data comment, a docstring cross-reference, a `dev/`
consumer, or a test. The package is therefore not wired into any `config`/`app`
runtime path.

### F2 - The package depends up into production `core`

The terminology modules import `aeat.core.*` (`STRICT_FROZEN_CONFIG`,
`external_constants`, `i18n.tr`, `resources.bundled_path`, `topics`, `time`). It
is not leaf tooling: relocating it to `dev/` turns each `from ..core...` into
`from aeat.core...`. That resolves, because `dev/` already imports `aeat.*`, but
it is a real import-shape change on the moved modules, not a verbatim move.

### F3 - The authoring data ships in the production wheel

`[tool.hatch.build.targets.wheel] packages = ["src/aeat"]` ships everything under
`src/aeat`, including `src/aeat/_data/terminology/`. The loader reads it through
`aeat.core.resources.bundled_path("terminology", ...)`, which resolves
`files("aeat")/_data/terminology`. The tripwire `test_wheel_bundles_corpus_and_registry`
asserts every tracked file under `src/aeat/_data` (corpus, registry, terminology)
appears in the wheel. Corpus and registry are runtime tax-reference data;
terminology is doc-build-only, so its presence in the wheel is incidental.

### F4 - The relevance ranking references the terminology API page

`src/aeat/_data/terminology/relevance/relevance.json` carries shipped offline-search
ranking entries that target the terminology code's API page
(`api/aeat.terminology.html`, `code:aeat.terminology`). Removing the terminology
code from the production package removes its autodoc stubs
(`docs/api/aeat.terminology*.rst`), so those ranking targets would dangle. The
relevance mapping is laundered search data governed by `shipped-search-licence-clean`.

### F5 - Tree-scanning conformance gates carry terminology expectations

Three gates that scan `src/aeat/` would change behaviour when terminology leaves:
`test_docstring_return_type_links` has hardcoded `aeat.terminology._*` expected
rows; `test_exception_base_hygiene` allowlists `aeat.terminology._errors.TerminologyError`;
`test_wheel_bundles_corpus_and_registry` lists `src/aeat/_data/terminology`. The
codebase-size budget and docstring-core-struct gates take terminology out of
their input set.

### F6 - Consumers, tests, CLI, and stubs to update

About ten `dev/docs/` importers and tests reference `aeat.terminology`. The
package owns a `python -m aeat.terminology` CLI (`__main__.py`; no
`[project.scripts]` console-script entry). Fourteen `docs/api/aeat.terminology*.rst`
autodoc stubs plus the `aeat.rst` toctree node are generated and must be
regenerated. Hardcoded `src/aeat/_data/terminology` path strings exist in a few
`dev/docs/` modules and the `curation-ratchet.json` source string.

## Options

- **Option D1 - move code, keep shipped data.** Relocate the terminology package
  code and tests to `dev/docs/`, rewrite its `core` imports to absolute, update
  the consumers, gates, CLI invocation strings, and regenerate API stubs. Leave
  `src/aeat/_data/terminology/` in place; the relocated loader keeps reading it
  through `bundled_path`. Lower risk: no loader redesign, no wheel-bundle change.
  Residual impurity: doc-build-only data still ships in the wheel, and the
  relevance entries pointing at the removed API page must still be repaired.
- **Option D2 - move code and data.** Also relocate `_data/terminology/` to the
  dev tooling, repoint the loader to a dev-relative resolution, drop the
  terminology arm from the wheel-bundle tripwire, and regenerate the relevance
  ranking. Cleanest end state (the wheel carries only runtime data), but it
  touches the laundered search-ranking regeneration, which needs the dev RAG
  oracle per `shipped-search-licence-clean`.

## Recommendation

Adopt **D2** as the correct end state but sequence it so the laundered-data step
is explicit and gated: the move is only "complete" once the relevance ranking is
regenerated and re-ratified. If the ranking regeneration cannot be run cleanly in
this environment, fall back to **D1** for the code move and track the data
de-shipping plus relevance regeneration as a defined follow-up, so the production
package is at least free of the doc-build tooling code. Either way, the API-stub
removal and the dangling relevance targets must be reconciled in the same atomic
change. Decision recorded in the sibling ADR.
