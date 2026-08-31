---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:92b4dd711502d244c43c6dfd9cf0ee9fe6b9869f0d4271c73a2c825306778046'
step_id: 'S233'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Give the inert-namespace rule a standing tree-wide gate, because it currently has none. MEASURED BY AST OVER src/cadrumo 2026-08-31: of 283 package __init__.py files, 84 carry project imports or their own definitions, which aeat-architecture-boundaries forbids outright -- 'Package __init__.py namespaces are inert and may not import, bind, alias, lazily resolve, or re-export project symbols.' THE 84 DECOMPOSE INTO THREE KINDS NEEDING THREE DIFFERENT REMEDIES, and the single number hides the two that matter most. (1) FOUR LAZY PEP 562 FACADES, which the rule prohibits by name in its list of banned constructs alongside re-export modules and aliases: core/__init__.py at 1236 lines, adapters/persistence/storage/__init__.py at 912, entrypoints/cli/__init__.py at 366, and tests/__init__.py at 207. Each resolves names inside __getattr__, so nothing binds statically. These are the highest-reach namespaces in the tree and the most explicitly forbidden. (2) TWENTY-TWO NAMESPACES DEFINING PRODUCTION CODE -- a module wearing a package's name -- led by domain/contribuyente/inventory/__init__.py with 53 definitions across 1690 lines, core/redaction with 34 across 1141, domain/bienes_inversion 25, core/corpus_manifest 22, domain/prorrata_register 20. The remedy is a hard move to a semantically named public module, not a repointing of consumers. (3) FIFTY-EIGHT PURE RE-EXPORT FACADES, the shape the rule was written against, led by application/aggregation with 33 project imports and application/calculations with 21; the remedy is repointing consumers at defining modules. THE ENFORCEMENT GAP IS THE POINT OF THIS ROW AND WAS CHECKED RATHER THAN ASSUMED. dev/quality/import_hygiene_scan.py already carries an inert_modules spec field and a 'non-inert package import' diagnostic, so the detector EXISTS, but the only assertion wiring it up is test_components_facade_has_no_imports_or_exports, over entrypoints/tui/components alone; the other 282 packages are unevaluated. Two neighbouring gates were read and are NOT this gate: test_no_dunder_init_module_imports forbids the `from ..__init__ import x` submodule spelling for its double-execution hazard and says its scope is deliberately narrow, and test_facade_export_lazy_shapes exists to make the facade SCANNER model PEP 562 dispatch correctly -- it accommodates lazy facades rather than forbidding them, and its own docstring names cli and domain.user_profile as shipping that shape. So the tree ships a construct the architecture rule bans while the tooling around it treats it as ordinary. That tension should be resolved by a ruling in one direction or the other, not left implicit. DELIVER: populate inert_modules from the real package set and assert it tree-wide, with any genuinely-exempt namespace named and reasoned rather than silently outside the denominator. CAVEATS: re-measure before quoting, because a relocation sweep is actively promoting modules out of core; and this row claims only that none of the 84 is currently CHECKED, not that all 84 are equally wrong. Sequence the gate before the cleanup, or the cleanup has nothing holding it

## Scope

- `dev/quality/import_hygiene_scan.py`
- `dev/tests/test_import_hygiene_gate.py`
- `src/cadrumo/**/__init__.py`

## Changes

- `M` `dev/quality/import_hygiene_scan.py`
- `M` `dev/quality/import_hygiene_baseline.json`
- `M` `dev/tests/test_import_hygiene_gate.py`
- `verify:` `uv run --no-sync pytest dev/tests/test_import_hygiene_gate.py -n0` -> `pass`

## Notes

The row's headline measurement is superseded by the one taken while building the
gate: 32 non-inert namespaces of 284, not 84 of 283. The retirement campaign
landed a great deal between the two readings.

The row's three-kind decomposition is superseded by four breach kinds, one per
verb the rule forbids: import binding (32), symbol export (30), own definition
(17), lazy resolution (3). Three kinds were tried and rejected on evidence.
`core` and `entrypoints.cli` each carry all four, so a precedence-ordered
classification files them under lazy resolution alone and hides that they also
define production code -- the exact collapse this row warned the single number
was causing.

The gate is a named-set ratchet keyed on `(package, breaches)`, with set
equality checked in both directions, so a namespace that stops re-exporting but
keeps its own definitions reads as partially paid rather than done. No count is
a pass condition. Nine planted-namespace fixtures and three inert controls prove
it bites. The baseline change was purely additive -- 279 insertions, zero
deletions -- so no pre-existing family was widened to accommodate it.

DEFERRED, NOT DELIVERED: the row also asked that the tension between this rule
and `test_facade_export_lazy_shapes`, which accommodates the PEP 562 facades the
architecture rule bans by name, be resolved by a ruling in one direction. That is
ADR-grade and is not settled here. The gate records the three lazy namespaces as
breaches, which states the rule's position without retiring the accommodating
test.

The gate's value was confirmed against unrelated work the same day.
`core.errors.registry` is one of the 32, and its non-inertness is what makes
`core.errors.error_codes` circular with it -- a cycle that module already
carries a deliberate deferred-binding window in order to survive.
