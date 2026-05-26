---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-26'
step_id: 'S143'
related:
  - '[[2026-05-20-schema-hardening-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `schema-hardening` `W09.P20.S143`

Closed the Bucket B repair-integrity import edge as a tracked cross-campaign
defer, without scaffolding the foreign-owned backend from schema-hardening.

- Modified: `.vault/plan/2026-05-20-schema-hardening-plan.md`
- Created: `.vault/exec/2026-05-20-schema-hardening/2026-05-26-schema-hardening-W09-P20-S143.md`

## Description

The four baseline entries remain owned by the parallel repair-integrity/live
IVA wallet work. This schema-hardening row is therefore closed as an edge record
rather than by implementing the symbols in `repair_integrity.py`.

The active cross-module import gate still passes with the Bucket B entries in
the baseline. Its silent-fix detector remains the correct guard: once the
owning campaign lands the symbols into the committed runtime surface, the gate
will fail until `_BASELINE_BROKEN_IMPORTS` is trimmed.

## Tests

`uv run --no-sync pytest src/aeat/tests/test_cross_module_imports_resolve.py -q`
passed with three tests.
