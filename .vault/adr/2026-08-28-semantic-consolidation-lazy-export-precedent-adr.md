---
tags:
  - '#adr'
  - '#semantic-consolidation'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:d52805ed5b98d160dd3409c1bd5c4794af968af661afd0f13eb717cb926bc839'
related:
  - "[[2026-08-28-semantic-consolidation-research]]"
---

# `semantic-consolidation` adr: `the lazy export map is bounded to its measured case` | (**status:** `proposed`)

## Problem Statement

Two accepted positions in this repository contradict each other, and the contradiction
has been resolved in practice by the one nobody wrote down.

`aeat-architecture-boundaries` states that package `__init__.py` namespaces are inert
and may not import, bind, alias, lazily resolve or re-export project symbols, and that
PEP 562 export maps are prohibited.

`2026-06-03-cli-errors-domain-package-lazy-import-adr`, status accepted, introduces a
PEP 562 `__getattr__` at a package boundary. Its scope is narrow and explicit: ONE
package (`domain/user_profile`), ONE symbol (`UserProfilePortableExport`, the heavy
re-export), for a measured reason -- importing that package must place zero
`calculations.registry*` modules in `sys.modules`. It states in terms that the
lightweight error, value, schema, loader and registry-contract re-exports remain eager.

What ships is neither position. NINE packages carry a full `_LAZY_EXPORTS` map covering
1127 symbols across roughly 2953 import sites, and NOT ONE of them is the sanctioned
site: `domain/user_profile/__init__.py` carries no `__getattr__` at all today.

| package | symbols | importing modules |
|---|---|---|
| `core` | 354 | 2229 |
| `adapters/persistence/storage` | 257 | 102 |
| `adapters/persistence/storage/custody` | 147 | 61 |
| `domain/modelos` | 118 | 402 |
| `application/filing` | 97 | 37 |
| `application/registry` | 87 | 8 |
| `application/review` | 47 | 19 |
| `adapters/persistence/storage/crypto` | 18 | 14 |
| `tests` | 2 | 157 |

## Findings

The drift is in two dimensions at once, and separating them is what makes this
rulable.

SHAPE. The ADR sanctioned an on-demand guard for ONE named heavy symbol. What
propagated is a whole-namespace export map -- the precise construct the standing rule
prohibits by name. A guard that defers one expensive import and a map that indirects an
entire public surface are different mechanisms with different consequences; only the
first was argued for.

SITE. The ADR's justification is a MEASUREMENT about one package's import graph. That
measurement does not transfer. Nothing in the accepted text claims the idiom is
generally good, and nothing measured the other eight.

There is a third finding that changes the size of the problem. `application/registry`
exposes `verify_filed_state`, which consumers import from the package namespace but
which is defined directly in that package's own `__init__.py` and is NOT in its
`_LAZY_EXPORTS` map. So retiring a lazy map does not by itself make a namespace inert:
locally-defined exports are a second, uncounted population sitting behind the same
import statements.

## Constraints

The 1127 symbols are reached through roughly 2953 import statements. `core` alone is
2229 importing modules -- two orders of magnitude beyond the other eight combined. Any
plan that treats the nine as one unit is really a plan about `core` with eight
rounding errors attached.

A peer `git reset --hard` destroyed nineteen uncommitted consolidations during this
campaign, and module-scope validation in a mid-edit file failed roughly 142 tests at
collection. A sweep touching thousands of import sites in this worktree cannot be one
change.

## Considered options

**Amend the rule to permit the idiom.** Rejected. The rule's reasoning is intact: an
indirected namespace makes the import graph unreadable to the layered-contract audits
that depend on it, and the lazy map hides which submodule actually owns a symbol. That
the idiom spread is evidence it is convenient, not that it is correct.

**Delete all nine maps.** Rejected as a single act, not as an outcome. It is the right
end state and the wrong first move: it would rewrite thousands of import statements
across a tree with live peer sessions, and the one measured justification for the idiom
has not been re-tested.

**Leave it.** Rejected. The contradiction is load-bearing: a future author reading the
accepted ADR reasonably concludes the idiom is sanctioned, because at nine packages it
plainly looks like house style.

## Decision

The sanctioned exception is BOUNDED TO ITS MEASURED CASE, and the standing prohibition
governs everywhere else.

Concretely: a PEP 562 `__getattr__` at a package boundary is permitted only for a
NAMED SYMBOL whose deferral is justified by a RECORDED MEASUREMENT of import weight, and
only for as long as that measurement holds. It is not permitted as a whole-namespace
export map. The eight unmeasured maps are unsanctioned and are retired; `core` is
retired under its own phase and its own measurement.

The earlier ADR is not overturned. Its reasoning was sound for the case it argued; what
is corrected is the inference that a bounded exception is a general licence. Its scope
sentence -- the lightweight re-exports remain eager -- was the boundary all along, and
this decision restates it as a rule rather than an aside.

## Implementation

Retirement is by package, smallest production blast radius first, one package per
commit, never a tree-wide sweep. `custody` and `crypto` lead: both are over 80 per cent
test-only consumers, so their symbol counts overstate their production reach.
`application/registry` (8 importing modules) is the smallest and is the natural first
proof of the mechanics.

`core` is its own phase and does not begin until the other eight are closed. Before it
starts, its cold-start justification is RE-MEASURED rather than assumed: if importing
`cadrumo.core` eagerly is cheap today, the original reason has lapsed and retirement is
mechanical; if it is expensive, retirement needs a different shape and that shape is
decided then, on the numbers, not now.

Each package's locally-defined `__init__.py` exports are counted alongside its lazy map
before that package is called done, because retiring the map alone leaves the namespace
non-inert and would let the package be recorded as closed while still re-exporting.

## Consequences

The import graph becomes readable to the layered-contract audits again, one package at
a time, and every symbol is reached at its defining module.

The cost is real and worth stating: roughly 2953 import statements move, in a worktree
where uncommitted work has already been destroyed once. The per-package, per-commit
sequencing is what bounds that exposure, and it is a constraint on the plan rather than
a preference about it.

The risk this decision accepts is that `core`'s re-measurement may show the eager import
is genuinely expensive, in which case the largest package keeps a mechanism the other
eight lost. That would be an honest outcome rather than a failure -- the exception was
always meant to be a measured one -- but it must be recorded as a measurement, not
inherited as a habit.
