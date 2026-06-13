---
tags:
  - '#adr'
  - '#cli-errors-domain-package-lazy-import'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-cli-errors-domain-package-lazy-import-research]]"
  - "[[2026-06-03-user-profile-lazy-import-adr]]"
---

# `cli-errors-domain-package-lazy-import` adr: `Lazy import via PEP 562 dispatch for the user_profile domain package boundary` | (**status:** `accepted`)

## Problem Statement

The CLI lazy-loading discipline gate at
`src/aeat/entrypoints/cli/test_lazy_command_tree.py` reds five state-free-surface
tests even after the parent campaign's application-package boundary fix landed
(commit `20992e0d4` — `aeat.application.user_profile` is now lazy-by-default and
the producer probe at `src/aeat/application/user_profile/test_lazy_boundary.py`
confirms zero `aeat.domain.calculations.registry*` modules enter `sys.modules`
on package import).

A fresh-interpreter probe demonstrates the residual leak is orthogonal to the
application boundary: `import aeat.entrypoints.cli._errors` places 69
`aeat.domain.calculations.registry*` modules in `sys.modules`, identical to
the count the CLI-side gate measures end-to-end. The chain is
`cli/__init__.py:46` -> `cli/_errors.py:55` (a module-scope
`from ...domain.user_profile import StoredProfileDriftError`) ->
`aeat.domain.user_profile/__init__.py:22` (a module-scope
`from ._portable_export import UserProfilePortableExport`) ->
`_portable_export.py:21` (`from ..modelos._calculation_revision import ...`) ->
`_calculation_revision.py:52` (`from ..calculations.registry import CasillaObservation`).

The first contact with the registry is the `_calculation_revision` import,
reached by importing the `user_profile` domain package only because the
package's `__init__.py` eagerly re-exports `UserProfilePortableExport`. Every
state-free CLI surface that needs any user-profile name pays this 69-module
cost at module-load time.

## Considerations

The parent ADR (`2026-06-03-user-profile-lazy-import`) recorded the diagnosis
of this vector in its "Findings — execution-time scope expansion" section and
explicitly deferred the decision to a successor ADR rather than half-fix it
under the parent's scope. The parent ADR also catalogued three candidate
patterns: (E) lazy domain-package boundary, (F) consumer-side direct import,
(G) lift `StoredProfileDriftError` up to `aeat.core`. This ADR adopts the
parent's nomenclature: the successor "Pattern (a) / (b) / (c)" in the
dispatch brief maps to the parent's (E) / (F) / (G).

The discipline ratchet at `test_lazy_command_tree.py` is documented as
load-bearing for the cold-start UX (a fresh `aeat --version` budget of 2.0 s
silently regresses to 3+ s without it). The companion ADR
`2026-06-03-bare-invocation-bucket-session-gate` documents the same axis
from a different angle. Both ADRs frame the state-free CLI surfaces as a
distinct architectural class with stricter import constraints than
subcommand-bound surfaces.

The rule `aeat-architecture-boundaries` mandates hexagonal direction: the
domain layer's eager pull of registry through `_calculation_revision` is
legitimate (domain imports nothing from adapters; the registry is itself a
domain primitive). The registry's import cost is real but architecturally
correct. The fix must therefore live in the *domain package boundary*'s
re-export discipline, not in the domain layer's internal structure.

The rule codified in `4e443841b` (consume through the package boundary,
not past it) and the lazy-loading ratchet are both correct. The fix must
satisfy both simultaneously — neither can yield. Pattern (E) satisfies
both; Patterns (F) and (G) each weaken one.

## Constraints

The `__init__.py` re-export of `UserProfilePortableExport` is consumed
through the package boundary at three real call sites (the import / export
verbs in the user-profile application service) and through the `__all__`
list as a publicly documented symbol. The public surface must not change.

