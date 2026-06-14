---
tags:
  - '#adr'
  - '#docs-tooling-separation'
date: '2026-06-14'
modified: '2026-06-14'
related:
  - "[[2026-06-14-docs-tooling-separation-research]]"
  - "[[2026-06-04-aeat-cli-userdocs-hardening-plan]]"
---

# `docs-tooling-separation` ADR: `terminology package separation from production`

## Status

Accepted.

## Context

`W07.P14.S59` requires documentation tooling to leave the production `src/aeat/`
package. The research (`2026-06-14-docs-tooling-separation-research`) found the
doc generators and build helpers already live under `dev/docs/`, with one
residual: `src/aeat/terminology/`, a doc-build package (Terminology Handbook
loader, scaffold, ratchet, seed-import, CLI) with zero production runtime
importers that nonetheless ships in the wheel. Its authoring data lives at
`src/aeat/_data/terminology/` and is read through
`aeat.core.resources.bundled_path`. Removing the package's code also removes its
autodoc API pages, which orphans two `code:` targets in the shipped relevance
ranking.

## Decision

Relocate the terminology **package code and its tests** out of the production
package into contributor tooling at `dev/docs/terminology_handbook/`. Keep the
authoring data at `src/aeat/_data/terminology/`; the relocated loader continues
to read it through `aeat.core.resources.bundled_path`, which resolves the data in
the editable/source tree the docs build runs in. This is option D1 from the
research: it removes the doc-build tooling code from the production package (the
goal of S59) at the lowest risk, without a loader redesign, a wheel-bundle
contract change, or a laundered-ranking regeneration.

Specifically:

- `git mv src/aeat/terminology dev/docs/terminology_handbook` (package, tests,
  fixtures).
- Rewrite the moved modules' `from ..core...` imports to `from aeat.core...`.
- Update every `dev/docs/` consumer and test to import the package from its new
  location.
- Move the production-CLI conformance test
  (`test_terminology_redeclaration_conformance.py`) to the dev tooling and
  repoint its import.
- Update the three tree-scanning gates: remove the `aeat.terminology._*` rows in
  `test_docstring_return_type_links`, remove the `aeat.terminology._errors`
  allowlist row in `test_exception_base_hygiene`. Leave
  `test_wheel_bundles_corpus_and_registry` unchanged (the data stays shipped).
- Regenerate the autodoc stubs (`python -m dev.docs.apidocs scaffold`), removing
  the `docs/api/aeat.terminology*.rst` orphans and the `aeat.rst` toctree node.
- Reconcile the two now-dead `code:aeat.terminology*` targets in
  `relevance/relevance.json` (remove the dead code-surface targets; this is a
  licence-clean removal of targets pointing at removed code, not new ranking
  data).
- Update the `python -m aeat.terminology` invocation strings (the
  `curation-ratchet.json` source string) to the new module path.
- Land as ONE atomic commit tagged `relocation:aeat.terminology`, with a clean
  `pytest --collect-only -q` immediately before commit per the
  relocation-atomicity rule.

## Consequences

- The production wheel no longer carries the terminology tooling **code**; the
  package boundary is cleaner and the doc-build tooling is uniformly under
  `dev/`.
- The authoring **data** still ships in the wheel (consistent with how corpus
  and registry data bundle). De-shipping the data (option D2) and the matching
  loader redesign, wheel-bundle change, and full relevance regeneration via the
  dev RAG oracle are deferred as a follow-up if the data footprint must also
  leave the wheel.
- The terminology CLI moves to `python -m dev.docs.terminology_handbook`.
- Risk: a multi-file atomic relocation in a shared worktree. Mitigation: the
  move is import-mechanical (no behaviour change), verified by clean collect-only
  plus the terminology, glossary, wheel-bundle, and the two edited tree-scan
  gates, and the apidocs drift check.
