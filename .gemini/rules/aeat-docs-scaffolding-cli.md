---
name: aeat-docs-scaffolding-cli
trigger: always_on
---

# AEAT documentation scaffolding CLI

## Rule

Maintain the generated API reference with the `dev.docs.apidocs` CLI; never
hand-author or hand-edit the `docs/api/*.rst` stubs. Run
`python -m dev.docs.apidocs scaffold` after any change to the `src/aeat/` module
tree — especially a symbol relocation, rename, or deletion — and land the
regenerated stubs in the same commit as the source change. Use
`python -m dev.docs.apidocs scaffold --check` as the drift gate and
`python -m dev.docs.apidocs audit` for a health report.

## Why

The API reference stubs under `docs/api/` are generated from the module tree,
and the nitpicky `-n -W` Sphinx gate imports every stubbed module. A stub left
behind for a deleted or moved module is an *orphan* that hard-crashes autodoc
with `ModuleNotFoundError`; a module added without a stub silently drops out of
the reference. During the module-relocation campaign this recurred: deleting
`adapters/inbound/pdf/_errors.py` left an orphan
`aeat.adapters.inbound.pdf._errors.rst` that reddened the entire docs-build gate
for an unrelated agent, and `apidocs audit` then found 2 orphan plus 6 missing
stubs accumulated across uncoordinated moves. The CLI is idempotent and
authoritative; hand-editing a stub drifts from the source tree and is reverted on
the next regeneration. This rule is the call-site companion to the
relocation-atomicity paragraph in `aeat-architecture-boundaries` (one atomic
explicit-path commit per relocation) and to `core-struct-docstring-links` (which
governs the docstring cross-references the stubs expose).

## How

- **Good:** a relocation commit that moves a symbol runs
  `python -m dev.docs.apidocs scaffold` and stages the regenerated `docs/api/*.rst`
  deltas (new stubs, removed orphans, updated parent toctrees) in the same
  explicit-path commit as the source move, so the docs tree never lags the code.
- **Good:** before declaring a structural refactor done,
  `python -m dev.docs.apidocs scaffold --check` exits clean (no drift) and
  `just docs-check` passes.
- **Good:** a newly-stubbed module that cross-references a stdlib name
  module-qualifies it (`:exc:`~decimal.InvalidOperation``, not bare
  `:exc:`InvalidOperation``) — the bare form is absent from the Python
  intersphinx inventory and reds the nitpicky gate the moment its stub is
  generated. Bare *project* anchors (`:class:`ModeloRevision``) stay bare: the
  short-reference resolver maps them, and `core-struct-docstring-links` forbids a
  dotted path on an anchor.
- **Bad:** hand-creating or hand-editing a `docs/api/*.rst` stub. It drifts from
  the module tree and the next `scaffold` overwrites it.
- **Bad:** deleting or renaming a module and committing without re-running
  `scaffold`, leaving an orphan stub that crashes the next `-n -W` build for a
  peer agent.
- **Bad:** running the full doc build to *discover* stub drift instead of
  `apidocs audit` / `scaffold --check` — the build is a tens-of-minutes gate; the
  audit is instant.

## Source

Operator directive recorded 2026-06-02 during the docs-educational-surface
campaign on the `chore/eliminate-shims` branch, after a relocation-orphan stub
(`aeat.adapters.inbound.pdf._errors`) reddened the nitpicky docs-build gate.
Documentation-surface taxonomy: `2026-05-30-docs-architecture-adr`. Companion
rules: `aeat-architecture-boundaries` (relocation atomicity),
`core-struct-docstring-links` (docstring cross-reference coverage),
`aeat-documentation-workflow` (the hand-written narrative surfaces this rule's
generated surfaces complement).
