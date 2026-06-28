---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S03'
related:
  - '[[2026-05-27-schema-hardening-m308-standardization-plan]]'
---



# `schema-hardening-m308-standardization` `P01.S03`

Verified the Modelo 308 directory-form registry source through the focused
registry and generic directory-loader gate.

- Modified: none.
- Created: `.vault/exec/2026-05-27-schema-hardening-m308-standardization/2026-05-27-schema-hardening-m308-standardization-P01-S03.md`

## Description

The first focused pytest invocation exposed a real regression in the test
expectation: the generic loader tests still required at least one committed
root-level single-file modelo. Modelo 308 was the final such file, so the
test expectation was updated to accept an all-directory committed corpus
while preserving single-file loader coverage through existing temporary
round-trip fixtures.

The generated fragment baseline confirms the root-level `308.toml` source
has been eliminated. The largest M308 fragment is now 42 lines, with all
other fragments at or below 35 lines.

## Tests

Initial failed run:

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_308_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`

Result: 3 loader expectation failures, all requiring committed single-file
sources after the final root-level single-file modelo was removed.

Passed after updating the loader-test expectation:

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_308_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`

Result: 31 passed in 68.88 seconds.
