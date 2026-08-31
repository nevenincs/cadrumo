---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-27'
body_schema: 'body-v1'
body_hash: 'sha256:203860ad32cace6c5155eec41e643baf7e0e40fe7dc341de8150c43c85e2d4aa'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
  - "[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]"
  - "[[2026-08-14-registry-temporal-coverage-load-topology-reference]]"
---

# `registry-temporal-coverage` audit: `load closure census`

## Scope

The static import closure of the sanctioned registry load, diffed against the
traced execution sets, with every reachable-but-unexecuted module and every
non-executing registry module classified by owning entry point. Closes the
enumeration-completeness question the coverage decision record left open on its
import-graph axis; the repo-wide regulatory-literal axis is a separate census
and is not answered here.

Three instruments, all re-runnable through `dev/registry/load_census.py`:

The **static closure** is computed with grimp over the `cadrumo` root package,
excluding `TYPE_CHECKING`-guarded imports so the graph describes what a running
interpreter imports. It is taken from the two sanctioned load entry points --
`ValidatedRegistryAuthority.load` and the package facade every cross-package
consumer must route through -- and it holds **509 modules**, of which **148 are
registry modules**. That figure is confirmed against reality rather than
trusted: after a real load, `sys.modules` holds exactly those 148 registry
entries.

The **execution sets** are recorded with `sys.monitoring`, one callback on
`PY_START`, imports performed outside the traced window. A **warm** load
executes 38 modules, 22 of them in the registry package and 3 of its 42
validators. A **cold** load -- both cache directories redirected to empty
temporary directories, the machine's real caches untouched -- executes 186, 93
and 36. The warm set is a strict subset of the cold set. A third entry point was
traced because the load alone attributes too little: **inspection snapshot
construction** across all 73 bundled modelos executes 160 modules, 61 in the
registry and 27 validators. Every one of these figures reproduces the campaign's
prior measurement exactly.

The **reference map** is symbol-level, and it has to be. A registry module is
almost never imported directly from outside the package, because the
architecture rules route every cross-package import through the facade, so
module-level importer counts read zero for modules with real consumers. The map
reads both publication mechanisms -- the eager re-imports and the PEP 562
`_LAZY_EXPORTS` table -- and scans `src/cadrumo` and `dev` for consumers.

The **census universe** is the union of the static closure, what the closure
reaches through resolved dynamic imports, and every production module file in
the registry package: **523 modules**, test modules excluded. The third term is
the one that matters, because a registry module the load never imports is
exactly the population under investigation and is invisible from the closure
alone.

Derived quantities: **323** modules are reachable but execute nothing during a
cold load, and **61** registry modules execute in neither load regime. Every one
of the 523 carries exactly one classification, and a completeness gate refuses
the tree if any member does not.

## Findings

### load-closure-census | medium | no module in the census universe is dead, and the empty set is a measured result rather than an unexamined one

Every one of the 523 universe members is either live on the load path or
conditionally reachable from a named non-load trigger. The breakdown is 187 live
and 336 conditionally reachable; inside the registry package, 94 live and 60
conditionally reachable. The step this census executes carries a deletion
clause, and that clause has no members: nothing was deleted, because nothing
qualified.

The classification is recorded in `dev/registry/load_census_classification.py`
as reviewed rules, and `src/cadrumo/domain/calculations/registry/tests/test_load_census_classification.py`
refuses any universe member a rule does not cover. The gate was proven to bite:
an empty module dropped into the package produced one unclassified member and
exit code 1, and its removal restored exit code 0.

### load-closure-census | high | two modules read as dead on the import graph and both are alive, so an import-graph difference is not a deletion warrant

The first pass of the scanner reported `_constructs` and `_handoff_paths` as
having no importer anywhere but the facade. Both are consumed by registry gates
that reach them through the facade -- `from .. import resolve_revision_constructs`
and `from .. import audit_registry_handoff_paths` -- an edge module-level
importer counting cannot see, because the import lands on the package.

What would have been lost is two live modules and the two gates that depend on
them. The remediation is already in the instrument: the reference map is
symbol-level for this reason, and `unreferenced_modules` is documented as
returning candidates for review, never a verdict. This finding is recorded
rather than merely fixed because the same reasoning error is available to
anybody reading a dead-code report against this package.

### load-closure-census | high | none of the six validators the campaign carried as never executing is unable to execute, and four of them execute on a traced entry point

The campaign brief and the plan's deletion inventory both carry six validator
modules as executing in neither load regime, with the plan's `W01.P04.S21`
instructed to delete each one that is dead on the reasoning that a validator
which cannot execute on any machine is not worth keeping. The measurement does
not support that premise for any of the six.

