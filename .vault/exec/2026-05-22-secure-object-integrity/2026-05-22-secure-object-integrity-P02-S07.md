---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
step_id: 'S07'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path
     (e.g., S03 at L1, P02.S03 at L2, W01.P02.S03 at L3 / L4). The
     step_id frontmatter field below carries the canonical identifier;
     the heading restates the display path as a reading hint. -->

# `secure-object-integrity` `P02.S07`

Added shared helper code for accepted secure SQL test isolation.

- Created: `src/aeat/tests/secure_sql.py`
- Created: `src/aeat/tests/test_secure_sql.py`

## Description

Added `isolated_ephemeral_secure_sql`, a test helper that sets a temporary SQLite `AEAT_DATABASE_URL`, disposes cached SQL engines before and after the isolated block, and opens a real `EphemeralMasterKeyProvider`. This encodes the accepted isolation pattern in reusable test helper code rather than prose-only documentation.

Added a real-behavior helper test proving the default SQL engine routes to the temporary database while the helper is active and that the ephemeral session is closed afterward.

## Tests

Focused validation passed:

- `uv run ruff check src/aeat/tests/secure_sql.py src/aeat/tests/test_secure_sql.py src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`
- `uv run pytest src/aeat/tests/test_secure_sql.py src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`

The focused test run passed 3 tests.
