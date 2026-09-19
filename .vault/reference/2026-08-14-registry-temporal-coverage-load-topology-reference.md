---
tags:
  - '#reference'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:6f9176129e3b9df2ccc4a0b8addbc42b03dfb23c99b645bfec79f55edd99f8cc'
related:
  - "[[2026-08-14-registry-temporal-coverage-research]]"
---

# `registry-temporal-coverage` reference: `registry load topology and authority-surface inventory`

Two consecutive design reviews of the temporal-coverage work each surfaced
registry modules the preceding analysis had not considered — first the typed
inspection projection and the snapshot review gates, then the coverage ledger in
`src/cadrumo/domain/calculations/registry/_coverage.py`. Neither omission was
careless reading; both were structural. This reference measures the surface that
made them likely, so that later work starts from an inventory rather than from
whichever modules a search happened to surface.

Every figure below was obtained mechanically at HEAD by enumeration over the
tree, not by reading and summarising. Commands were `rg` over `src/cadrumo` and
`dev`, `fd` over the package directory, and one interpreter call reading
`__all__` off the imported package. Semantic search was unavailable for this
session, which is itself relevant: the discovery sequence the project's rules
assume was not available, and keyword search alone did not surface
`_coverage.py` in either prior pass.

## Summary

### The package is past the size a single reading can cover

`src/cadrumo/domain/calculations/registry/` holds **155 Python modules totalling
54,999 lines**, and its package facade exports **545 symbols** in `__all__`.
There is no map, no layering document, and no grouping in the facade: the
export list is a flat alphabetical surface, so a consumer cannot tell the
authority boundary from a compiler internal by reading it.

That size is the mechanism behind both review misses. An analysis that reads the
modules a search returns will systematically miss a module whose name does not
contain the searched noun — `_coverage.py` contains the project's second
filing-eligibility predicate and its evidence-tier ledger, and matches neither
"temporal" nor "selector" nor "revision".

### There are three distinct tiers by which the registry can be loaded

**Tier one, the sanctioned authority.** `ValidatedRegistryAuthority.load(root, *,
source_root)` at `_authority.py:72`. **Twelve production files call it
independently**, each resolving its own `root` and `source_root`:
`adapters/inbound/declaracion/_parser.py:480`,
`adapters/outbound/aeat/sede/_declarations_observations.py:172`,
`application/diagnostics.py:722` and `:864`, `application/filing/runtime.py`,
`application/live/_filed_data_capture.py:1011`,
`application/registry/__init__.py:334` and `:346`,
`application/registry/_conformance.py`, `application/registry/_diff.py`,
`core/resources/_repos/modelos.py:48`, `domain/deadlines/_engine.py:159`, and
`domain/calculations/registry/_formula_runtime_ops.py:452` and `:479`. Three
further call sites live under `dev/`, and eleven test files call it directly.

**Tier two, the raw loader, published.** The facade re-exports the compiler
entry points at `__init__.py:406-410` and lists them in `__all__` at
`:1204-1208`: `load_registry_tree`, `load_modelo_directory`, `load_modelo_file`,
`load_modelo_path`, `load_modelo_source`. Counting the catalogue and
parameter-scoped loaders, **the facade publishes nine load-family entry points**
(the five above plus `load_catalogue_file`, `load_legal_parameters_only`,
`load_convenio_authority`, `load_m303_annual_orden_authority`).

This is the finding with governance weight. The `aeat-registry-authority-flow`
rule states that `_loader.py` is a compiler implementation detail and that
production paths must not call raw loaders and then independently validate or
select revisions. The facade nevertheless makes exactly that reachable from any
consumer in one import, and no gate detects it: the shipped import-hygiene scan
enforces that cross-package imports resolve to a facade, which a raw-loader
import already satisfies.

**Tier three, package-internal direct loader use.** Besides the facade and the
authority, two registry modules import `_loader` directly:
`_classification_coherence.py:87` and `_external_grounding.py:85`, both taking
`load_registry_tree`. These are intra-package and therefore legitimate under the
import rules, but they mean the raw tree is materialised by at least three
distinct in-package paths.

### At least seven typed shapes carry registry authority

`ValidatedRegistryAuthority` (`_authority.py:57`), `RegistrySnapshot`
(`_schema.py:1276`), `RegistryCatalogues` (`_schema.py:1268`),
`RegistryRevisionInspection` (`_static_inspection.py:39`),
`ModelLawCoverageLedger` (`_coverage.py:89`), `ConstructEvidenceLedger`
(`_coverage.py:218`), and `ModeloEntry` (`_support_matrix.py:202`). Raw
`ModeloDefinition` from the loader is an eighth reachable shape.

Their relationships are undocumented. Two of them independently answer whether a
revision may be treated as filing-grade: `_snapshot.py` does it through
`_check_snapshot_revision_review_status` and `_check_snapshot_legal_review_status`,
gated by `require_operator_review` which `_snapshot.py:403` hardwires to `True`;
and `_coverage.py:733` reimplements the same predicate as
`_revision_is_filing_eligible`. Both require an `OPERATOR_REVIEWED` revision and
`OPERATOR_REVIEWED` legal references. Neither delegates to the other, so the
filing-eligibility rule exists twice and can drift.

### Caching is distributed across at least five modules

`_loader.py` carries six cache declarations, `_loader_cache.py` two, and
`_authority.py` four, with `_compiled_cache.py`, `_validate_cache.py` and
`_loader_fingerprints.py` existing as further dedicated modules. The
authority-flow rule requires that any cache above the loader be invalidated by
the complete registry-tree fingerprint. Whether every one of these honours that
was not established here and is an open question for follow-on work.

### Two live defects in the coverage ledger

Both were found while establishing the above and are recorded here because they
bear directly on any coverage or horizon work.

`_representative_year` (`_coverage.py:748`) reduces a revision to one filing year,
returning the first enumerated year or, for an open selector, `year_from` — the
*earliest* claimed year. It feeds the snapshot the audit assesses at
`_coverage.py:341` and `:400`. The registry-wide coverage audit therefore
examines Modelo 341's `2000-y-siguientes` at year 2000 and never at 2001 through
2026. Measured against the open-selector population in
`2026-08-14-registry-temporal-coverage-research`, the audit built to report
evidence completeness cannot observe the great majority of the years the corpus
claims.

`ModelLawCoverageLedger.filing_gaps` (`_coverage.py:107-110`) returns `self.gaps`
only when `filing_eligible`, which requires `authority_scope == "filing"`, which
`build_model_law_coverage_ledger` sets only for a proof-carrying
`RegistrySnapshot`, which requires `_revision_is_filing_eligible`, which requires
an `OPERATOR_REVIEWED` revision. No revision in the corpus carries any review
stamp. **Every ledger is therefore `inspection_only` and `filing_gaps` returns
empty for the entire registry by construction** — a gate that reports clean
because nothing can reach it, which the `aeat-quality-gates` discipline names as
the unproven-gate failure mode.

### What this implies for method

The two review misses are explained by the measurements rather than by
inattention, and the same conditions apply to any future contributor: 155
modules and a flat 545-symbol facade, three load tiers, eight authority shapes,
one duplicated predicate, and no map. Work that proposes a new registry concept
should first establish whether the concept already exists under a name it did
not search for. The enumeration commands used here are cheap enough to rerun and
are the intended starting point.
