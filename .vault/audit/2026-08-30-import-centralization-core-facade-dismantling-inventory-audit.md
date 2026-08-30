---
tags:
  - '#audit'
  - '#import-centralization'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:dc9c1d0d2134baeadf78e2d97cd4d57b5600998267779d395c63634a591bab16'
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