Four -- `_validate_cross_domain_snapshot`, `_validate_reference_checker`,
`_validate_reference_sections` and `_validate_references` -- execute under
inspection snapshot construction, observed directly by tracing `build_snapshot`
across the bundled corpus. Their entry point is the snapshot-scoped reference
check at `src/cadrumo/domain/calculations/registry/_snapshot.py:328`, which the
load never reaches because the load builds no snapshot.

`_validate_cache` publishes the three cache objects that
`src/cadrumo/domain/calculations/registry/_validate.py:38` binds at import. It
defines no callable of its own, so it cannot appear in any execution set however
live it is; its absence measures the instrument, not the module.

`_validate_cross_revision_advisory` is imported by
`src/cadrumo/domain/calculations/registry/_validate_cross_revision.py:30`, which
executes on every cold load. Its advisory builders fire only for a corpus
carrying a contiguity divergence, which the bundled corpus does not present.

What is lost if this stands uncorrected is six live modules, four of them
validators guarding snapshot reference integrity. The remediation is to re-scope
that row: classify by reachable caller as the row already says, and record that
the deletion clause has no members rather than finding some.

### load-closure-census | high | the snapshot reference check cannot be reached at filing grade, because the operator-review gate refuses first for every revision in the corpus

`check_all_id_references` runs at
`src/cadrumo/domain/calculations/registry/_snapshot.py:328`, after the review
gate at `:303`. `build_validated_snapshot` -- the path
`ValidatedRegistryAuthority.snapshot` takes -- passes
`require_operator_review=True` at `:403`, and no revision in the corpus carries
a review stamp, so every filing-grade snapshot refuses before the check. A trace
of `authority.snapshot` across twelve modelos and three period tokens produced
zero snapshots and a `RegistryValidationError` on every attempt.

Only the inspection-grade `build_snapshot` at `:181`, which defaults
`require_operator_review` to `False`, reaches the check; that path produced 53
snapshots across the 73 bundled modelos.

This is the same shape the load-topology reference already recorded for the
coverage ledger's `filing_gaps`: a check that reports clean because nothing can
reach it. It is not the same defect -- the referential check does run on the
inspection path -- but a reader who assumes filing-grade snapshots exercise it
today is wrong, and any bite proof for a filing-grade snapshot rule must
establish reachability before it can claim to have proven anything.

### load-closure-census | medium | build_snapshot is published on the facade with no production caller outside the package

`build_snapshot` is re-exported at
`src/cadrumo/domain/calculations/registry/__init__.py:612` and listed in
`__all__` at `:1122`. Its only consumers are the package's own tests and the
census trace. The three production files that mention it by name --
`src/cadrumo/adapters/outbound/aeat/sede/_declarations.py:44`,
`src/cadrumo/adapters/outbound/aeat/sede/_declarations_fetch.py:29` and
`src/cadrumo/entrypoints/cli/_config/_google.py:45` -- do so in comments about
cross-domain check installation, not in code.

This is the same class of surface as the raw loader family the coverage decision
demotes from the facade: a published entry point that bypasses the validated
authority. It differs in that no production consumer has taken it, so the
demotion is cheap now and gets more expensive with every future consumer.

### load-closure-census | medium | the load path carries one first-party import edge no AST import graph can represent, and it crosses a domain boundary

`src/cadrumo/domain/calculations/registry/_snapshot.py:177` imports the renta
routing-integrity modules by name, iterating a module-level tuple, for their
registration side effect. The edge is deliberate and the import-linter
configuration documents it as the sanctioned Protocol-injection direction in
which the registry never names renta. It is nonetheless invisible to grimp, and
eight modules reachable only through it were absent from the static closure:
the renta package, its errors, substrate, first-slice routing and routing
integrity, retenciones routing integrity, ledger expenses and maritime
exemption.

The census recovers them by reading the tuple, which is the one indirection
worth following because it is how every production dynamic-import site in this
tree is written. They are classified and counted. The finding is recorded
because any future closure computation over this package that does not read that
tuple will under-report by these eight modules and will not say so.

### load-closure-census | medium | five production dynamic-import sites remain unresolved and are reported unclassified

The scanner resolves a literal argument and a loop over a module-level tuple of
module paths. Five production sites match neither shape and are reported as
unresolved rather than assumed harmless:
`src/cadrumo/domain/calculations/registry/_static_inspection.py:88` builds its
target with an f-string over `__package__`;
`src/cadrumo/entrypoints/cli/__init__.py:1168` and
`src/cadrumo/entrypoints/cli/_app_contract.py:82` take a loop variable through
an intervening function boundary; `dev/identity/hex64_acceptance_probe.py:146`
and `dev/quality/shims.py:28` are dev tooling.

There is no sanctioned inventory of first-party function-local import edges in
this repository to check these against. They are therefore reported on the graph
difference alone and left **unclassified**; nothing here should be read as an
allowlist having cleared them.

### load-closure-census | medium | the warm regime is a caching state, not a population, and the first load after any tree change is partially cold