The lightweight re-exports (errors / values / schema / loader) are touched
by 54 consumer sites and stay eager — every consumer that imports a
lightweight name expects it to resolve at module-load time. Routing every
lightweight name through `__getattr__` would over-rotate; routing only the
heavy ones keeps the cut at the cost boundary.

The `aeat.domain.user_profile/__init__.py` does not currently implement a
module-level `__getattr__`. The pattern is new at this site (the parent
ADR established it at the application-package boundary one layer up); the
shape is mechanical and proven.

The relocation lands as one atomic explicit-path commit per the
`aeat-architecture-boundaries` symbol-relocation atomicity clause. The
file is shared with peer agents; the commit must restrict its blast
radius to the four-file set named in Implementation.

## Decision: Pattern (a) / (E) — lazy domain-package boundary via PEP 562 `__getattr__`

Make `aeat.domain.user_profile/__init__.py` lazy-by-default for its heavy
re-export, `UserProfilePortableExport`. The lightweight error / value /
schema / loader / registry-contract re-exports remain eager. The
`UserProfilePortableExport` symbol is resolved on demand through a
module-level `__getattr__` block (PEP 562). The `__all__` list does not
change; the public surface is unchanged.

After the change, importing `aeat.domain.user_profile` in a fresh
interpreter places zero `aeat.domain.calculations.registry*` modules in
`sys.modules`. The `cli/_errors.py` import of `StoredProfileDriftError`
resolves through the eager error re-exports and never touches
`_portable_export`. The five red CLI-gate tests go green; the producer
probe at `src/aeat/application/user_profile/test_lazy_boundary.py`
continues to pass (the application boundary fix is preserved). The
producer-side mirror probe at
`src/aeat/domain/user_profile/test_lazy_boundary.py` lands alongside the
change to pin the domain-package contract at the layer where it actually
lives.

## Why not the alternatives

**Pattern (b) / (F) — consumer-side direct import** scatters function-local
import blocks across every state-free CLI consumer that touches a
user_profile symbol. The current red gate is satisfied by patching a
single site, but the producer-side discipline stays structurally wrong:
any future state-free CLI surface acquiring its first user_profile import
re-introduces the regression. The pattern also violates the codified
package-consumption rule (consume through the boundary, not past it),
which has been applied uniformly across the project. Granting an
exception only for `cli/_errors.py` sets a precedent that any state-free
CLI surface can dot into private submodules.

**Pattern (c) / (G) — lift `StoredProfileDriftError` up to `aeat.core`**
relocates a domain-specific error class into a framework layer. The
class is currently a `UserProfileError` subclass; the parent class chain
either moves with it (cascading to every other `UserProfileError`
subclass — a 22-file relocation surface) or breaks (introducing a
cross-layer parent the core layer should not own). The core layer is
meant for primitives every domain depends on; a user-profile-specific
drift error is not such a primitive. Reject on layering grounds.

The parent ADR's Pattern C / D rejections (split the package; revert
the boundary-tightening commit) carry the same reasoning here and need
no re-litigation.

## Implementation

The implementation is a single atomic relocation:

- Convert `src/aeat/domain/user_profile/__init__.py` to dispatch the
  `UserProfilePortableExport` symbol through a module-level `__getattr__`
  block (PEP 562). Remove the top-level
  `from ._portable_export import UserProfilePortableExport` line. Keep
  every other top-level re-export (errors, values, schema, loader,
  registry-contract) eager — they are all lightweight.
- Add the `__getattr__` block at module scope. It imports
  `UserProfilePortableExport` from `._portable_export` on first access
  and caches the binding on the module via `globals()`. Any other
  attribute access falls through to a standard `AttributeError` for
  symmetry with eager-import semantics.
- Keep `__all__` unchanged. The public surface is identical; a `dir()`
  call returns the same list.
