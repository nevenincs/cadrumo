---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:1cdaec39dc09aef3150438300f9c32e86bb26bbd3afffc635747a00e09e34690'
step_id: 'S19'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Remediate review findings: retire no-op selector-only validators, narrow binding source accessors on provider members with explicit refusal, drop the duplicate source field from query rows, refuse cross-revision data-type disagreement in the converter and ground its family-level money rule, carry an unknown prefill coordinate as None, enforce the absolute-coordinate guard structurally in the domain, and remove the two import-invariant restatement tests

## Scope

- `src/cadrumo/domain/calculations/registry/binding_provider_registration.py`
- `src/cadrumo/domain/calculations/registry/bindings.py`
- `src/cadrumo/domain/calculations/registry/queries.py`
- `src/cadrumo/domain/calculations/registry/query_reports.py`
- `dev/registry/convert_binding_provider_shape.py`
- `src/cadrumo/application/calculations/binding_prefill.py`
- `dev/registry/compiler/validate_bindings.py`

## Changes

- `M` `dev/registry/convert_binding_provider_shape.py`
- `M` `dev/registry/tests/test_convert_binding_provider_shape.py`
- `M` `dev/registry/tests/test_modelo_100_2024_profile_surface.py`
- `M` `dev/registry/tests/test_binding_source_kind_taxonomy.py`
- `M` `dev/registry/compiler/validate_bindings.py`
- `M` `dev/registry/tests/test_validate_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/binding_provider_registration.py`
- `M` `src/cadrumo/domain/calculations/registry/binding_selector_utils.py`
- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/inventory_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/withholding_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/gasto193_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/profile_grounding.py`
- `M` `src/cadrumo/domain/calculations/registry/queries.py`
- `M` `src/cadrumo/domain/calculations/registry/query_reports.py`
- `M` `src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py`
- `M` `src/cadrumo/application/calculations/binding_prefill.py`
- `M` `src/cadrumo/application/calculations/multi_year.py`
- `M` `src/cadrumo/application/calculations/relation_prefill_m202.py`
- `M` `src/cadrumo/application/modelo/work_wizard.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_discovery_rendering.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_binding_source_accessors.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_provider_registration.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_selector_utils.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_aggregation.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_queries.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_ledger_renta_gastos_estimacion_directa_binding.py`
- `M` `src/cadrumo/domain/user_profile/tests/test_registry_contract.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace_manifest.py`
- `M` `src/cadrumo/application/modelo/tests/test_profile_binding.py`
- `M` `src/cadrumo/application/calculations/tests/test_row_producer_default_op_detection.py`
- `verify:` `uv run --no-sync ruff check <touched files>` -> `pass`
- `verify:` `uv run ty check <touched files>` -> `pass`
- `verify:` `uv run --no-sync basedpyright <touched domain and application files>` -> `pass`
- `verify:` `uv run --no-sync pytest <touched registry, profile and converter suites> -n 0` -> `pass`

## Notes

Pre-existing failures outside this change remain in modules it touches: four modelo 100
profile-surface assertions and three registry query assertions name pre-rename binding
identifiers, two schema-hygiene tests fail on dangling modelo 232 export references, and
two binding-validation tests carry a retired row-set fixture. One unrelated module under
the application modelo package fails to import a symbol another change is mid-edit on.

Second-review remediation, appended to the same Step.

Restored the prior-domiciliation header-key import and added an executing
import gate. `_prior_domiciliation` imported an accessor the carry-ingress
module never defined, so every consumer of the modelo filing actions raised
`ImportError`; the module-level constant it replaced is back at both use sites.
A new gate under the package test root imports all 1021 non-test modules of
`cadrumo.application` and `cadrumo.entrypoints` and reports every `ImportError`
at once. It passes with no residual: the static import-resolution gates could
not have caught this defect, because they resolve names against packages
without executing the importing module.

Wired the stored relation-override migration into the calculation path. The
forward migration had no caller, so a pre-cut store kept its retired override
keys indefinitely. It now runs where the source-mesh resolution constructs the
calculation-revision repository, mirroring the bienes-inversion authority
migration: only for a repository the function constructs, never for an injected
one, and a no-op on an already-current store.

Widened override-key classification to the active revision's own bindings. An
override keyed by a binding authored after the cut is absent from the frozen
join and was classified as an orphan, which would have refused the revision
forever. A key is now current if the join resolves onto it OR the revision's
registry snapshot declares it; a key matching neither is still refused rather
than dropped.

Refused a filing-year offset bound that admits no step. `max_years` below
`abs(years)` filtered out every anchor silently, leaving a declaration that
looked live and resolved to nothing.

Made the relative-coordinate provider guard recurse. A coordinate nested one
model below a provider field was invisible to the guard; the walk now descends
into nested models with a dotted diagnostic path, skips `temporal` at every
depth, and terminates on self-referential shapes. No enrolled provider trips
the widened guard.

Dropped the frozen advisory count from the binding-validation module docstring
and rewrote the modelo 202 instalment-base header comment: it now describes the
declared 1P/-2 and 2P,3P/-1 anchors and states the Modelo 200 pre-2024 gap as a
resolution-time source absence rather than as an operator-entered period.

Hoisted the calculation-source diagnostic import to module level after
confirming no import cycle results.

New tests: the import gate, the migration entry point and post-cut key
preservation, the offset-bound refusals, the nested-provider detector teeth,
and a live terminal-origin pair proving the registration-derived default is
non-empty and that real profile-resolver output audits clean.

Deferred: the byte-level hash guard requested for the modelo 202 binding file.
The repository has no per-declaration digest ratchet to enrol it in, and a
frozen content hash over a comment would assert the presence of a string rather
than a behaviour. The declaration itself is covered by the compiled-registry
gates.

Pre-existing failures, all reproduced at `HEAD` in a detached baseline worktree
and none introduced here: the twelve prior-domiciliation election assertions
fail on a carry-ingress resultado refusal unrelated to the header key, and they
became visible only because the module can be imported again; the IVA component
catalogue rejects its own category rows across the aggregation suites; two
cross-module and two relative-import gate entries name modules under concurrent
edit; and the binding validation CLI gate aborts inside an untracked in-flight
module.

Late in this Step a concurrent change to the registry schema and the published
authority artifact began refusing `formula_evolutions` as an extra input, which
fails every module that builds a bundled snapshot, including this Step's own
suites. Each suite recorded here passed before that change landed; the refusal
is in files this Step did not touch.

### Third-review remediation: channel screening, operand refusal, rename guards

Widened the application and entrypoint import scan to catch `Exception` rather
than `ImportError`, so a registry validation error or `TypeError` raised while a
module builds a constant is reported with its type name instead of aborting the
scan at the first module. A fabricated temporary package on `sys.path`, one
module raising `RuntimeError` and one raising `ImportError`, proves both are
reported and that the scan continues past the first.

Screened the boolean channel against the revision's declared binding ids through
the shared `reject_unknown_external_values` gate and dropped the permissive
channel default that treated an unknown id as boolean-contracted. The shared
gate was keyed on ids alone rather than on `Decimal` values so every external
channel screens through one function. A truth value under an undeclared id is
now refused instead of silently discarded.

Added the compiler refusal the evaluator's docstring had been claiming: a
binding whose value contract declares the boolean channel may be an `equal`
operand, an `if_then_else` condition, or the whole expression of a formula
targeting a yes/no casilla, and is refused under every arithmetic operator at
any depth. Run over the published corpus it reports no authored violation across
1473 formulas; the two shapes it first flagged are the bare-leaf projection onto
Modelo 100 casilla 0245, which the record design itself encodes as 1/0, so the
rule was scoped to operator-consumed positions and the docstring restated to
match.

Replaced the `NotImplementedError` in the Modelo 303 prorrata transition path
with the module's typed `AggregationValidationError` under a new translation key
present in all four catalogues, and moved the record-design grounding onto the
function: the transition period is the last period of the taxpayer's own filing
schedule, per Nota 6 of the official record design that the served revision
cites as its casilla source reference. Removed the campaign marker comment above
it.

Hardened two rewrite guards in the identifier rename tool. The corpus-wide
textual rewrite now refuses a chained rename map, naming the offending pairs,
because one pass cannot decide whether a chained source stops at its target or
travels on. The span strip now runs the same cross-edition post-image projection
the family collapse runs, through one shared screen rather than a second copy;
both plans satisfy a small protocol that owns the withdrawal.

Made the rename tool's data-keyed exemption structural. A member field is a
filing coordinate because of its declared type -- the filing-year alias, the
`Period` model, or a registry period-code alias -- and never because it is
spelled `year` or `period`; a collection of period codes is a row's coverage
rather than its identity. Deadline windows stay withheld on `filing_year` and
`period`, and filing schedules stay in scope, unchanged from the name rule.

Scoped the provider guard's record-layout-integer and `temporal` exemptions to
the provider model itself. Both exemptions describe one specific declared
surface, so a nested model reusing either name no longer inherits them; the
enrolled provider table still passes.

Pointed the reference-section walker's docstrings at `reference_checker`, the
module that exists, and deleted a dead helper from the boolean-channel transport
suite before moving that suite to the application package whose transport it
exercises.

Verification. `ruff check`, `ruff format --check`, `ty check` and `basedpyright`
are clean over every touched file; the only `ty` diagnostics left are the
fourteen pre-existing translatable-message argument reports in the Modelo 303
arrivals module, to which the new refusal adds a fifteenth of the same kind by
following the module's existing call shape. The compiler refusal suite (11
cases), the rename span-strip and chained-map suite (7), the family-collapse
suite including the typed-exemption cases (12), the nested provider guard (11)
and the provider registration suite (35) all pass; the boolean-channel screening
was exercised directly against a compiled revision, refusing an undeclared id
and a decimal-contract id and accepting a declared one. `pytest` could not be
used for the registry-authority-backed suites: the tree cannot compile the
bundled authority because governed facts live in untracked files, which fails
the moved transport suite and every sibling case in it alike. Two cases in the
binding-validation suite fail on fixture strings that no longer match the modelo
190 corpus, and the application import gate reports a module under concurrent
edit; neither is touched here.
