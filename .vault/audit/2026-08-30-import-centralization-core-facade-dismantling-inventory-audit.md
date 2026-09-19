---
tags:
  - '#audit'
  - '#import-centralization'
date: '2026-08-30'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:ef1ef4e00d1e83b86e6252683c23a7bb8d21906e39c7e8cfa5614441f0f20913'
related:
  - "[[2026-07-01-import-centralization-adr]]"
---

# `import-centralization` audit: core facade dismantling inventory

Measured 2026-08-30 against the working tree. `cadrumo/core/__init__.py` is 1,236
lines and resolves part of its surface through a PEP 562 `__getattr__`, the export
shape `aeat-architecture-boundaries` prohibits outright. This records what
dismantling it actually costs, because the cost is not where it looks.

## The headline: it is promotion-bound, not rewrite-bound

    365 exported names
  5,812 symbol-import sites
  5,110 sites blocked behind a module PROMOTION   (88%)
    702 sites repointable immediately             (12%)
     85 private modules needing promotion

The obvious plan -- repoint every `from cadrumo.core import X` at the module that
defines `X` -- is WRONG for 88% of the surface. 230 of the 310 resolvable symbols
are defined in underscore-private modules, so a naive sweep would replace one
prohibited facade with roughly five thousand cross-package private imports, which
the same rule forbids. The order is forced: promote the module to a public name,
then repoint consumers, then remove the facade line. Each promotion is one atomic
relocation commit.

## Cost concentration

Five private modules carry 3,045 of the 5,812 sites -- over half the campaign:

| sites | module | symbols |
|---:|---|---:|
| 1093 | `core._casilla_id` | 3 |
|  827 | `core._period` | 13 |
|  434 | `core._models` | 2 |
|  402 | `core._operator_action_enums` | 6 |
|  289 | `core._modelo` | 4 |

Those five are the whole first wave. `_casilla_id` and `_period` alone are 1,920
sites, and they carry the two most-imported symbols in the codebase (`CasillaId`
at 595 direct references, `Period` at 733).

The largest already-public homes are `core.aggregation` (250 sites),
`core.operations` (168), `core.external_constants` (50) and
`core.source_connectivity` (42). Those, plus the rest of the public tail, are the
702 sites that need no promotion and could land as a first, self-contained slice.

## Sequencing this campaign

1. **Public slice first (702 sites, no prerequisite).** Repoint every symbol whose
   defining module is already public. Lands independently, proves the mechanics,
   and shrinks the facade before any rename.
2. **Promote by descending site count.** `_casilla_id`, `_period`, `_models`,
   `_operator_action_enums`, `_modelo`. One module per atomic commit: rename,
   sweep consumers, update the facade, re-run `apidocs scaffold` for the stub
   rename, and confirm clean collection immediately before and after.
3. **Tail.** The remaining 80 private modules, most under 30 sites each.
4. **Remove the facade and the `__getattr__`** only once nothing imports through
   it, and prove it with a zero-consumer measurement rather than a passing suite.

## Two hazards this campaign must respect

**A sweep tool that rebuilds its target set from the live tree is dangerous here.**
Re-running one after the tree moved rewrote 483 files instead of the intended ten,
including working `core.errors` imports. It was caught on the file count, verified
as imports-only with no peer content, and reverted before any commit. Pin the
target set explicitly per run and diff the file count against the expectation
before writing.

**Lazy edges do not fail at import.** A `DeferredTarget`, and worse an f-string one,
resolves only when the verb runs, so an emptied namespace leaves no collection
error at all -- sixteen CLI enum targets were already dead and exactly one surfaced.
Every wave of this campaign must finish by resolving every first-party
`DeferredTarget`, not merely by collecting cleanly.

## Blocked at time of writing

The campaign could not start on 2026-08-30. Tree-wide collection reported 919
errors from a single cause outside this work: `core/errors/_registry.py` and
`core/errors/error_codes.py` are 98.6% identical twins of the same error-code
registry. `hierarchy.py` binds codes through `error_codes`, while `core/errors/__init__.py`
and every `registry/_*.py` declaration table import from `_registry`, so
declarations land in one table and validation reads the other -- surfacing as
"CadrumoError subclass ... AuthError is missing a declared ErrorCode registry entry".

That duplication is a promotion whose private original was never deleted, and it
is mid-flight and NOT actionable from outside: `error_codes.py`, `hierarchy.py`,
`not_found.py` and `severity.py` are UNTRACKED, and the commit that repointed the
dangling references was reverted at `eafd3f70cc`. Repointing consumers at
`error_codes.py` would commit references to files that are not in the repository.
It belongs to whoever holds those uncommitted files.

Until that lands, no slice of this campaign is verifiable, and an unverifiable
import sweep of the innermost package is not worth its risk.

## Outcome: zero remaining sites

The campaign ran to completion on 2026-08-31. Measured against the same method
that produced the 5,812-site estimate: **0 facade sites resolvable to a core
module, and 0 private modules left directly under `cadrumo/core`.**

All 85 private modules were promoted to public names and every consumer repointed,
in batches that each landed the rename and its consumer sweep together so the tree
was never left with a repointed consumer and an unrenamed module. The 24
`DeferredTarget("cadrumo.core", ...)` string targets, deliberately left in an
earlier pass because their homes were private, were repointed last -- the
promotions are exactly what unblocked them.

