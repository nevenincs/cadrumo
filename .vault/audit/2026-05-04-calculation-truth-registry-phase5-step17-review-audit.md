---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-04-calculation-truth-registry-phase5-step17-exec]]'
---



# `calculation-truth-registry` Code Review


P5S17-001 | MEDIUM | Deletion gates do not prove the removed schema/modelo authority packages stay absent

`tests/import_contract/test_adr_layout_import_smoke.py` keeps `DELETED_ROOT_MODULES` limited to older cutover modules and does not include `aeat.domain.schema` or `aeat.adapters.inbound.schema`; `tests/import_contract/test_registry_deletion_gates.py` now only checks the application filing static-schema provider boundary and has no current-behaviour assertion that the deleted schema packages, BOE schema extraction adapter package, or deleted modelo metadata private modules are absent and non-importable. This means the focused import-contract suite can pass even if `aeat.domain.schema`, `aeat.adapters.inbound.schema`, `aeat.domain.modelos._registry`, `aeat.domain.modelos._entries`, `aeat.domain.modelos._metadata`, `aeat.domain.modelos._applicability`, `aeat.domain.modelos._citations`, or `aeat.domain.modelos._citation_registry` are reintroduced as Python legal/schema/modelo authorities. Add non-transition deletion gates that exercise the current intended behaviour: `importlib.util.find_spec(...) is None` for the deleted packages/modules, package-directory absence for the physical package roots, and public `aeat.domain.modelos` assertions that only `ModeloCode` is exported and old registry/applicability/citation helpers are not attributes.

P5S17-002 | MEDIUM | Known-bad citation blocklist move lost broad behavioural regression coverage

`src/aeat/domain/calculations/registry/_citation_blocklist.py` carries the preserved known-bad citation table, but `src/aeat/domain/calculations/registry/test_catalogue_verification.py` exercises only one blocked citation through `verify_legal_catalogue`. The deleted modelo citation tests previously covered many blocklist rows plus accent folding and false-positive precision. The Phase 5 plan requires legal-reference validation with known-bad citation regression, so the current tests do not adequately prove the moved registry validator still blocks all preserved known-bad cases without overmatching. Add current-behaviour tests against the registry validator: parameterize representative or all `_KNOWN_BAD_CITATIONS` rows through `LegalReference` plus `verify_legal_catalogue`, include diacritic-folding cases, and include allowed near-miss citations that must not fail.

P5S17-003 | LOW | Public docs/config still advertise deleted schema extraction packages

`README.md`, `docs/api/aeat.domain.rst`, `docs/api/aeat.adapters.inbound.rst`, `docs/api/aeat.domain.schema.rst`, `docs/api/aeat.adapters.inbound.schema.rst`, and `docs/api/aeat.adapters.inbound.schema.testing.rst` still describe or autodoc deleted `aeat.domain.schema` and `aeat.adapters.inbound.schema` packages. `pyproject.toml` also retains stale references to the deleted modelo CLI path and schema-extraction/domain marker descriptions. This is not a current runtime authority path, but it leaves public documentation and generated API docs inconsistent with the hard deletion and can cause docs builds to fail on missing automodules. Remove the deleted packages from API toctrees and update README/test marker/config wording to registry-backed schema terminology.

## Resolution

- P5S17-001: current-behaviour coverage was kept on the live public surface instead of adding new migration or deletion-state tests. `aeat.domain.modelos` now asserts that its supported public API is the `ModeloCode` identifier only. No new tests were added that exercise prior-state migration.
- P5S17-002: fixed. `verify_legal_catalogue` now has current-behaviour coverage for every preserved known-bad citation entry, diacritic-insensitive matching, and allowed near-miss text.
- P5S17-003: fixed. The deleted schema extraction packages were removed from public API docs and stale README/config wording was updated to describe the registry-backed surface.

Verification passed:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry src/aeat/domain/modelos src/aeat/domain/portals src/aeat/domain/casillas tests/import_contract`
- `uv run --no-sync ty check`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry src/aeat/domain/modelos src/aeat/domain/portals src/aeat/domain/casillas/test_corpus_rule_alignment.py tests/import_contract/test_adr_layout_import_smoke.py tests/import_contract/test_registry_deletion_gates.py`
