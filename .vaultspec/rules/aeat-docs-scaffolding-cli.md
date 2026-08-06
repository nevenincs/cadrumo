---
name: aeat-docs-scaffolding-cli
---

# AEAT documentation scaffolding CLI

## Rule

Maintain the generated API reference with the `dev.docs.apidocs` CLI; never
hand-author or hand-edit the `docs/api/*.rst` stubs. Run `python -m
dev.docs.apidocs scaffold` after any change to the `src/cadrumo/` module tree
(especially a symbol relocation, rename, or deletion) and land the regenerated
stubs in the same commit as the source change. Use `python -m dev.docs.apidocs
scaffold --check` as the drift gate and `python -m dev.docs.apidocs audit` for a
health report.

## Why

The `docs/api/` stubs are generated from the module tree and the nitpicky `-n -W`
Sphinx gate imports every stubbed module: a stub left for a deleted/moved module
is an *orphan* that hard-crashes autodoc with `ModuleNotFoundError`, and a module
added without a stub silently drops out. During the module-relocation campaign a
leftover `cadrumo.adapters.inbound.pdf._errors.rst` reddened the whole docs-build
gate for an unrelated agent. The CLI is idempotent and authoritative; a hand-edit
drifts from the tree and is reverted on the next regeneration.

## How

- **Good:** a relocation commit runs `scaffold` and stages the regenerated
  `docs/api/*.rst` deltas (new stubs, removed orphans, updated parent toctrees) in
  the same explicit-path commit as the source move; before declaring a refactor
  done, `scaffold --check` exits clean and `just docs-check` passes. A newly-stubbed
  module module-qualifies a stdlib cross-reference
  (`:exc:`~decimal.InvalidOperation``, not bare `:exc:`InvalidOperation``, which is
  absent from the intersphinx inventory), while bare *project* anchors
  (`:class:`ModeloRevision``) stay bare per `core-struct-docstring-links`.
- **Bad:** hand-creating/editing a `docs/api/*.rst` stub; committing a
  delete/rename without re-running `scaffold` (leaving an orphan that crashes the
  next `-n -W` build); or running the full doc build to *discover* stub drift
  instead of the instant `apidocs audit` / `scaffold --check`.

## Source

Operator directive recorded 2026-06-02 (docs-educational-surface campaign,
chore/eliminate-shims); taxonomy `2026-05-30-docs-architecture-adr`. Companion:
`aeat-architecture-boundaries` (relocation atomicity),
`core-struct-docstring-links`, `aeat-documentation-workflow`.
