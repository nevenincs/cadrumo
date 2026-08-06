---
step_id: S260
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-07-17'
body_hash: 'sha256:1f1b578f138e5696dd1f41bc7b3b10435e42d83c2e03c6272eceb3cf0c521276'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-30-codebase-solidification-audit]]"
---

# codebase-solidification W02.P11.S260

**Raise site:** `src/aeat/adapters/persistence/storage/_namespace_registry.py:119`

**Change:** Replaced `raise ValueError(f"namespace {self.namespace!r} does not define a singleton object key")` with `raise NamespaceRegistryError(...)`. `NamespaceRegistryError` was already imported from `.errors` at the top of the file.

**Test:** `test_namespace_registry.py` — 30 tests pass.

**Commit:** `d76cbf66e`
