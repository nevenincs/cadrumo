---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m100-revision-drift-research]]'
  - '[[2026-05-27-schema-hardening-non-overlap-drift-inventory-exec]]'
---



# `schema-hardening` `label-artifact-inventory`

Added a generic advisory collector for unresolved casilla label format
placeholders.

## Description

The M100 annual-drift research found unresolved placeholder artifacts in
labels. The new collector inventories those artifacts across all modelos
without adding modelo-specific rules. The committed-corpus regression test
pins the current baseline at 266 placeholder occurrences, all in Modelo 100,
using the placeholder tokens `{0}` and `{2}`.

This is advisory rather than a hard load-time validator because the current
corpus still contains legacy artifacts. The baseline test prevents silent
creep while allowing a future cleanup slice to intentionally lower and
rebaseline the count.

## Tests

Initial failed gates, not swallowed:

`uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_label_artifacts.py src/aeat/domain/calculations/registry/test_label_artifacts.py`

Result: failed on Ruff S105 against direct placeholder-token assertions.

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_label_artifacts.py -q`

Result: failed because the generic regex found 266 unresolved placeholders,
not the earlier literal `{0}` scan's 247 occurrences.

Final gates:

`uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_label_artifacts.py src/aeat/domain/calculations/registry/test_label_artifacts.py`

Result: passed.

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_label_artifacts.py -q`

Result: 3 passed.