Three consecutive warm traces immediately after peer edits landed in the package
produced 44, then 22, then 22 executing registry modules, with 4, then 3, then 3
validators. The first load re-certified the moved tree fingerprint and was
therefore partially cold; the regime settled from the second load on.

This matters for every warm-regime bite proof the plan requires. A proof run
once, immediately after touching the tree, may be measuring a re-certification
pass and not the warm regime at all. The reliable procedure is to load once to
settle, then measure.

### load-closure-census | medium | the coverage ledger is imported by every load and executed by none, which is how its single-representative-year defect stayed unobserved

`src/cadrumo/domain/calculations/registry/_coverage.py` is in the static closure
of every load, so its declarations run on every import, and it appears in no
execution set for any of the three traced entry points. Its only named trigger
is registry conformance reporting through
`src/cadrumo/application/registry/_conformance.py`.

A module in that position looks present to any reader of the import graph and
runs for nobody in ordinary use. The two live defects the load-topology
reference recorded in it were both invisible on that basis. The same position is
occupied by `_static_inspection` and `_classification_coherence`, which share
the trigger.

### load-closure-census | low | the applicability rule literals sit behind an application-layer trigger, not the load

The six applicability modules -- `_applicability` and its labels, modelo-202,
payer-facts and routes siblings, plus `_censo_modelos` -- execute on no traced
entry point. Their trigger is modelo obligation resolution from
`application.modelo`, `application.overview` and the modelo discovery CLI.

This locates the 28 Python-resident rule literals the coverage decision moves
into the authoring tree: they are not on the load path, so a registry-load bite
proof cannot cover the migration, and the compiled-equality proof the migration
row already requires is the right instrument rather than a load-time check.

## Recommendations

Every finding above is dispositioned; none is left unclassified.

Re-scope `W01.P04.S21` before it executes. The row's premise -- a validator that
cannot execute on any machine -- is false for all six of its named modules, and
four of them execute under inspection snapshot construction. The row should
record the reachable caller for each, note that its deletion clause has no
members, and close on the classification rather than on a deletion. This census
supplies the callers.

Enroll the unreachable filing-grade reference check with the snapshot-boundary
enforcement row. Any rule landing at the authority and snapshot resolution
boundary must state which of the two snapshot paths it lands on, and a bite
proof taken on the inspection path must not be presented as covering the filing
path, which no revision in the corpus can currently reach.

Fold the `build_snapshot` facade publication into the facade-closure row that
already demotes the raw loader family. It is the same defect class, it currently
has no production consumer, and demoting it now costs one line.

Carry the five unresolved dynamic-import sites forward to the repo-wide drift
census as a named input, so the two censuses share one answer about what the
static graph cannot see. They are deferred here, not dismissed: this census
reports them and claims no clearance.

Adopt the load-then-measure procedure for every warm-regime bite proof the plan
requires. A first load after a tree change is not a warm load, and a proof taken
on it measures the wrong regime.

Treat the imported-but-never-executed position as a review signal in its own
right for the coverage-ledger reconciliation rows. Three modules occupy it, and
the two defects already found in that position were both found by reading rather
than by any gate.

### Correction, 2026-08-27: the sixth validator's classification was wrong in substance

The finding above records `validate_cross_revision_advisory` as alive because
`_validate_cross_revision` imports it on every cold load. Re-read at HEAD, that
is wrong in substance rather than merely stale, and in two ways.

The import it cited was a **re-export, not a call site**. At the cited revision
the two names appear in that file only at its import block and its `__all__`;
no production call site has ever existed, in any commit. The census conflated
import with execution, and conflated this module with
`_validate_cross_revision_contiguity`, which is the module that genuinely fires
during validation and is reached from `_validate_cross_revision_evolution`.
The same mis-attribution was copied into the classification rule in
`dev/registry/analysis/load_census_classification.py`, whose stated reason
described contiguity while its members named the advisory; that rule has been
re-pointed at the module its prose actually describes.

The re-export was removed deliberately by the export-hygiene sweep, and the
module's own stated expiry condition -- that it hold the line until a
corpus-wide continuity completeness gate existed -- has since been met by the
shipped continuidad completeness ratchet. No accepted ADR mandated the
advisory; two accepted records disfavour its premise, both holding that
repeated identifiers do not authorize continuity, which is exactly what its
non-overlapping grouping inferred.

`W01.P04.S21`'s deletion clause therefore acquired **exactly one member**, and
the module has been retired. The other five members stand as classified. One
capability is genuinely not carried forward: the advisory produced a finer
(modelo, revision-pair, field) inventory with an evolution-covered split that
the ratchet's per-modelo counting does not reproduce. Nothing consumed it. If
the grounding campaign wants it as a work queue it belongs in `dev/` behind a
real caller, over the surviving divergence iterator -- not as an uncalled
module under `src/`.
