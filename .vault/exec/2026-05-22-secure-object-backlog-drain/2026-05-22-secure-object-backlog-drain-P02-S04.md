---
tags:
  - '#exec'
  - '#secure-object-backlog-drain'
date: '2026-05-22'
step_id: 'S04'
related:
  - '[[2026-05-22-secure-object-backlog-drain-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `secure-object-backlog-drain` `P02.S04`

Inventoried the classified secure-SQL hygiene backlog and selected the
first repair slice.

- Modified: none
- Created: `.vault/exec/2026-05-22-secure-object-backlog-drain/2026-05-22-secure-object-backlog-drain-P02-S04.md`

## Description

The guard currently carries 60 classified P02.S06 file-level exceptions.
The first repair slice will convert three modules that already use an
autouse temp SQLite fixture but still rely on `pytest.MonkeyPatch` for
`AEAT_DATABASE_URL`: `src/aeat/adapters/outbound/aeat/sede/test_observation_store.py`,
`src/aeat/adapters/persistence/storage/test_submission_repository.py`,
and `src/aeat/domain/usage_ratios/test_service.py`.

This slice is intentionally bounded because each selected module can be
made compliant by direct `os.environ` save/restore plus engine disposal,
without changing business assertions or introducing fakes, stubs,
mocks, monkeypatches, skips, or xfails.

## Tests

Read the current hygiene guard classification list and the selected
test modules. No code tests were run for this inventory-only step.
