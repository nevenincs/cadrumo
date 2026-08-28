---
tags:
  - '#adr'
  - '#semantic-consolidation'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:736574420f4488714efd2dd02b058764d8cd1afe1264bf4353f29a2db2d6b37e'
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

Retirement is by package, one package per commit, never a tree-wide sweep. But the nine
are NOT one population, and a survey of their `__init__.py` files found the split that
decides the sequencing:

SEVEN ARE TRUE FACADES -- the module contains the lazy hooks and nothing else, so
retiring the map IS the whole job: `crypto` (135 lines), `tests` (207), `review` (249),
`domain/modelos` (499), `custody` (522), `storage` (908), `core` (1233). Length varies
with the size of the export map, not with logic.

TWO ARE MODULES IN DISGUISE. `application/registry/__init__.py` is 840 lines defining
five pydantic models (`RegistryTreeReport`, `RegistryRevisionDetailReport`,
`RegistryWorkbookParityDetailReport`, `FiledStateVerificationReport`), a NamedTuple and
several public functions. `application/filing/__init__.py` is 1464 lines with 36
top-level definitions. For these, retiring the lazy map is the SMALLER half: their
namespaces hold production code that must first be relocated to real defining modules,
because a namespace containing classes cannot be made inert by deleting a dict.

`crypto` leads: a true facade, 18 symbols over two owning submodules, 14 importing
modules of which over 80 per cent are tests. It is the smallest honest proof of the
mechanics.

`application/registry` was named the first slice in an earlier draft of this decision, on
the strength of its 8 importing modules. That was wrong and the survey corrected it: a
low importer count made it look cheap while its namespace is a module. The two disguised
packages are sequenced LAST and are scoped as relocations, not retirements.

`core` is its own phase and does not begin until the other eight are closed. Its
cold-start justification has now been MEASURED rather than assumed, three runs per arm,
fresh interpreter each time:

| | modules in `sys.modules` | wall time |
|---|---|---|
| `import cadrumo.core` as shipped | +6 | 5.6-6.9 ms |
| same, then eagerly importing all 100 lazy targets | +416 | 719-781 ms |

So a naive retirement -- rewriting the map as 354 plain imports -- would add roughly
three quarters of a second to EVERY process that imports `cadrumo.core`, which is every
`aeat` invocation. The justification has not lapsed. It is real and it is large.

But the measurement also shows the weight is not diffuse. THREE submodules carry 311 of
the 416 modules, about 75 per cent: `_action_argument_resolution` (+135),
`_foreign_asset_obligation` (+130), `_config_state_root` (+46). Most of the other 97
targets cost nought to two modules each.

That decides the shape, and it is the shape this decision already sanctions rather than a
new exception. `core` retires its WHOLE-NAMESPACE MAP like the other eight, and keeps a
PEP 562 guard for the two or three named heavy symbols -- which is precisely "a named
symbol whose deferral is justified by a recorded measurement of import weight" and
nothing more. The measurement above is that record.

This is the outcome the Consequences section anticipated as a risk, and it arrived as the
better case: `core` does not keep the mechanism the other eight lost, it keeps the
BOUNDED exception the original ADR always described, now grounded in numbers rather than
inherited as a habit. The remaining question -- whether those three submodules are heavy
for a good reason or are themselves carrying an avoidable dependency -- is worth asking
before the guard is written, because a fixed root cause would shrink the exception
further.

The 2229-importing-module figure also survived a precise re-count. An AST walk resolving
every relative import found 2542 `from cadrumo.core import` statements across 2278 files
carrying 5552 symbol references, of which 5501 (99.1 per cent) are lazy-map symbols.
`core/__init__.py` defines NO public symbols of its own -- the 51 non-lazy references are
submodule imports that bypass `__getattr__` entirely. So unlike `application/registry`,
`core` has no second uncounted population: retiring its map is the whole job.

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
