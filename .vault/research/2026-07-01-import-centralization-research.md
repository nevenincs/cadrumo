---
tags:
  - '#research'
  - '#import-centralization'
date: '2026-07-01'
modified: '2026-07-17'
related:
  - '[[2026-07-01-import-centralization-adr]]'
---

# `import-centralization` research: `cross-package private-import inventory`

This research inventories every place `src/aeat` bypasses its own package-level
`__all__` boundary — a cross-package private import, a shim/alias module, or a
symbol re-exported from more than one surface — as the discovery pass for the
`import-centralization` campaign. It generalizes the existing
`service-imports-via-top-level-reexports` project rule from a single-service
constraint into a project-wide, mechanically-gated inventory.

## The scanner

`dev/import_hygiene_scan.py` is the campaign's mechanical, read-only discovery
tool. It AST-walks every `.py` file under `src/aeat`, resolves every `import` /
`from ... import ...` statement (including relative imports) to an absolute
dotted module name, and classifies cross-package reaches into three violation
families plus a facade-boundary inventory and a fix-strategy classification. It
modifies nothing.

Re-run with:

```
python dev/import_hygiene_scan.py --top 30
python dev/import_hygiene_scan.py --json inventory.json --top 30
```

Ownership rule the scanner encodes: for a private module `A.B._C...` (first
dotted component starting with `_`, excluding dunders), the owning package is
`A.B` — everything strictly before the first private component. An import is a
violation only when the importer is NOT the owning package itself and NOT a
descendant of it (an intra-package private import, or a package's own
`__init__.py` building its facade, is legitimate and excluded).

An AST-vs-`rg` reconciliation pass confirmed the scanner's static counts against
a live grep sweep: the only discrepancy is 2 sites in `aeat.core.setup_answers`
that use dynamic `importlib.import_module(...)` calls (not static
`import`/`from` statements) as a deliberate circular-import-avoidance
technique — `rg` finds the string but the AST walk cannot resolve a dynamic
target. `rg -n "import_module"` against `src/aeat/core/setup_answers.py`
confirms exactly these two call sites; every other family-1/2/3 count the
scanner reports matches an independent `rg` count for the same target module or
symbol name.

## Facade boundary set

`src/aeat` has 232 `__init__.py` files; 104 of them carry a real, non-empty
`__all__` (a list/tuple/set of string literals) and are treated as the
package's canonical public-export surface. The other 128 `__init__.py` files
are structural-only (no `__all__`) and do not define a facade boundary. Every
cross-package import is classified against this 104-package set. The full
enumeration is in the scanner's `=== FACADE BOUNDARY SET ===` output; the
largest facades are `aeat.domain.calculations.registry` (365 exported names),
`aeat.application.modelo` (262), `aeat.adapters.persistence.storage` (237),
`aeat.application.live` (96), `aeat.domain.transactions` (83), and
`aeat.application.user_profile` (85).

## Family 1: cross-package private imports (2465 total)

An import that reaches `A.B._C...` from an importer outside `A.B` (or its
descendants). Split 866 production / 1599 test-only.

By owning package (target of the reach), the top offenders are
`aeat.domain.modelos` (630), `aeat.application.user_profile` (284),
`aeat.application.workflow` (197), `aeat.domain.calculations.registry` (108),
`aeat.core` (71), `aeat.domain.deadlines` (70), `aeat.domain.iva_compensation`
(65), `aeat.application.calculations` (63), `aeat.application.live` (61), and
`aeat.application.aggregation` (57).

By concrete offender private module reached, the top ten are
`aeat.application.user_profile._orchestration` (137),
`aeat.application.workflow._persistence` (117),
`aeat.domain.modelos._repository` (107),
`aeat.domain.modelos._calculation_repository` (101),
`aeat.domain.modelos._calculation_revision` (89),
`aeat.application.user_profile._testing` (82),
`aeat.domain.modelos._work_unit` (77),
`aeat.domain.deadlines._models` (49),
`aeat.domain.modelos._filing_repository` (39), and
`aeat.domain.modelos._verification_report` (39).

By importer area (top-3 dotted segments), the reach is dominated by
`aeat.application.modelo` (708 sites), `aeat.entrypoints.cli` (466),
`aeat.application.user_profile` (221), `aeat.adapters.persistence` (124),
`aeat.application.calculations` (80), `aeat.application.overview` (78), and
`aeat.application.bucket_maintenance` (70) — the "importer area" side of the
inventory is the consumer-rewrite sizing signal; the "owning package" side is
the promotion-target sizing signal.

## Family 2: shim / alias / pure-reexport modules (8 total)

7 `pure_reexport_shape` hits (a non-`__init__` module whose body is only
import statements plus an `__all__`, zero real function/class definitions) and
1 `english_alias_over_spanish_stem` hit. Reading each hit individually (per
the `aeat-swarm-audit-cadence` substitutability discipline) shows most are
legitimate documented bridges rather than accidental duplication:

- `src/aeat/adapters/outbound/aeat/_playwright.py`,
  `src/aeat/application/workflow/_utils.py`,
  `src/aeat/domain/calculations/registry/applicability.py`,
  `src/aeat/domain/deadlines/taxpayer_model.py`,
  `src/aeat/domain/transactions/_ids.py`, and
  `src/aeat/entrypoints/cli/_schemas.py` — six pure-reexport bridge modules.
- `src/aeat/locales/__main__.py` — a false positive: an entry-point module is
  expected to be a thin `import` + dispatch shape; the classifier should
  exclude `__main__.py` from this heuristic.
