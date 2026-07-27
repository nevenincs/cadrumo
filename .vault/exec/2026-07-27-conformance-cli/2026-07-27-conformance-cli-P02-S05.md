---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S05'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# lift the registry-wide external-oracle grounding fold (per-modelo oracle inventory, revision selection, both-direction honesty facts) into a new importable module exported through the registry facade

## Scope

- `src/cadrumo/domain/calculations/registry/_external_grounding.py`

## Description

- Add `ExternalOracleCorpus` to `src/cadrumo/core/_external_oracle_corpus.py` as the
  closed source-kind taxonomy over the two bundled oracle corpora, exported through
  the core facade. The `aeat_manual_worked_example` member's value is byte-identical
  to the `source_kind` token those payloads already store, so a stored token hydrates
  to its member; the replay corpus declares no such token and its member simply names
  the corpus.
- Add `src/cadrumo/domain/calculations/registry/_external_grounding.py` carrying the
  fold as strict frozen pydantic models: `ExternalOracleEvidence` (one payload's
  expected-value inventory attributed to a modelo and filing year),
  `UnattributedOraclePayload`, `ExternalOracleInventory`, `ExternalGroundingFinding`,
  `RevisionExternalGroundingRow`, and `RegistryExternalGroundingAudit`. Both
  finding-kind axes are module-local `Literal` aliases, matching the sibling coverage
  ledger's `CoverageGateStatus` shape.
- Expose `load_bundled_external_oracle_inventory`, `build_external_grounding_audit`,
  `audit_bundled_external_grounding`, and `select_revision_for_filing_year` plus every
  model through the registry package's public top-level facade.
- Consume `PeriodSelector.includes_year` for revision year coverage instead of
  re-deriving the discrete-years and `year_from`/`year_to` span logic, which the
  trapped implementation had hand-rolled alongside the schema method that already
  owned it.
- Record a payload the fold cannot attribute as a typed attribution gap rather than
  discarding it with a bare `continue`, and surface evidence that resolves to no
  revision the same way.
- Take the modelo definitions as an injected argument with an explicit
  `registry_validated` stamp, so a caller holding the validating authority folds its
  own snapshot while the bundled convenience reads the non-validating loader and
  labels itself degraded.
- Regenerate the API reference stubs for the two new modules and land the parent
  toctree deltas with the source change.

## Outcome

The registry-wide external-grounding facts are importable for the first time. The fold
emits 90 rows over the bundled registry, attributes 20 of the 21 bundled oracle
payloads, and reports 0 findings in either honesty direction.

Grounding is surfaced as coverage of independent checking and documented as such on
both the per-revision and registry-wide properties, never as a correctness score. The
numerator is the declared grounding intersected with the reconciled set, which is
exactly the per-verdict computation the verification layer already performs, so the
registry-wide and per-filing signals are one quantity read at two scopes. Registry-wide
coverage measures 0.0460 today; the highest per-revision values are 1.000 for the three
single-expectation IVA group revisions and 0.144 for Modelo 100 filing year 2024 over
its 181 reconciled casillas.

Revision content is read from compiled definitions, never from a fragment-directory
listing, and the bundled entry point stamps `registry_validated=False` because it
deliberately uses the non-validating loader to survive concurrent registry edits that
the validating authority would refuse outright.

Verification, all at the commit:

- `ruff check` and `ruff format --check` over the five authored files: `All checks
  passed!` and `3 files already formatted`.
- `python -m dev.quality.types`: 9 `ty` and 9 `pyright` diagnostics, none in the
  authored files; every diagnostic sits in unrelated peer-owned modules.
- Mutation proof that the fold is not vacuous, run against the real registry: starving
  the inventory of manual-oracle evidence produces 54 unevidenced-declaration findings
  with `ok = False`; injecting an oracle figure for a casilla that is neither computed
  nor enrolled produces 1 stranded finding with `ok = False`; the unmutated control
  reports 0 findings with `ok = True`.
- Strict mode refused a bare string in the corpus field during that proof, confirming
  the enum is validated at the boundary rather than silently coerced.
- `python -m dev.docs.apidocs scaffold`: `Scaffolded 4 changed stubs, left 1230
  unchanged, removed 0 stale stubs`, the four being the two new stubs and their two
  parent toctrees; no peer module was swept in.
- `pytest dev/docs/tests/test_docs_build.py`: `17 passed in 34.67s`, so the new stubs
  build clean under the nitpicky gate.
- `pytest src/cadrumo/tests/test_docstring_core_struct_links.py -m docs`: `3 passed in
  15.79s`, after the gate correctly caught two missing core-struct cross-links on first
  run and they were added.
- `pytest --collect-only -q src/cadrumo`: `14844/18181 tests collected (3337
  deselected) in 39.58s`, no collection errors.
- `pytest src/cadrumo/core src/cadrumo/domain/calculations/registry -m "unit or
  integration"`: `1 failed, 3877 passed, 2 warnings in 151.29s`.

## Notes

The one scoped-suite failure is `test_period_combined_string_gate.py::
test_repo_has_no_unallowlisted_combined_period_strings`, whose findings all sit in the
sanitizer fixtures and a declaracion extraction test. Two further failures appeared in
the import-hygiene gate, over an underscore-named reach in a sanitizer test. All four
implicated files are byte-identical to HEAD, and their debt baseline is unmodified, so
those reds are properties of HEAD owned by other campaigns rather than consequences of
this step. Nothing here touches period strings or adds an underscore-named cross-package
reach.

One bundled manual oracle for Modelo 303 names no filing year in its filename, so the
trapped implementation dropped it silently and its four AEAT figures sat outside both
honesty directions with nothing reporting their absence. It is now reported as an
attribution gap. Attributing it properly, by trusting the modelo and filing year the
payload itself declares, was measured before being ruled out: three of its four figures
are neither computed nor enrolled in the Modelo 303 revision covering 2025, so
attributing it would turn a green gate red over a defect this step did not create.
Widening the attribution rule is therefore deferred rather than taken silently, and the
gap is now visible data instead of an invisible skip.

Both governance enums for the finding axes were kept as module-local `Literal` aliases
rather than promoted to core, following the sibling coverage ledger; only the corpus
source-kind, which is a stored token read on both sides of the shipping boundary, went
to core.

The mandatory semantic discovery probe could not run at first: the search service had
been restarted by another process and its code index was truncated to roughly 1,057 of
4,669 files, with the rebuild job failed on a watcher collision and no watcher armed to
retry. Searches still answered from the partial index, which is the failure mode that
returns confident nonsense, so discovery was held until the index was rebuilt to 57,392
sections and the probes returned coherent results. The service was never restarted.
