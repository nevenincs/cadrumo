---
tags:
  - '#audit'
  - '#legacy-cleanup'
date: '2026-04-18'
modified: '2026-04-18'
related:
  - '[[2026-04-18-rename-corpus-review-schema-adr]]'
  - '[[2026-04-18-rename-corpus-review-implementation-plan]]'
---

# `legacy-cleanup` Code Review

LEGACY-CLEANUP-001 | MEDIUM | Dead casillas protocol stub still carries stale review naming
`src/aeat/domain/casillas/_protocols.py` is not imported by the active runtime tree and `BulkTranslator.translate_translatable(..., reviewed_at=...)` still preserves the pre-rename review namespace. Keeping dead scaffolding in `src/` increases maintenance surface and weakens the strict no-legacy stance of issue `#225`.

LEGACY-CLEANUP-002 | MEDIUM | LLM language validation still routes through a compatibility shim
`src/aeat/adapters/outbound/llm/_i18n_compat.py` is still imported by live LLM modules even though the repo already has a real `aeat.core.i18n` package that owns the language contract. This is active compatibility debt and should be collapsed into the canonical i18n surface so the runtime tree stays lean.
