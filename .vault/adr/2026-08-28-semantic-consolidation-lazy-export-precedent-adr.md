---
tags:
  - '#adr'
  - '#semantic-consolidation'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:156fec10e0410b715379a1337f6ffe174e42ef9684223fa5abe14db7e2a1bb73'
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

Retirement is by package, one package per commit, never a tree-wide sweep -- with one
structural qualification found the hard way, stated first because it changes the unit of
work.

ONE OF THE NINE RE-EXPORTS FROM THREE OTHERS. A census of all nine `_LAZY_EXPORTS` maps
for entries naming another package on the list returns exactly one row:

| package | symbols | entries naming another of the nine |
|---|---|---|
| `storage` | 257 | `core` 21, `custody` 17, `crypto` 11 |

The other eight name nothing on the list. So `storage` is an ANCESTOR whose map re-exports
its own descendants' surfaces, and retiring a descendant leaves those entries dangling:
emptying `crypto/__init__.py` broke runtime access to `KEY_SIZE` and ten siblings from
modules that never imported the crypto package at all, because they reached the symbols
through `storage`.

THE CONSEQUENCE FOR THE UNIT OF WORK: a package's consumer population is NOT its direct
importers. An AST census of `crypto` found 56 importing files; the module that actually
broke was in none of them. So retiring a package MUST, in the same commit, repoint every
ancestor-map entry naming it. That is a mechanical step, not a judgement -- but it is
invisible unless looked for, which is why it is recorded here rather than left to the
executor.

It does NOT force the nine into one commit. Eight are independent and retire in any order.
`storage` retires LAST of its subtree, after `crypto` (done) and `custody`, and its 21
`core`-facing entries repoint at core's owning submodules directly, which works whether or
not `core` still has a map. So `storage` does not have to wait for `core`.

With that qualification, the nine still split by shape, and a survey of their `__init__.py`
files found the split that decides the rest of the sequencing:

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

ONE OF THE NINE IS NOT A TARGET, AND MEASURING IT IS WHAT SHOWED THAT. `cadrumo/tests`
carries exactly TWO lazy entries, and its module docstring already argues each one
individually: both defer a domain surface out of an unrelated test's import graph, and it
states in terms that the two "are consequently NOT a template" and that a new shared helper
belongs in a submodule rather than a third row. That is this decision's sanctioned shape
described in prose -- named symbols, stated reasons -- lacking only the measurement this
decision requires.

Measured, three runs, fresh interpreter:

| | modules in `sys.modules` | added time |
|---|---|---|
| `import cadrumo.tests` | 371 | -- |
| plus its two deferred targets | 1672 | +2.73 s |

Deferring two names saves 1301 modules and 2.7 seconds for every test module that touches
any OTHER name on that facade. That is a larger saving than `core`'s entire 357-symbol map,
from two entries.

So `cadrumo/tests` KEEPS its `__getattr__`. It is not an unmeasured whole-namespace export
map; it is the bounded exception, applied correctly, and the table above is the record it
was missing. The retirement population is EIGHT packages and 1112 symbols, not nine and
1114.

A DEFERRAL IS ONLY REAL IF SOMETHING REALISES IT, and that turns out to decide package
disposition more than the paper figure does. A module-level `__getattr__` defers only when a
caller imports the MODULE and never touches an attribute; `from X import Y` fires it at
import time and pays for Y's owner immediately. So the honest measurement is not "what does
the map defer" but "what does a real consumer pay".

Measured that way, two packages answer oppositely:

| package | eager | one real symbol | verdict |
|---|---|---|---|
| `domain/modelos` | 625 | 605 | deferral realised by nobody -- RETIRE |
| `application/filing` | 1271 | 749 | saves 522 -- KEEP a bounded guard |

`domain/modelos` has zero plain `import` statements tree-wide and its cheapest owner alone
drags 167 modules, so its twenty owners share a heavy floor no bounded guard can protect.
`application/filing` has no such floor: `._complementaria` (+259) and `._export` (+152) are
79 per cent of its weight, and a `build_draft` consumer genuinely avoids both.

`domain/modelos` also names a trap worth recording: the naive middle path -- keep the
facade, make `__init__` eager -- would REGRESS the 64 consumers that touch only cheap owners
from ~236 modules to 625, while full retirement improves them to ~168. Retirement dominates,
but only the repoint-and-delete kind, never the make-it-eager kind.

This is worth stating plainly because the campaign nearly deleted the one instance that was
right. The nine were assembled by searching for a MECHANISM -- `_LAZY_EXPORTS` -- and a
mechanism census cannot distinguish the sanctioned use from the copied one. Only applying
this decision's own test, symbol by symbol with a number attached, separates them.

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
