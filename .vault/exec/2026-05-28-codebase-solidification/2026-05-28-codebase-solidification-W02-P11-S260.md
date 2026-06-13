---
step_id: S260
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-30-codebase-solidification-audit]]"
---

# codebase-solidification W02.P11.S260

**Raise site:** `src/aeat/adapters/persistence/storage/_namespace_registry.py:119`

**Change:** Replaced `raise ValueError(f"namespace {self.namespace!r} does not define a singleton object key")` with `raise NamespaceRegistryError(...)`. `NamespaceRegistryError` was already imported from `.errors` at the top of the file.

**Test:** `test_namespace_registry.py` — 30 tests pass.

**Commit:** `d76cbf66e`
