---
name: aeat-worktree-safety
trigger: always_on
---

# AEAT worktree safety

- Work only in the assigned worktree and confirm its root and branch before a material change.
- Treat every pre-existing modification as another contributor's work. Inspect before editing, preserve unrelated changes, and never use destructive reset, checkout, clean, or broad restore operations to obtain a tidy tree.
- Before moving or deleting recursively, resolve the exact absolute targets and verify they remain inside the intended directory. Prefer recoverable operations when practical.
- Use one writer for a shared file or tightly coupled generated surface. Re-read the file and diff before applying a stale patch.
- Stage or report only the files owned by the requested change. A dirty worktree is not permission to absorb, reformat, fix, commit, or discard unrelated work.
- Do not commit, push, merge, publish, or alter external project state unless the operator requested that action or the active approved workflow explicitly requires it.
