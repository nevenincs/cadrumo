---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:78b55e1e25baa5b173eefbc8fdc43be9a16a9d6f477a6ec3e74cc96786135a5e'
step_id: 'S01'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---

# Discover token-naming modules by AST scan instead of a hand-listed tuple, and rebind the nine surviving twin declarations to the authority

## Scope

- `src/cadrumo/application/calculations/tests/test_iva_compensation_casillas.py src/cadrumo/application/calculations/__init__.py src/cadrumo/application/calculations/_iva_compensation_annual_partition.py src/cadrumo/application/modelo/_filed_revision_observation.py src/cadrumo/application/modelo/_iva_wallet_gate.py`

## Description

The drift gate watched a hand-listed tuple of three modules. Its own stated
reasoning for replacing an import inventory was that an inventory asserts
something the code is free to change, and that applies verbatim to its own
subject list. Nine twin declarations stood outside the watched set, three of them
in the module on the live local filing path, where a stale literal would stop the
refunded rewrite from finding the row it must re-stamp and carry a full generated
credit into the next quarter with no gate red.

## Outcome

Subjects are now discovered rather than enumerated. An AST sweep of the
production tree finds every module that names an authority token, either as a
string literal or through a module-level import of an authority constant, and
only those few modules are then imported for the identity verdict. Parsing rather
than importing keeps the sweep independent of import cost.

Discovery grew the watched set from three modules to eleven, and it now includes
the registry binding validator and the AEAT-capture persistence path, neither of
which the hand list named.

The nine twins were rebound. The two same-package sites bind through the private
authority module; the two application modelo sites bind through the owning
package's public facade, which required promoting four constants to the
calculations package all-list as a precondition of the consuming change.

Two discovery refinements were needed. A bare-numeric token is excluded from
literal discovery: 71 collides with any unrelated module containing that string,
and because CPython interns it the identity verdict could not rule on a twin of
it anyway, so including it only manufactures subjects. Import discovery is
restricted to module-level statements, since a function-local import binds the
authority's own object at call time and leaves nothing in the namespace to read.

The interning limitation stays recorded honestly. Discovery does not close it: it
finds such a module, and identity then cannot discriminate its twin. Only the
dotted registry ids are covered, and the docstring says so.

## Verification

Proven test-first, which needs no mutation window at all. The rewritten gate was
run against unmodified production code and observed to red on exactly the three
twin modules, each failure naming the attribute and the token. It passes after
the rebinding.

The touched suites pass at HEAD. The type checker and the linter are clean on
every touched file.

Import-linter could not run tree-wide because an unrelated module carried a
syntax error in live peer work in progress. It was run instead against a copy of
the python sources with only that peer file restored to its committed bytes,
leaving the peer working tree untouched: the four contracts this change could
affect are all KEPT, and neither of the two broken contracts names any file
touched here.

## Notes

This change was swept into HEAD by a broad-commit agent while still being edited,
and split across three separate commits. The tree was transiently red for about
three hours as a result, because the first of those commits took the gate with
container detection absent while the registry literals were still in place. The
later commits closed it and HEAD is green.
