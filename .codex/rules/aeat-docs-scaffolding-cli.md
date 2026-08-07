---
name: aeat-docs-scaffolding-cli
trigger: always_on
---

# AEAT documentation scaffolding CLI

Maintain the generated API reference with the `dev.docs.apidocs` CLI; never
hand-author or hand-edit the `docs/api/*.rst` stubs. Run
`python -m dev.docs.apidocs scaffold` after any change to the `src/cadrumo/`
module tree — especially a relocation, rename or deletion — and land the
regenerated stubs in the same commit as the source change. Use
`scaffold --check` as the drift gate and `audit` for a health report.

The stubs are generated from the module tree, and the nitpicky `-n -W` Sphinx
gate imports every stubbed module: a stub left for a deleted or moved module is
an *orphan* that hard-crashes autodoc, and a module added without a stub silently
drops out. The CLI is idempotent and authoritative; a hand-edit drifts and is
reverted on the next regeneration.

**`scaffold` is tree-wide, not change-scoped.** In this shared worktree peers
routinely add modules without scaffolding, so one run emits stubs for *their*
modules too. Diff each modified stub and stage only the ones whose added lines
name **your** module; leave the rest for their owners and do not revert them.

## How

- **Good:** a relocation commit runs `scaffold` and stages the regenerated deltas
  for its own modules in the same explicit-path commit; before declaring a
  refactor done, `scaffold --check` exits clean and `just docs-check` passes.
- **Good:** a newly-stubbed module module-qualifies stdlib cross-references
  (`:exc:`~decimal.InvalidOperation``, not a bare name absent from the
  intersphinx inventory), while bare *project* anchors stay bare per
  `core-struct-docstring-links`.
- **Bad:** hand-creating or editing a stub; committing a delete or rename without
  re-running `scaffold`, leaving an orphan that crashes the next build; or
  running the full doc build to *discover* stub drift instead of the instant
  `--check`.

A red docs build after `scaffold` is often not yours — grep the log for your own
module names before assuming it is.
