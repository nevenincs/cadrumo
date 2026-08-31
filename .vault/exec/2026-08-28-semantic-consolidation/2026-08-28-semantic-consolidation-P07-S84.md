---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:7db861cf2cf8206b30a7775823c50ca01b23f27566aea7bac6877e1ddb5b48b6'
step_id: 'S84'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Rule on the three module-scope registration side effects, whose dependency inversion is sound but whose siting in a package namespace makes touching that package cost 613 modules

## Scope

- `src/cadrumo/`

## Changes

- `M` `src/cadrumo/application/registry/__init__.py`
- `M` `src/cadrumo/application/calculations/__init__.py`
- `verify:` AST census of module-scope calls in every package namespace -- 7, of which 2 are test fixtures

## Notes

Censused rather than taken from the step's count. Seven module-scope calls sit in
package namespaces; two are `_s09_optional_*` test fixtures. The five real ones
are three different things, and the ruling differs for each.

**Sound and forced.** `application/calculations` calls `model_rebuild()` to
resolve a forward reference that is `TYPE_CHECKING`-only inside
`_iva_wallet_reconciliation` because of a circular import. It cannot move to a
defining module: it needs BOTH modules already loaded, and the package namespace
is the only place that observes that condition. It registers nothing and reaches
nothing.

**Process configuration, not registration.** `entrypoints/cli` configures stdio
for UTF-8, disables rich rendering, and decorates the Typer app. These are an
entrypoint's own setup on the way to becoming a program, not a package exporting
behaviour, and the step's "dependency inversion" framing does not describe them.

**Superseded.** `application/registry` imports `cadrumo.domain.renta` purely to
trigger its cross-domain check registration. That is the finding.
`_snapshot_internals._install_cross_domain_snapshot_checks` now does the same
import, idempotently and flag-guarded, at the start of every snapshot build --
and its docstring names THIS site as the problem it was built to solve:
"registration no longer relies on a composition root happening to import renta
before the first M100 snapshot."

So the old mechanism survives beside its own replacement, in a namespace whose
`__all__` is empty. That pairing is the worst available: nothing to import the
package FOR, yet importing it pulls a domain. It is the 613-module cost the step
names.

Ruled superseded and recorded at the site rather than deleted. Removing a
registration side effect is a behaviour change on an import-order-sensitive path
and wants a green tree to land against; the tree is currently mid-relocation by a
peer and will not import.
