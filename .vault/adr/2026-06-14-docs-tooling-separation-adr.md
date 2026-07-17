---
tags:
  - '#adr'
  - '#docs-tooling-separation'
date: '2026-06-14'
modified: '2026-07-17'
related:
  - "[[2026-06-14-docs-tooling-separation-research]]"
---

# `docs-tooling-separation` ADR: `terminology package separation from production` | (**status:** `accepted`)

## Status

Accepted.

## Context

Documentation tooling must remain outside the production `src/cadrumo/`
package. The research (`2026-06-14-docs-tooling-separation-research`) found the
doc generators and build helpers already live under `dev/docs/`, with one
residual now removed: the former production terminology package was doc-build
tooling (Terminology Handbook
loader, scaffold, ratchet, seed-import, CLI) with zero production runtime
importers. Its authoring data lives at `src/cadrumo/_data/terminology/` and is
read through `cadrumo.core.resources.bundled_path`.

## Decision

Relocate the terminology **package code and its tests** out of the production
package into contributor tooling at `dev/docs/terminology_handbook/`. Keep the
authoring data at `src/cadrumo/_data/terminology/`; the relocated loader reads it
through `cadrumo.core.resources.bundled_path`, which resolves the data in
the editable/source tree the docs build runs in. This is option D1 from the
research: it removes the doc-build tooling code from the production package (the
goal of S59) at the lowest risk, without a loader redesign, a wheel-bundle
contract change, or a laundered-ranking regeneration.

Specifically:

- The tooling and its tests live under `dev/docs/terminology_handbook/`.
- Tooling imports the public `cadrumo.core.resources` boundary.
- Update every `dev/docs/` consumer and test to import the package from its new
  location.
- Move the production-CLI conformance test
  (`test_terminology_redeclaration_conformance.py`) to the dev tooling and
  repoint its import.
- Update tree-scanning gates so no removed terminology package is allowlisted in
  `test_docstring_return_type_links` or `test_exception_base_hygiene`.
- Regenerate autodoc stubs with `python -m dev.docs.apidocs scaffold`; no
  production terminology API node remains.
- Reconcile dead terminology-code targets in
  `relevance/relevance.json` (remove the dead code-surface targets; this is a
  licence-clean removal of targets pointing at removed code, not new ranking
  data).
- Use `python -m dev.docs.terminology_handbook` for contributor tooling.

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
