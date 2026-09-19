---
tags:
  - '#audit'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:a9f20766a2ab4c6d4c1576893a71ac33bb45c2490c8cd411352715ab46566832'
related: []
---

# `semantic-consolidation` audit: non-inert package namespaces, censused by construct

## Why this re-census was needed

The lazy-export ADR assembled its population by grepping one identifier,
`_LAZY_EXPORTS`, and a later sweep widened it to `__getattr__`. Both searches
name a MECHANISM, and a mechanism census cannot see the same construct spelled
differently. The plan's Phase `P07` therefore describes "ten further package
namespaces".

Censusing by CONSTRUCT instead -- parsing every `__init__.py` and counting
relative-import re-exports, top-level public definitions, and module-scope call
side effects -- gives **108** non-inert namespaces. The lazy maps were never the
population; they were the visible three per cent of it.

The rule this measures against does not mention laziness at all: package
`__init__.py` namespaces "may not import, bind, alias, lazily resolve, or
re-export project symbols". An eagerly re-exporting facade breaches it exactly
as a lazy one does, and is harder to spot because it looks like ordinary code.

## The population, by kind

### Eager re-export facades (the bulk)

Twelve heaviest, by count of names re-exported through the namespace:

| package | names |
|---|---|
| `domain/iva` | 179 |
| `application/aggregation` | 160 |
| `application/calculations` | 108 |
| `application/filing` | 107 |
| `adapters/outbound/aeat/sede` | 70 |
| `application/storage/calc_sheets` | 66 |
| `adapters/outbound/google` | 61 |
| `core/observability` | 61 |
| `domain/deadlines` | 59 |
| `application/invoices` | 53 |
| `tests` | 53 |
| `domain/filing` | 43 |

These are map deletions plus consumer repointing -- the same shape as the
`portals`, `transactions`, `modelos` and `llm/providers` retirements already
landed, and no harder per symbol, only larger.

### Modules in disguise (23 packages)

These DEFINE production code directly in `__init__.py`, so their namespaces
cannot be made inert by deleting a map; the definitions must relocate first.

| package | re-exports | own definitions |
|---|---|---|
| `domain/contribuyente/inventory` | 14 | 38 |
| `domain/bienes_inversion` | 10 | 21 |
| `core/redaction` | 10 | 18 |
| `core/errors` | 16 | 16 |
| `core/corpus_manifest` | 28 | 13 |
| `core/classification` | 1 | 11 |
| `domain/prorrata_register` | 9 | 10 |
| `domain/contribuyente/assets` | 6 | 8 |

`core/errors` is the one already known to the plan, at 1496 consumers. Seven
others of comparable kind were not in the population at all.

### Module-scope side effects (5)

A namespace that RUNS something on import is the sharpest case, because the
import is load-bearing and deletion is not available:

- `application/registry` -> `import_module('cadrumo.domain.renta')`, a
  cross-domain registration whose comment measures the cost at roughly 613
  modules and 1.3s against a clean interpreter. Any consumer touching this
  package pays that, and the package's own docstring says so.
- `application/calculations` -> `IvaCompensationReconciliationReport.model_rebuild()`
- `entrypoints/cli` -> `_configure_stdio_for_utf8()`
- Two fixture packages under `entrypoints/cli/tests/` deliberately raise on
  import; those are test apparatus, not findings.

The registration cases are dependency inversion done through import side
effects: `domain/renta` registers a referential-integrity check with the
registry validator so the registry never imports renta. The inversion is sound;
siting the trigger in a package namespace is what makes it a finding, because
it converts "touch this package" into "import 613 modules".

## What this changes about the campaign

`P07` cannot close on the ten namespaces it names. Either its completion
criterion widens to the censused 108, or the plan records explicitly what the
standing goal still asks for that the narrower scope excludes -- a campaign may
not narrow its own completion criterion silently.

Nothing here is a regression: every one of these namespaces works today. The
cost is the one the campaign exists to remove -- a contract reachable at two
paths is a contract that gets retyped, and an import-time cost nobody can see
is one nobody removes.

## Method

`ast.parse` over every `src/cadrumo/**/__init__.py`; a namespace counts as
non-inert if it has any relative-import or plain-import name, any top-level
public class or function definition, or any module-scope expression call. The
count is of NAMES re-exported, not import statements. Test-fixture packages are
included in the total and called out where they are apparatus rather than
findings.