- Land a producer-side regression probe at
  `src/aeat/domain/user_profile/test_lazy_boundary.py`. The probe runs
  a fresh subprocess (warm-cache pollution from other test modules
  is not adequate evidence), imports the domain package, and asserts
  the registry-module count is zero. This mirrors the application-side
  probe the parent campaign established and pins the contract at the
  layer where the discipline actually lives.
- No consumer code changes. All 54 consumer sites import lightweight
  names; none receive an edit.

## Rationale

The decision preserves both binding rules: the package-consumption
discipline (consume through the boundary, not past it) and the
lazy-loading ratchet (state-free CLI surfaces import no registry). The
PEP 562 pattern is already in use one layer up (the application package
under the parent ADR); the relocation extends the pattern's scope rather
than introducing a new mechanism. The fix carries no skip, xfail, mock,
or stub — it makes the gate green honestly per `aeat-quality-gates`.

The relocation respects the `aeat-architecture-boundaries`
symbol-relocation atomicity clause: one symbol-group move
(`UserProfilePortableExport` from eager re-export to lazy re-export),
one commit, zero consumer updates needed because the public surface is
unchanged, and the `__getattr__` block lands together.

The parent ADR's Pattern A succeeded with the same shape at the
application layer; replicating it at the domain layer is the
lowest-precedent-cost, lowest-blast-radius fix and the one that keeps
the project's accumulated discipline coherent.

## Consequences

- The domain package becomes lazy for its only heavy re-export. First
  reference to `UserProfilePortableExport` triggers the on-demand
  import; every other import resolves at module-load as before. The
  cost shifts from import-time to first-use only for the one symbol
  that actually carries it.
- The state-free CLI surfaces stay registry-free without skip or test
  rewrite. The cold-start budget at `aeat --version` returns to the
  pre-regression profile.
- The PEP 562 pattern is now established at both the application-layer
  and domain-layer boundaries for re-export surfaces that span the
  lightweight / registry-coupled cut. The codified rule from the parent
  ADR (`application-boundary-lazy-by-default`) extends naturally to
  domain-package boundaries with the same shape.
- The implementation cost is one in-place edit to the package
  `__init__.py` plus a producer-side probe. No consumer code changes.
  The relocation lands in one commit.
- Pitfall to track: a future re-export that needs the heavy
  `UserProfilePortableExport` at module-load time pays the cost. The
  current consumer set does not have this need (the portable-export
  flow is reached only through explicit `aeat config profile
  export/import` verbs whose command modules already pay registry
  costs). The producer-side probe will fail loudly if a future eager
  re-export re-introduces the regression.

## Codification candidates

- **Rule slug:** `domain-boundary-lazy-by-default`.
  **Rule:** Domain-layer package `__init__.py` files that aggregate
  registry-coupled or otherwise heavy re-exports MUST use module-level
  `__getattr__` (PEP 562) to resolve those re-exports on demand.
  Top-level imports in the `__init__.py` body are reserved for
  lightweight primitives (errors, value records, schema records,
  loaders) that every consumer pays for unconditionally; anything that
  pulls registry, modelos, or transactions goes through the
  `__getattr__` block.

  **Why:** the state-free CLI surface budget enforced by
  `test_lazy_command_tree.py` is operator-visible; any domain-package
  boundary that eagerly imports registry-coupled material drags the
  cost across every consumer that crosses the boundary. The PEP 562
  pattern lets the boundary stay canonical (one consumption point)
  while keeping the cost deferred. The companion rule at the
  application-layer (`application-boundary-lazy-by-default`) and this
  rule together form the lazy-by-default discipline at every
  re-export surface that spans the cost boundary.

  **How to apply:** when authoring or modifying an
  `aeat.domain.<package>/__init__.py`, check whether any re-export
  pulls another domain package (`modelos`, `calculations`,
  `transactions`) at module-load time. If yes, the re-export goes
  through `__getattr__`. A producer-side probe at
  `aeat.domain.<package>.test_lazy_boundary.py` pins the contract at
  the layer where the discipline lives.
