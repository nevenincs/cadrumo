---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase5` `step2`

Removed the public application testing helper's dependency on model-specific
domain filing builder schemas and kept complementaria rebuilds behind explicit
schema-provider injection.

- Created: `src/aeat/application/filing/_testing_static_schema.py`
- Modified: `src/aeat/application/filing/testing.py`
- Modified: `src/aeat/application/filing/_complementaria.py`
- Modified: `src/aeat/application/filing/test_complementaria.py`
- Modified: `src/aeat/entrypoints/cli/filing/__init__.py`
- Modified: `src/aeat/entrypoints/cli/filing/test_filing_cli.py`
- Modified: `tests/import_contract/test_registry_deletion_gates.py`

## Description

The application testing API now imports synthetic static schemas from an
application-local testing module instead of `domain.filing._builders`.

`build_complementaria` no longer calls `build_runtime_schema_provider`
internally. The caller must pass a schema provider explicitly. This keeps the
production CLI on the registry gate because its provider creation still routes
through the disabled runtime provider, while tests can deliberately use the
synthetic provider. The CLI now catches the registry-gate filing error and
returns it as an operator-facing command validation failure without writing an
amended draft or amendment record.

The import-contract suite now asserts that application testing helpers do not
import builder static schema modules.

## Tests

Verified with targeted `ruff check`, `ty check`, and the filing/import-contract
test slice. The slice passed 135 tests covering import boundaries, synthetic
fixture loading, draft building, Modelo 303/390 arithmetic, Modelo 130 filing
tests, justificante import, complementaria, and filing CLI behaviour.