The 49 imports that remain against `cadrumo.core` are SUBMODULE imports
(`from cadrumo.core import config, logging, external_constants, bucket_pointer,
aggregation`). Those are not facade re-exports and are correct as they stand.

### The facade itself is NOT removed, and should not be

`core/__init__.py` keeps its PEP 562 `__getattr__` and its 357-entry
`_LAZY_EXPORTS` map. That looks like the obvious last step and is the one thing
this campaign deliberately did not do.

`core/tests/test_early_init_facade_imports.py` documents why. The package once
bound most of its surface eagerly and served a few names through a `__getattr__`
defined near the END of `__init__`. Any module imported EARLIER in that file which
reached the settings validator asked a half-built package for an attribute whose
accessor did not exist yet, and `import cadrumo.core` failed for the whole
process -- the tree became unimportable for every agent until the chain was backed
out. The facade now resolves its entire surface lazily and imports no submodule
while it executes, precisely so there is no earlier module to reach back from.

So this `__getattr__` is load-bearing against a real, once-observed outage, not a
re-export of convenience. Removing it is an ADR-level decision about that import
cycle, not a cleanup, and it must not be done on the strength of "the rule
prohibits PEP 562 export maps". What the campaign achieved is the part that
mattered: nothing in production depends on the facade to reach a symbol any more,
so the map now serves only a handful of core's own tests.

### Rewriter defects, each found by the tree and each fixed in the tool

Every one of these silently produced a WRONG rewrite rather than an error, which
is why the count check before writing and the collection check after are both
mandatory:

- **Scope.** The relative-import rule was not scoped to core, so `from ._models
  import` was rewritten inside every other package owning a `_models.py`.
  Collection hit 800 errors. Repair restores an import only where the package
  genuinely lacks the public module, so it cannot mask a real promotion.
- **Over-correction.** Scoping it to "files directly in cadrumo/core" then broke
  `from .._hex import` in `core/identity/`, which legitimately means `core._hex`.
  The rule now RESOLVES the dots against the tree instead of guessing by
  directory, which settles both cases from one rule.
- **A guard that was always true.** The resolution rule carried a "core/_OLD.py
  does not exist" check, but the rename runs at the END of a sweep, so inside core
  it was always true and core's own files were skipped every time.
- **Prose uses a shorter form.** Docstrings say ``core._x``, not
  ``cadrumo.core._x``, so six `:mod:`/`:class:` references survived the qualified
  replace. The lookahead added with the fix stops `core._storage_taxonomy` from
  swallowing `core._storage_taxonomy_locations`.
- **PEP 695 type aliases** (`type CasillaId = ...`) are `ast.TypeAlias`, not
  assignments, so `CasillaId` was invisible and its 595 references were nearly
  missed.
- **The aliased submodule form** `from .. import _x as owner` was explicitly
  skipped by the rule that handled the bare form.

### Operational notes

Transient `OSError 22` writes on this share abort a sweep mid-way and leave a
promotion half-applied -- consumers repointed, module not renamed. The tool
retries writes, and the trailing `git mv` needs its own retry because it loses
lock races against concurrent agents. `--pathspec-from-file` is required for
commits: these file sets run past the argv limit.

The eight residual collection errors throughout belonged to concurrent uncommitted
relocations under `adapters/persistence/storage` and `application/aggregation` and
were excluded from every commit in this campaign.

### Postscript: parse the rendered source before writing it

The sweep's worst defect was not a wrong rewrite, it was an UNPARSEABLE one, and
it is worth stating separately because the blast radius is categorically larger.

One heuristic indented any column-zero `from X import` whose next non-blank line
happened to be indented -- true for a multi-line import, a dict literal, a wrapped
call. It rewrote 2,604 files in a single pass and left `IndentationError` at module
scope, which makes the module AND every package importing it unimportable. At peak
a peer measured 3,192 syntax errors across `src/cadrumo`. `cadrumo/tests/__init__.py`
was among them, which the root conftest imports, so ALL pytest collection died.

Three second-order effects none of which are visible from the sweeping session:

- **A background commit-retry loop stages from disk at attempt time.** Another
  session's retry loop picked up corrupted files and would have committed them
  under ITS commit message; that session caught seven of thirteen in one batch.
  A rewrite defect therefore lands in history attributed to somebody else.
- **`lint-imports` aborts on the first syntax error** and prints no tally, so the
  layering gate evaluates ZERO contracts while appearing to be one narrow
  complaint. A gate that reports nothing reads as green-adjacent.
- Peers correctly refuse to repair files that look like live edits, so the damage
  persists and blocks their lanes rather than being fixed by whoever hits it.

**The guard is one line and belongs in every source rewriter:** `ast.parse` the
rendered text and skip the write if it raises. Microseconds against a rewrite
already being done, and it would have caught every instance here.

Recovery that did NOT destroy concurrent work, for the next person: restore HEAD's
indentation only on lines whose content is otherwise byte-identical (so peer edits
survive), then repair the remainder verified by COMPILATION rather than by pattern
matching -- de-indent a candidate, compile, keep it only if it parses. Reverting
whole files with `git checkout` would have discarded peer edits in the same files.
