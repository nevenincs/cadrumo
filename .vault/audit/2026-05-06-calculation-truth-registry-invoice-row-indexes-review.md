---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-06-calculation-truth-registry-invoice-row-indexes]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `calculation-truth-registry` Code Review

No blocking issues were found in the invoice row-index alignment slice.

The previous row resolver shape used zero-based indexes, which did not match
the filing draft schema or export renderer. The resolver now emits one-based
indexes and the row-binding tests assert the public contract directly.

Verification recorded:

- `uv run pytest src/aeat/domain/calculations/registry/test_invoice_bindings.py -q`
- `uv run ty check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- `git diff --check -- src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