- `src/aeat/application/aggregation/_withholding_observations_repository.py` —
  the one genuine violation: a real 282-line M190 percepciones implementation
  under an English-stem name, sitting beside the distinct
  `_retencion_observations_repository.py` (the M180/193 store). This is a
  naming collision, not a re-export shim, and needs a rename (not a merge) to
  `_percepciones_observations_repository.py` per `aeat-spanish-stem-naming`.

## Family 3: redundant / multi-sourced symbols (578 total, scan reported 580)

A symbol reachable from more than one facade `__all__`, or consumed both via a
facade AND directly from a private submodule by an outside consumer. Split by
confidence: 101 `hierarchical_rollup` (a parent umbrella facade re-exporting a
child facade's symbol — e.g. `aeat.adapters.persistence.storage` rolling up its
`.envelope` / `.bucket` / `.crypto` sub-facades; NOT a violation), 68
`name_collision` (same name, different resolved origin — two unrelated symbols,
e.g. two domains each defining their own `Settings`; low priority), and 411
`high` (same or shared resolved origin across non-hierarchical facades, or a
private-vs-facade consumption split — the genuine duplication/leak candidates).

Reading through the `high`-confidence list, roughly ten are genuine multi-
sourced duplicates rather than incidental noise (facade lists both sides of a
recorded relationship). The load-bearing examples surfaced for the ADR:

- `CalculationRevision`, `CalculationRevisionAmendmentKind`,
  `ExternalEvidenceKind`, `WorkUnit` — each declared in BOTH
  `aeat.application.modelo.__all__` and `aeat.domain.modelos.__all__`, with the
  private source in every case `aeat.domain.modelos.*`. `application.modelo`
  is re-exporting a domain-owned symbol as an umbrella convenience.
- `link_transaction`, `suggest_reconciliations`, `verify_link_consistency` —
  each declared in BOTH `aeat.application.invoices.__all__` and
  `aeat.domain.invoices.__all__`, private source `aeat.domain.invoices._service`
  in every case. Same shape as the modelo group, one domain below one
  application umbrella.
- `save_envelope` — declared in `aeat.adapters.persistence.storage`,
  `aeat.adapters.persistence.storage.envelope`, AND `aeat.core.observability`,
  but resolving to TWO distinct private origins
  (`aeat.adapters.persistence.storage.envelope._envelope` and
  `aeat.core.observability._store`) — two unrelated same-named functions, not
  one symbol needing consolidation.
- `DEFAULT_IVA_GENERAL_RATE_PCT` — declared in both
  `aeat.domain.contribuyente.assets` and `aeat.domain.contribuyente.inventory`
  facades with zero private sources and zero consumers recorded by the
  scanner — a benign, single-origin, unused-cross-package entry.
- `OutputLanguage` — declared in both `aeat.core.i18n` and
  `aeat.entrypoints.cli._config`, zero private sources, zero cross-package
  consumers recorded — the CLI config facade's entry is a redundant re-export
  of the `core.i18n` closed-value enum.

## Fix-strategy classification and magnitude

The scanner classifies every (owning_package, symbol) pair consumed
cross-package in PRODUCTION code (test-only consumers excluded from this
sizing) by whether the symbol is already in the owning package's `__all__`:

- 549 distinct (owner, symbol) pairs total.
- 149 pairs NEED FACADE PROMOTION FIRST (symbol absent from the owning
  `__all__`) — 302 production consumer sites depend on these.
- 400 pairs are SIMPLE CONSUMER REWRITES (symbol already facaded) — 937
  production consumer sites just need their import statement repointed.
- 250 distinct production files carry at least one cross-package private
  import.
- 34 distinct owning packages need at least one new promotion.

The heaviest promotion batches by owning package: `aeat.domain.modelos` (24
symbols / 67 sites — `CalculationRevisionId`, `LedgerFilingSnapshot`,
`ModeloError`, `WorkUnitState`, `validate_m347_threshold`, etc.),
`aeat.adapters.outbound.google` (18 symbols / 26 sites —
`apply_export_plan`, `load_client`, `pull_operator_edits`, `run_login_flow`,
etc.), `aeat.core` (13 symbols / 35 sites — `Modelo`, `Period`, `TaxDomain`,
`resolve_active_bucket_id`, etc.), `aeat.application.live` (9 / 12),
`aeat.domain.iva_compensation` (8 / 14), and `aeat.adapters.inbound.pdf`
(7 / 14 — the PDF text-extraction primitives). The heaviest simple-rewrite
batches: `aeat.domain.modelos` (43 symbols / 268 sites),
`aeat.domain.calculations.registry` (37 / 60),
`aeat.adapters.persistence.storage.master_key` (34 / 40),
`aeat.application.user_profile` (22 / 56), `aeat.domain.deadlines` (20 / 48),
and `aeat.application.workflow` (15 / 51).

## Existing narrower gates this scanner supersedes

Two existing tests enforce a narrower version of this boundary today and are
candidates for retirement once the ratcheting gate lands:
`src/aeat/domain/calculations/registry/tests/test_public_api_boundaries.py`
(registry-package-scoped) and
`src/aeat/entrypoints/cli/tests/test_architecture_boundaries.py`
(CLI-package-scoped). Their existing allowlisted exceptions should be seeded
into the new gate's Family-2 shim allowlist / Family-3 pinned-symbol set rather
than dropped.

## Relation to existing rules

This inventory generalizes `service-imports-via-top-level-reexports` (which
mandated top-level-facade imports for one new service) into a project-wide
policy, and is the discovery input for `registry-resolver-family-extraction`
(per-family module placement) and `aeat-spanish-stem-naming` (the
percepciones/retencion naming collision surfaced in Family 2).
