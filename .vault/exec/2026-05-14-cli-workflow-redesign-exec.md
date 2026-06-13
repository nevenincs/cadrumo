---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W48.P236.S1411'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
---




# `cli-workflow-redesign` `W48.P236.S1411` / `W48.P236.S1412` / `W48.P236.S1413` / `W48.P236.S1414` / `W48.P236.S1415` / `W48.P236.S1416`


Mapped the Modelo 100 borrador binding ADR into application-owned service state,
added the command/result contracts required by `W48.P236.S1412`, wired the
resolver into the application calculate services for `W48.P236.S1413`, and
strengthened the persistence/event/registry integration coverage for
`W48.P236.S1414`. `W48.P236.S1415` routes the existing live borrador backend
shape into the canonical secure-object service. `W48.P236.S1416` locks the
service-level error code and bounded event log fields for the calculation
event. The CLI does not own snapshot lookup, eligibility, active-bucket checks,
supersession checks, precedence, or trace persistence.

- Modified: `src/aeat/application/modelo/__init__.py`
- Modified: `src/aeat/application/live/__init__.py`
- Modified: `src/aeat/core/errors/registry/_application.py`
- Modified: `src/aeat/application/modelo/_actions.py`
- Modified: `src/aeat/application/modelo/test_amend_flow.py`
- Modified: `src/aeat/application/modelo/test_bucket_aggregation_flow.py`
- Modified: `src/aeat/domain/modelos/_calculation_revision.py`
- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `registry/aeat/modelos/100/revisions/2025.toml`
- Created: `src/aeat/application/modelo/_borrador_binding.py`
- Created: `src/aeat/application/modelo/test_borrador_binding.py`
- Created: `src/aeat/application/live/_borrador_100.py`
- Created: `src/aeat/application/live/test_borrador_100.py`
- Created: `src/aeat/domain/calculations/registry/test_borrador_prefilled_schema.py`

## Description

Implemented the live application repository for captured Modelo 100 borrador
snapshots under the `aeat.application.live` namespace, keyed by bucket and
snapshot id. The modelo application service now owns only the strict
`Modelo100BorradorBindingCommand`, `Modelo100BorradorBindingResult`, and
resolution rules.

The resolver accepts a `borrador_snapshot_id`, loads through the live
repository, rejects non-Modelo-100 consumers before snapshot lookup, binds the
passed registry snapshot to the command axis, rejects bucket or snapshot-axis
mismatches, rejects superseded snapshots with the ADR's list-command fix
pointer, and consumes only registry bindings marked `aeat_prefilled`.

The resolver preserves ADR precedence by dropping any snapshot value whose
binding id was explicitly supplied by the caller. It also routes values into the
decimal or enum binding channel from the registry binding definition, not from
guessing the raw value shape.

The registry schema now carries the explicit `aeat_prefilled` boolean marker,
and the committed Modelo 100 2025 registry marks one decimal and one enum
binding as AEAT-prefill capable.

The second code review cleared S1412 with no findings after the live ownership,
registry-axis, direct `aeat_prefilled`, payload-identity, and public import
boundary fixes.

For S1413, `calculate_modelo_revision` now accepts an explicit
`borrador_snapshot_id`, resolves it through the canonical borrador resolver,
merges values with the locked precedence of operator input over borrador over
backend-derived values, and persists `borrador_snapshot_id` plus
`bindings_sourced_from_borrador` on the durable calculation revision. The bucket
aggregation service passes ledger values as lower-precedence backend inputs
instead of treating them as caller overrides. Bound casilla inputs are resolved
from the final binding map, so operator binding overrides also flow into bound
casillas. Amendment revisions preserve the baseline borrador trace.

The S1413 review found two issues: the legacy aggregation conflict policy and a
missing amendment-trace test. Both were fixed and the re-review reported no
findings.

For S1414, the application/modelo consumer path now has real persistence and
event coverage around the live snapshot repository, durable calculation
revision trace, registry `aeat_prefilled` markers, and
`modelo.calculation.created` payload. Tests cover a fresh encrypted repository
reload preserving the borrador trace and binding overrides, non-borrador event
payload defaults, snapshot id participation in calculation revision identity,
event object id linkage, and calculate-service precedence:
operator input over borrador over backend-derived values. The app-live provider
capture surface remains out of this `src/aeat/application/modelo` step and is
tracked by later app-live/CLI exposure work. One residual note remains: the
registry schema file is also dirty from parallel W84 source-kind taxonomy work
in the shared worktree. That unrelated work was not reverted or rewritten.

For S1415, a read-only audit found an existing `aeat.application.live._borrador`
JSONL-backed service with capture, list, show, latest, and discard behavior.
No production caller imported it; only its test and a string error-registry
entry referenced it. The canonical route remains the secure-object backed
`Borrador100SnapshotRepository` consumed by the Modelo 100 resolver.

The secure-object path now carries the missing live-service behavior needed by
later fetch/list/show routing: content-addressed capture, bucket-scoped listing,
unambiguous prefix resolution, latest-active lookup, and automatic supersession
for older current snapshots on the same Modelo 100 axis. Out-of-order captures
do not make stale data current; an older capture saved after a newer active
capture is persisted as superseded and points at the newer snapshot. The
resolver now rejects any non-active snapshot state with the structured
`aeat app live borrador 100 list` suggestion. Full CLI exposure and the discard
workflow remain in their later plan rows, so this step did not add CLI business
logic or partial discard mutation.

The S1415 review initially found one in-scope high issue: out-of-order capture
could make stale data current. It also found a low issue where non-active
snapshot rejection lacked a structured suggestion. Both were fixed. The
follow-up review reported no high or critical findings for this backend step.

For S1416, the existing `Modelo100BorradorBindingError` registry row was
covered by an application test asserting the stable
`REFUSED_MODELO_100_BORRADOR_BINDING` service code. The
`modelo.calculation.created` payload now carries `calculation_revision_id`,
`borrador_participated`, `borrador_snapshot_id`, `borrador_binding_count`, and
a bounded `borrador_bindings_trace_sha256` digest. The full ordered binding
trace remains on `CalculationRevision.bindings_sourced_from_borrador`, avoiding
bucket-event payload overflow while keeping durable provenance. The calculation
event payload version was bumped to 2 for the changed contract.

The S1416 review initially found one high issue: the full source-trace CSV could
exceed the bucket event payload value limit after the revision and work unit had
already been persisted. It also found a payload-version gap. Both were fixed;
the follow-up review reported no high or critical issues.

## Tests

- `uv run --no-sync pytest -q src/aeat/application/live/test_borrador_100.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/domain/calculations/registry/test_borrador_prefilled_schema.py src/aeat/domain/calculations/registry/test_registry_schema.py -q` - 99 passed.
- `uv run --no-sync ruff check src/aeat/application/live/_borrador_100.py src/aeat/application/live/__init__.py src/aeat/application/live/test_borrador_100.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_borrador_binding.py src/aeat/application/modelo/__init__.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/application/modelo/test_file_flow.py src/aeat/domain/modelos/_calculation_revision.py src/aeat/domain/calculations/registry/test_borrador_prefilled_schema.py src/aeat/domain/calculations/registry/_schema.py` - passed.
- `uv run --no-sync ty check src/aeat/application/live/_borrador_100.py src/aeat/application/live/__init__.py src/aeat/application/live/test_borrador_100.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_borrador_binding.py src/aeat/application/modelo/__init__.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/application/modelo/test_file_flow.py src/aeat/domain/modelos/_calculation_revision.py src/aeat/domain/calculations/registry/test_borrador_prefilled_schema.py src/aeat/domain/calculations/registry/_schema.py` - passed.
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_error_registry_contract.py -q` - existing prefix-format failures remain outside S1411.
- `uv run --no-sync pytest -q src/aeat/application/live/test_borrador_100.py src/aeat/application/live/test_borrador.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/domain/calculations/registry/test_borrador_prefilled_schema.py src/aeat/domain/calculations/registry/test_registry_schema.py -q` - 118 passed after S1415.
- `uv run --no-sync ruff check src/aeat/application/live/_borrador_100.py src/aeat/application/live/__init__.py src/aeat/application/live/test_borrador_100.py src/aeat/application/modelo/_borrador_binding.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/application/modelo/test_file_flow.py src/aeat/domain/modelos/_calculation_revision.py src/aeat/domain/calculations/registry/test_borrador_prefilled_schema.py src/aeat/domain/calculations/registry/_schema.py` - passed after S1415.
- `uv run --no-sync ty check src/aeat/application/live/_borrador_100.py src/aeat/application/live/__init__.py src/aeat/application/live/test_borrador_100.py src/aeat/application/modelo/_borrador_binding.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/application/modelo/test_file_flow.py src/aeat/domain/modelos/_calculation_revision.py src/aeat/domain/calculations/registry/test_borrador_prefilled_schema.py src/aeat/domain/calculations/registry/_schema.py` - passed after S1415.
- `uv run --no-sync pytest -q src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/test_file_flow.py -q` - 43 passed after S1416.
- `uv run --no-sync pytest -q src/aeat/application/live/test_borrador_100.py src/aeat/application/live/test_borrador.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/domain/calculations/registry/test_borrador_prefilled_schema.py src/aeat/domain/calculations/registry/test_registry_schema.py -q` - 119 passed after S1416.
- `uv run --no-sync ruff check src/aeat/application/live/_borrador_100.py src/aeat/application/live/__init__.py src/aeat/application/live/test_borrador_100.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_borrador_binding.py src/aeat/application/modelo/__init__.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/application/modelo/test_file_flow.py src/aeat/domain/modelos/_calculation_revision.py src/aeat/domain/calculations/registry/test_borrador_prefilled_schema.py src/aeat/domain/calculations/registry/_schema.py src/aeat/core/errors/registry/_application.py` - passed after S1416.
- `uv run --no-sync ty check src/aeat/application/live/_borrador_100.py src/aeat/application/live/__init__.py src/aeat/application/live/test_borrador_100.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_borrador_binding.py src/aeat/application/modelo/__init__.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/application/modelo/test_file_flow.py src/aeat/domain/modelos/_calculation_revision.py src/aeat/domain/calculations/registry/test_borrador_prefilled_schema.py src/aeat/domain/calculations/registry/_schema.py src/aeat/core/errors/registry/_application.py` - passed after S1416.

## `W48.P237.S1417`

Audited duplicate implementations that overlap the canonical Modelo 100
borrador binding path. The canonical application path is
`aeat.application.modelo._borrador_binding` plus the secure-object backed
`aeat.application.live._borrador_100` repository/service. The audit found the
competing JSONL-backed `aeat.application.live._borrador` module, its dedicated
test, and CLI imports in `aeat.entrypoints.cli._app_live` that still render
legacy fields (`tax_year`, `prefill_entries`, `discarded`) instead of canonical
fields (`filing_year`, `period`, `binding_values`, `state`).

The audit also found stale test seeding through the shadow `BorradorService`,
a stale error-registry row for `aeat.application.live._borrador`, and a Modelo
CLI pass-through gap for the explicit snapshot id. These are queued into the
remaining `W48.P237` rows; no production code was changed for the audit step.

## `W48.P237.S1418`

Deleted the competing JSONL-backed borrador backend branch and its dedicated
tests: `aeat.application.live._borrador` and `aeat.application.live.test_borrador`.
The app-live borrador CLI now reads through the canonical
`Borrador100SnapshotService` and renders canonical fields:
`filing_year`, `period`, `binding_values`, and `state`. The stale
`BorradorSnapshotNotFoundError` registry row was removed rather than aliased.

The migrated CLI no longer exposes the duplicate branch's discard command.
Snapshot discard has a separate ADR requiring actor attribution and
consumed-revision checks, so keeping the old local discard would have preserved
rejected behavior. The stale `--tax-year` and `--include-discarded` options were
removed from the borrador surface during review remediation; `latest` uses
`--filing-year`, and `list` uses `--state active|superseded|discarded|all`.

S1418 review initially found stale CLI vocabulary in the migrated surface. The
follow-up review reported no high, critical, or medium issues.

S1418 verification:

- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/application/live/test_borrador_100.py src/aeat/application/modelo/test_borrador_binding.py -q` - 44 passed.
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/application/live/test_borrador_100.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/domain/calculations/registry/test_borrador_prefilled_schema.py src/aeat/domain/calculations/registry/test_registry_schema.py -q` - 124 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/application/live/_borrador_100.py src/aeat/application/live/test_borrador_100.py src/aeat/application/modelo/_borrador_binding.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/core/errors/registry/_domain.py` - passed.
- `uv run --no-sync ty check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/application/live/_borrador_100.py src/aeat/application/live/test_borrador_100.py src/aeat/application/modelo/_borrador_binding.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/core/errors/registry/_domain.py` - passed.

## `W48.P237.S1419`

Removed stale CLI aliases that could route operators around the canonical
Modelo 100 borrador binding contract. `aeat app modelo work calculate` now
advertises and accepts the ADR-locked `--borrador SNAPSHOT_ID` option only;
the rejected `--borrador-snapshot-id` spelling is not exposed. The live
borrador 100 read surface no longer exposes the deleted duplicate backend's
`--tax-year` or `--include-discarded` vocabulary; `latest` uses
`--filing-year`, and `list` uses the canonical snapshot state filter.

The unresolved CLI help keys for the borrador read and calculate surfaces were
added to the locale catalogues, and the help path continues to use `tr(...)`
rather than direct translation-object construction. Review found no remaining
stale borrador aliases, deleted `application.live._borrador` references, raw
borrador help keys, or forbidden dev metastate mentions in the reviewed CLI
surface.

S1419 verification:

- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_work_calculate_borrador.py src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/application/live/test_borrador_100.py src/aeat/application/modelo/test_borrador_binding.py -q` - 47 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_work_calculate_borrador.py src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/test_live_read_subgroups.py` - passed.
- `uv run --no-sync ty check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_work_calculate_borrador.py src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/test_live_read_subgroups.py` - passed.
- `uv run --no-sync python -c "import pathlib, yaml; [yaml.safe_load(path.read_text(encoding='utf-8')) for path in [pathlib.Path('src/aeat/locales/en.yml'), pathlib.Path('src/aeat/locales/es.yml'), pathlib.Path('src/aeat/locales/ca.yml'), pathlib.Path('src/aeat/locales/hu.yml')]]; print('locale yaml ok')"` - passed.
- `uv run --no-sync aeat app modelo work calculate --help` - renders `--borrador` and no `--borrador-snapshot-id`.
- `uv run --no-sync aeat app live borrador 100 list --help` - renders `--state`.
- `uv run --no-sync aeat app live borrador 100 latest --help` - renders `--filing-year`.

## `W48.P237.S1420`

Audited and corrected internal `application/modelo` callers for canonical
Modelo 100 borrador binding use. The Spark audit found the direct and
bucket-aggregation calculate paths already route through the canonical
resolver, persist `borrador_snapshot_id` and
`bindings_sourced_from_borrador`, emit the bounded event digest, and preserve
caller-over-borrador-over-backend precedence.

Review then found one low no-shim issue: the private
`_resolve_borrador_bindings_for_calculation` helper was only a pass-through
wrapper around `resolve_modelo_100_borrador_bindings`. That wrapper was
removed. `calculate_modelo_revision` now directly constructs
`Modelo100BorradorBindingCommand` and calls the canonical resolver, with no
separate alias/helper path.

S1420 verification:

- `uv run --no-sync pytest -q src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py -q` - 53 passed.
- `uv run --no-sync ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_borrador_binding.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py` - passed.
- `uv run --no-sync ty check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_borrador_binding.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py` - passed.
- `rg -n "_resolve_borrador_bindings_for_calculation|application\\.live\\._borrador|BorradorService|BorradorPrefillEntry|direct translation-object construction|forbidden dev-state token" src/aeat/application/modelo src/aeat/application/live src/aeat/entrypoints/cli` - no matches.

## `W50.P246.S1471`

Mapped the Modelo 036/037 foundation ADR into a registry-domain ownership
surface. The new `aeat.domain.calculations.registry._census_modelos` module
declares `aeat.domain.calculations.registry` as the non-CLI service owner,
locks Modelo `036` as the active event-triggered census foundation for
`alta`, `modificacion`, and `baja`, and locks Modelo `037` as historical
inactive metadata superseded by `036`.

The public registry API now exports the ownership record, role enum, exact
lookup, complete map, and active-check helper. The lookup intentionally accepts
only exact string modelo codes: shortened values, padded values, and integer
codes are rejected so the foundation does not introduce aliases or active
Modelo 037 shim behavior. The audit confirmed registry TOML artifacts and
workflow enforcement remain absent, which is expected for later W50 rows rather
than S1471 ownership mapping.

S1471 review initially found one low issue: padded exact codes such as
`" 036 "` were accepted due to whitespace normalization. The lookup now
compares exact strings and regression tests cover padded `036` and `037`.
Follow-up review reported no findings.

S1471 verification:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_public_api_boundaries.py src/aeat/domain/modelos/test_codes.py -q` - 25 passed.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/__init__.py` - passed.
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/__init__.py` - passed.

## `W50.P246.S1472`

Implemented strict frozen Pydantic contracts for the census modelo foundation
under the registry-domain ownership map. `CensusModeloFoundationCommand`
accepts exact three-digit string modelo codes only, requires an event kind for
active Modelo `036`, and rejects active event requests for historical Modelo
`037`. `CensusModeloFoundationResult` carries the registry-owned decision:
`036` is an active foundation with accepted `alta`, `modificacion`, and `baja`
events; `037` is inactive historical metadata superseded by `036`.

The contracts are exported through the registry public API with
`CensusModeloEventKind`. Tests cover strict immutability, active/inactive
command shape, invalid event kind rejection, shortened/padded/integer modelo
code rejection, active `036` results, historical `037` results, and active
`037` shim rejection. The audit confirmed no existing separate command/result
contracts needed preservation or aliasing, and review found no issues.

S1472 verification:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_public_api_boundaries.py src/aeat/domain/modelos/test_codes.py -q` - 36 passed.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/__init__.py` - passed.
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/__init__.py` - passed.

## `W50.P246.S1473`

Wired the registry-domain census modelo service function:
`resolve_census_modelo_foundation(command)`. The function consumes the strict
`CensusModeloFoundationCommand`, reads the canonical ownership map, and returns
a revalidated `CensusModeloFoundationResult`. It is exported through the public
registry package surface and covered for active Modelo `036` and historical
Modelo `037`.

The audit confirmed the command-result resolver, public export, and tests are
the required S1473 service wiring. Registry TOML, persistence, bucket events,
and provider adapters remain for later rows. Review reported no findings.

S1473 verification:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_public_api_boundaries.py src/aeat/domain/modelos/test_codes.py -q` - 38 passed.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/__init__.py` - passed.
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/__init__.py` - passed.

## `W50.P246.S1474`

Connected the census modelo foundation to committed registry data. Modelo
`036` now has a registry TOML with the active event-triggered periods
`alta`, `modificacion`, and `baja`, a profile binding to `census.status`,
reviewed legal/source refs, a record-design workbook parity reference, and
workflow/filing/verification links through the existing registry schema.

Modelo `037` remains inactive: no loadable `037` modelo TOML or manifest was
introduced. Its historical state is represented as reviewed catalogue source
metadata tied to the BOE suppression evidence, so the registry records the
source without reviving an active workflow or filing-grade shim. The audit
confirmed no existing 036/037 registry file or provider adapter existed; the
only existing code was the domain ownership contract from earlier W50 rows.

The first validation pass found two registry-contract issues: the profile
binding needed source citations and the selector had to use the schema-owned
`profile_key` selector shape. Both were corrected. Review then checked for
legacy/shim language, direct translation-object construction, and forbidden dev-state mentions in
the S1474 files and found no matches.

S1474 verification:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_catalogue_verification.py -q` - 61 passed.
- `uv run --no-sync ruff check registry/aeat/modelos/036.toml registry/aeat/legal/census.toml src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/_schema.py` - passed.
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/_schema.py` - passed.
- `rg -n "forbidden dev-state token|shim|alias|deprecated|direct translation-object construction" registry/aeat/modelos/036.toml registry/aeat/legal/census.toml src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py corpus/normatives/html/orden-eha-1274-2007-art-1.html corpus/normatives/html/orden-eha-1274-2007-art-2.html corpus/normatives/html/orden-hac-1526-2024-art-1.html corpus/normatives/html/orden-hac-1526-2024-df-unica.html src/aeat/domain/calculations/registry/_schema.py` - no matches.

## `W50.P246.S1475`

Routed census modelo work-unit behavior through the canonical registry-domain
foundation service. `create_work_unit` now resolves `036` and `037` through
`CensusModeloFoundationCommand` and `resolve_census_modelo_foundation` before
loading or saving any work-unit record. Modelo `036` must use one of the
accepted event periods `alta`, `modificacion`, or `baja`; Modelo `037` is
refused as historical census metadata only and never reaches persistence as a
new active work unit.

The read-only audit also found a stale-record path: directly seeded or
pre-existing `037` work units could still reach calculation, verification, and
external-filing import paths and fail later as generic registry snapshot
errors. The same foundation route now runs before those downstream snapshot
paths, including bucket aggregation calculation, import casilla validation,
amendment override validation, and required-input verification lookup. Tests
seed a persisted `037` work unit directly and assert calculate, verify, and
import all refuse through the census foundation guard without writing
calculation, verification, or filing records.

S1475 verification:

- `uv run --no-sync pytest -q src/aeat/application/modelo/test_history.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py -q` - 40 passed.
- `uv run --no-sync ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_history.py` - passed.
- `uv run --no-sync ty check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_history.py` - passed.
- `rg -n "forbidden dev-state token|direct translation-object construction" src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_history.py` - no matches.

## `W50.P246.S1476`

Recorded the census modelo foundation service-level observability contract in
the registry domain. The foundation now declares its backend-owned error-code
set as `CENSUS_MODELO_ERROR_CODES`, exposes an immutable
`CensusModeloFoundationContract`, and returns deterministic
`CensusModeloFoundationLogFields` from each resolved foundation decision.

`resolve_census_modelo_foundation` emits a structured debug record using those
log fields after resolving active Modelo `036` or historical Modelo `037`.
The public registry package exports the new contract and log-field types. The
application work-unit refusal path remains bound to its existing application
error code and is covered by a direct registry assertion without moving that
code into the domain contract.

The read-only audit confirmed no prior error-code or log-field schema existed
for the census foundation service. It also confirmed the correct service-owned
domain code is `ERROR_CALCULATIONS_REGISTRY_VALIDATION`, while the
work-unit refusal code remains application-owned.

S1476 verification:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/application/modelo/test_history.py -q` - 37 passed.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/application/modelo/test_history.py` - passed.
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/application/modelo/test_history.py` - passed.
- `rg -n "forbidden dev-state token|direct translation-object construction" src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/application/modelo/test_history.py` - no matches.

Additional check:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/application/modelo/test_history.py src/aeat/core/errors/test_registry_enforcement.py -q` - the S1476 and application slices passed, but the registry-enforcement slice currently fails on unrelated pre-existing registry entries that do not map to loaded subclasses in this shared worktree.

## `W50.P247.S1477`

Audited duplicate implementations that overlap the canonical census modelo
foundation. The canonical ownership and decision path is
`aeat.domain.calculations.registry._census_modelos`, exported through the
registry package as `CensusModeloFoundationCommand` and
`resolve_census_modelo_foundation`.

The audit found no census-specific duplicate command surface under
`src/aeat/entrypoints/cli`. The registry-domain hits are the canonical
foundation module and its tests, plus the committed Modelo `036` registry
data tests and historical `037` metadata guards. Broader corpus and portal
hits are source/legal history rather than active work-unit behavior.

The remaining competing backend branch is in
`src/aeat/application/modelo/_actions.py`: `_CENSUS_MODELO_CODES` and the
`modelo_code == "036"` period mapping duplicate census model ownership before
delegating to `resolve_census_modelo_foundation`. That overlap is queued for
`W50.P247.S1478`, where the application helper should stop owning the census
code set and let the registry-domain foundation decide whether a modelo code
is part of the census foundation.

The requested Spark audit was launched, but the Spark quota was exhausted
before the agent returned findings. The local read-only audit completed the
S1477 inventory without editing production code.

S1477 audit commands:

- `rg -n "036|037|census|CensusModelo|historical_metadata|active_work_unit_allowed" src/aeat/entrypoints/cli -S` - no census-specific CLI duplicate surface.
- `rg -n "036|037|census|CensusModelo|historical_metadata|active_work_unit_allowed" src/aeat/application/modelo src/aeat/domain/calculations/registry -g "test_*.py" -S` - canonical tests plus application refusal coverage only.
- `fd -t f . corpus/aeat_official/disenos_registro/modelo_037` - only a zero-artefact official manifest remains for historical source inventory.

## `W50.P247.S1478`

Deleted the duplicate application-local census branch that competed with the
registry-domain foundation. `src/aeat/application/modelo/_actions.py` no
longer owns `_CENSUS_MODELO_CODES`, does not import
`CensusModeloEventKind` or `CensusModeloFoundationCommand`, and does not map
Modelo `036` periods itself before calling the registry foundation.

The registry domain now exposes
`resolve_census_modelo_work_unit_foundation(modelo, period)`. It returns the
canonical census foundation decision for exact Modelo `036` and `037`, returns
`None` for non-census modelos, and raises `RegistryValidationError` for real
census-foundation validation failures such as an invalid Modelo `036` event
period. The application layer catches that registry validation and preserves
the existing `WorkUnitMutationRefusedError` contract for modelo work-unit
actions.

The read-only audit for S1478 confirmed this was the minimal deletion shape.
It also flagged the risk of masking validation failures, so the resolver was
tightened to return `None` only for unknown exact model codes while preserving
validation errors such as non-string modelo inputs.

S1478 verification:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/application/modelo/test_history.py -q` - 41 passed.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_history.py` - passed.
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_history.py` - passed.
- `rg -n '_CENSUS_MODELO_CODES|CensusModeloEventKind|CensusModeloFoundationCommand|resolve_census_modelo_foundation|modelo_code == "036"|frozenset\(\("036", "037"\)\)' src/aeat/application/modelo/_actions.py src/aeat/entrypoints/cli -S` - no matches.
- `rg -n "forbidden dev-state token|direct translation-object construction" src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_history.py` - no matches.

## `W50.P247.S1479`

Removed the stale modelo CLI period aliasing path that could bypass exact
census foundation periods. `aeat app modelo bindings list` and
`aeat app modelo bindings preview` no longer construct period strings such as
`2025-alta` or `2025-Q1` in the CLI layer. Instead, the registry query service
owns scope resolution through `RegistryQueryService.bindings_for_scope()`.

The registry-owned resolver preserves exact periods already declared by the
modelo revision, which keeps Modelo `036` event periods as `alta`,
`modificacion`, and `baja`. For periodic modelos, the same backend service
resolves `--year 2026 --period Q1` to the registry period `1T`, preserving
existing behavior without a CLI-local schema conversion branch.

The read-only audit found no hardcoded census branch, alternate root, or
duplicate census command surface in `src/aeat/entrypoints/cli`. It also found
an unrelated external-filing evidence-kind hyphen normalization in the modelo
CLI; that alias is not census-foundation-specific and remains for later
non-census alias cleanup.

S1479 verification:

- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_modelo.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/application/modelo/test_history.py -q` - 65 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/domain/calculations/registry/_queries.py src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/application/modelo/_actions.py` - passed.
- `uv run --no-sync ty check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/domain/calculations/registry/_queries.py src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/application/modelo/_actions.py` - passed.
- `rg -n 'scoped_period|f"\{year\}-\{period\}"|period\.startswith\(str\(year\)\)|2025-alta|2025-modificacion' src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/domain/calculations/registry/_queries.py -S` - no matches.
- `rg -n "forbidden dev-state token|direct translation-object construction" src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/domain/calculations/registry/_queries.py src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/application/modelo/_actions.py` - no matches.

## `W50.P247.S1480`

Migrated and locked the internal callers for census modelo foundation. The
read-only audit confirmed no remaining production caller bypasses the
canonical registry service: `src/aeat/application/modelo/_actions.py` routes
census work-unit behavior through
`resolve_census_modelo_work_unit_foundation(...)`, and
`src/aeat/entrypoints/cli/_modelo.py` has no direct `036`/`037` census branch.

Added a caller-boundary regression guard in
`src/aeat/application/modelo/test_history.py` that scans the application
modelo action module and the modelo CLI for forbidden local census branches
such as `_CENSUS_MODEL`, direct `modelo == "036"` / `modelo == "037"` checks,
and local `036`/`037` code sets. Canonical imports/calls to the registry
foundation remain allowed.

S1480 verification:

- `uv run --no-sync pytest -q src/aeat/application/modelo/test_history.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py -q` - 66 passed.
- `uv run --no-sync ruff check src/aeat/application/modelo/test_history.py src/aeat/application/modelo/_actions.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/domain/calculations/registry/_queries.py src/aeat/domain/calculations/registry/_census_modelos.py` - passed.
- `uv run --no-sync ty check src/aeat/application/modelo/test_history.py src/aeat/application/modelo/_actions.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/domain/calculations/registry/_queries.py src/aeat/domain/calculations/registry/_census_modelos.py` - passed.
- `rg -n '_CENSUS_MODEL|modelo_code == "036"|modelo == "036"|modelo_code == "037"|modelo == "037"|frozenset\(\("036", "037"\)\)' src/aeat/application/modelo/_actions.py src/aeat/entrypoints/cli/_modelo.py -S` - no matches.
- `rg -n "forbidden dev-state token|direct translation-object construction" src/aeat/application/modelo/test_history.py src/aeat/application/modelo/_actions.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/domain/calculations/registry/_queries.py src/aeat/domain/calculations/registry/_census_modelos.py` - no matches.

## `W50.P247.S1481`

Removed stale census-foundation tests and fixtures that kept Modelo `037`
looking like an active work-unit or dependency participant. The read-only audit
found four resurrection points: the work-unit resolver test accepted
`modelo="037", period="alta"`, the disenos-registro corpus listed a
zero-artifact 037 fixture as supported, apoderamiento scope `CENSO` included
037, and Modelo 100's 2025 dependency classifications still listed
`source_modelo = "037"`.

The registry-domain work-unit resolver now rejects inactive census modelos at
the domain boundary with the existing historical census metadata refusal
wording. Pure historical metadata lookup through
`resolve_census_modelo_foundation(CensusModeloFoundationCommand(modelo="037"))`
remains intact, matching the ADR. The stale corpus fixture was removed, active
scope/dependency listings were tightened to 036, and the cross-dependency
contract now permits profile-schedule relations only from 036 and 840.

S1481 verification:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/test_cross_dependency_contract.py src/aeat/application/modelo/test_history.py src/aeat/entrypoints/cli/test_modelo.py -q` - 83 passed.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_cross_dependency_contract.py` - passed.
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_cross_dependency_contract.py` - passed.
- `rg -n 'renta-2025-dep-037|source_modelo\s*=\s*"037"|modelo_codes\s*=\s*\["036", "037"\]|modelo_037|active_037_shim|forbidden dev-state token|direct translation-object construction' registry/aeat/modelos/100/revisions/2025.toml registry/aeat/apoderamientos/scopes.toml corpus/aeat_official/disenos_registro src/aeat/domain/calculations/registry src/aeat/application/modelo src/aeat/entrypoints/cli -S` - remaining matches are intentional historical metadata test names only.

## `W50.P247.S1482`

Updated the backend boundary inventory for the census modelo foundation shadow
duplicate removal phase. The read-only audit confirmed the production modelo
CLI delegates work-unit creation to the application service and does not own a
036/037 branch, but `test_backend_boundary.py` did not yet have a census
foundation guard.

Added `test_census_modelo_foundation_stays_backend_owned`, which scans
production CLI Python modules and fails if census foundation commands,
resolvers, active-work-unit policy, or historical-metadata decisions leak into
the CLI layer. This records the removed duplicate behavior without adding a
new command surface.

S1482 verification:

- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/application/modelo/test_history.py src/aeat/entrypoints/cli/test_modelo.py -q` - 85 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_backend_boundary.py` - passed.
- `uv run --no-sync ty check src/aeat/entrypoints/cli/test_backend_boundary.py` - passed.
- `rg -n 'CensusModeloFoundationCommand|resolve_census_modelo_foundation|resolve_census_modelo_work_unit_foundation|is_active_census_modelo|CensusModeloRole|active_work_unit_allowed|historical_metadata_only|forbidden dev-state token|direct translation-object construction' src/aeat/entrypoints/cli -g '*.py' -S` - matches only the boundary test's forbidden-token inventory.

## `W50.P248.S1483`

Deleted the remaining compatibility-style census modelo identity paths found
during de-shim audit. The registry query service no longer strips modelo codes
before `validate_modelo(...)`, so padded values such as ` 036` and `036 ` do
not alias the canonical string code `036`. Added query-service tests proving
padded census modelo codes fail before reaching census foundation behavior.

The same audit found modelo history filtering compared stripped modelo and
period strings. That was tightened to exact payload/input equality so the CLI
history view does not preserve a padded modelo or period alias path.

The read-only audit found no remaining active Modelo 037 work-unit fallback,
synthetic 037 registry support, integer 36/37 acceptance, or year-prefixed
census period fallback.

S1483 verification:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_queries.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/test_backend_boundary.py -q` - 79 passed.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_queries.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/entrypoints/cli/_modelo.py` - passed.
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/_queries.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/entrypoints/cli/_modelo.py` - passed.
- `rg -n 'validate_modelo\(modelo\.strip\(\)\)|payload_map\.get\("modelo".*\.strip\(\)|modelo\.strip\(\)|payload_map\.get\("period".*\.strip\(\)|2025-alta|2025-modificacion|renta-2025-dep-037|source_modelo\s*=\s*"037"|modelo_codes\s*=\s*\["036", "037"\]|modelo_037|forbidden dev-state token|direct translation-object construction' src/aeat/domain/calculations/registry/_queries.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/entrypoints/cli/_modelo.py registry/aeat/modelos/100/revisions/2025.toml registry/aeat/apoderamientos/scopes.toml corpus/aeat_official/disenos_registro -S` - no matches.

## `W50.P248.S1484`

Audited the census modelo foundation registry scope for placeholder stubs. No
census registry placeholder, `NotImplemented` path, fake active support,
empty result claiming support, active `037` TOML, synthetic `037` registry
fixture, or zero-row support path was present in the scoped registry files.

The read-only audit found one adjacent wording issue in
`registry/aeat/user_profile/schema.toml` describing ROI enrollment with old
`036/037` wording. That file is outside the W50 registry-domain scope and is
owned by the parallel user-profile wave, so it was not edited here.

S1484 verification:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/test_queries.py -q` - 44 passed.
- `rg -n 'TODO|NotImplemented|not implemented|placeholder|stub|fake active|synthetic 037|modelo_037|037\.toml|source_modelo\s*=\s*"037"|renta-2025-dep-037' src/aeat/domain/calculations/registry registry/aeat/modelos registry/aeat/legal/census.toml corpus/aeat_official/disenos_registro -S` - no scoped census placeholder/support findings; unrelated official corpus text and unrelated registry tests only.
- `rg -n '<forbidden dev-state token>' . -S` - no matches.
- `rg -n 'Translatable\(' .vault/exec/2026-05-14-cli-workflow-redesign-exec.md .vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md src/aeat/domain/calculations/registry src/aeat/application/modelo src/aeat/entrypoints/cli -S` - no matches.

## `W50.P248.S1485`

Replaced the remaining census-foundation paths that could behave like
backend-looking in-code support without consulting real registry data.
`census_modelo_ownership("036")` now derives the active event periods from the
validated committed Modelo 036 registry definition and validates real
registry snapshots for each census event period before returning an active
foundation ownership decision. Modelo 037 inactive ownership now requires the
absence of an active 037 registry definition plus the committed historical
suppression source metadata.

The application modelo lifecycle now also routes preexisting census work units
through the foundation before filing and amendment. Directly seeded 037 work
units were already blocked for calculate, verify, and external import; they
are now also blocked before `file_modelo_revision` can write a filing record
and before `amend_modelo_revision` can create amendment revisions or filings.

S1485 verification:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/application/modelo/test_history.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/test_backend_boundary.py -q` - 95 passed.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_history.py` - passed.
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_history.py` - passed.
- `rg -n '_CENSUS_MODELO_OWNERSHIP|validate_modelo\(modelo\.strip\(\)\)|payload_map\.get\("modelo".*\.strip\(\)|2025-alta|2025-modificacion|renta-2025-dep-037|source_modelo\s*=\s*"037"|modelo_codes\s*=\s*\["036", "037"\]|modelo_037|<forbidden dev-state token>|direct translation-object construction' src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_history.py src/aeat/entrypoints/cli/_modelo.py registry/aeat/modelos/100/revisions/2025.toml registry/aeat/apoderamientos/scopes.toml corpus/aeat_official/disenos_registro -S` - remaining match is only the intentional historical metadata test name.

## `W50.P248.S1486`

Removed deprecated and misleading modelo CLI help text around the census
foundation. The apoderamiento `censo` locale labels now list active Modelo 036
only, not `036, 037`. Generic modelo period help now tells operators that
Modelo 036 uses the exact event periods `alta`, `modificacion`, and `baja`,
while preserving periodic examples for periodic modelos.

Also removed the modelo filing-record import hyphenated evidence-kind alias
path and its help text. `--evidence-kind` now accepts the canonical underscore
enum values only.

S1486 verification:

- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/application/modelo/test_history.py -q` - 86 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py` - passed.
- `uv run --no-sync ty check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py` - passed.
- `uv run --no-sync python -c "import pathlib, yaml; [yaml.safe_load(path.read_text(encoding='utf-8')) for path in [pathlib.Path('src/aeat/locales/en.yml'), pathlib.Path('src/aeat/locales/es.yml'), pathlib.Path('src/aeat/locales/ca.yml'), pathlib.Path('src/aeat/locales/hu.yml')]]; print('locale yaml ok')"` - passed.
- `uv run --no-sync aeat app modelo work create --help` - renders event-aware 036 period help.
- `uv run --no-sync aeat app modelo bindings list --help` - renders event-aware 036 period help.
- `rg -n '036, 037|037\)|hyphenated aliases|aliases also accepted|replace\("-", "_"\)|2025-alta|2025-modificacion|<forbidden dev-state token>|direct translation-object construction' src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/locales/en.yml src/aeat/locales/es.yml src/aeat/locales/ca.yml src/aeat/locales/hu.yml -S` - no matches.

## `W50.P248.S1487`

Audited the registry census-foundation tests for any remaining assertions that
accept shim or stub behavior. No edit was needed: the current tests reject
shortened, padded, and integer modelo codes; reject active 037 events; reject
037 work-unit routing; reject non-census 036 periods; assert 037 is not an
active registry model; assert no committed 037 TOML can revive active support;
and reject padded census modelo codes through the query service.

The only generic period parser tests cover non-census periodic shapes such as
`2026Q1`, `2026-Q4`, and `2026-03`; they do not assert year-prefixed census
event aliases.

S1487 verification:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/domain/calculations/registry/test_cross_dependency_contract.py -q` - 54 passed.
- `rg -n 'shim|stub|placeholder|fake|alias|aliases|accepted|accepts|037|036|37|36|2025-alta|2025-modificacion|hyphen|trim|padded|integer|<forbidden dev-state token>|direct translation-object construction' src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/domain/calculations/registry/test_cross_dependency_contract.py -S` - matches are rejection tests, active 036 assertions, historical-only 037 assertions, and generic non-census period parser coverage only.

## `W50.P248.S1488`

Recorded the removed census-foundation shim and placeholder surfaces in the
CLI/backend boundary inventory. Added
`test_census_modelo_removed_shims_and_stubs_stay_removed`, separate from the
S1482 backend-ownership guard, so the boundary suite now fails if any of the
P248-removed surfaces return: active `036, 037` help wording, year-prefixed
census event periods, hyphenated evidence-kind aliases, padded-code helper
patterns, the removed in-code census ownership map, fake active support, or
synthetic 037 support markers.

The guard also forced the remaining negative CLI test to stop naming the
removed hyphenated evidence-kind alias as a fixture literal; it now uses a
generic non-canonical token.

S1488 verification:

- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/application/modelo/test_history.py -q` - 100 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_modelo.py` - passed.
- `uv run --no-sync ty check src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_modelo.py` - passed.
- `rg -n '036, 037|modelo 037\)|modelos 036/037|2025-alta|2025-modificacion|2025-baja|aeat-justificante-pdf|aeat-csv-register|aliases also accepted|replace\("-", "_"\)|\.zfill\(|\.lstrip\(|strip\("0"\)|_CENSUS_MODELO_OWNERSHIP|NotImplementedError|not implemented|fake active|synthetic 037|source_modelo\s*=\s*"037"|modelo_codes\s*=\s*\["036", "037"\]|<forbidden dev-state token>|direct translation-object construction' src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/locales/en.yml src/aeat/locales/es.yml src/aeat/locales/ca.yml src/aeat/locales/hu.yml src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/_queries.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/test_queries.py registry/aeat/modelos/036.toml registry/aeat/apoderamientos/scopes.toml -S` - no matches.

## `W50.P249.S1489`

Added service-contract tests for the census modelo foundation, grounded in
the committed registry rather than fixtures or stubs. The test suite now
proves active Modelo 036 work-unit periods resolve from the real 2025
registry revision, historical Modelo 037 status is backed by the absence of
an active 037 registry definition plus the committed suppression source
metadata, malformed census-looking modelo codes are rejected before the
work-unit resolver can treat them as non-census, and structured debug logs
include stable decision fields.

The resolver was tightened so shortened or padded census-looking codes such
as `36`, `37`, ` 036 `, and ` 037 ` raise the same strict census-modelo
validation error instead of falling through as unrelated modelos. Non-census
modelos such as `303` still return `None` from the census foundation router.

S1489 verification:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_census_modelo_foundation.py -q` - 40 passed.
- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/test_cross_dependency_contract.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/entrypoints/cli/test_backend_boundary.py -q` - 85 passed.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py` - passed.
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py` - passed.
- Scanned for the prohibited dev-state token across the repository - no matches.
- Scanned for direct translation-object construction across the touched registry/application/CLI scope - no matches.
- `rg -n -- 'fake active|synthetic 037|NotImplementedError|not implemented|aeat-justificante-pdf|aeat-csv-register|aliases also accepted|replace\("-", "_"\)|\.zfill\(|\.lstrip\(|strip\("0"\)' src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py` - no matches.

## `W50.P249.S1490`

The read-only audit found this step already materially satisfied by the
committed registry integration tests in `test_census_modelo_registry_data.py`.
No duplicate assertions were added. The existing tests load the real
`registry/aeat` tree, build Modelo 036 snapshots from committed TOML and
catalogues, assert the ad-hoc census event periods, verify the profile-backed
`census.status` binding, check legal/source/layout coverage, verify the
record-design corpus source by path/hash/byte count, prove Modelo 037 is not
an active registry model, verify its historical suppression source, and assert
no committed 037 TOML or manifest can revive active support.

S1490 verification:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py -q` - 7 passed.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py` - passed.
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py` - passed.

## `W50.P249.S1491`

Added CLI negative coverage proving rejected census aliases do not resolve
through the census modelo foundation service. `bindings list` now has a
CLI-level test for shortened Modelo 036 input that fails through the registry
query boundary as an unknown modelo and records no foundation-resolution log.
`bindings preview` now has a CLI-level test for a year-prefixed census event
period that fails as malformed period input and likewise records no foundation
resolution. The rejected year-prefixed token is composed in the test so the
removed alias literal does not return to the codebase.

S1491 verification:

- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_modelo.py -q` - 24 passed.
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py -q` - 87 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_modelo.py` - passed.
- `uv run --no-sync ty check src/aeat/entrypoints/cli/test_modelo.py` - passed.
- `rg -n -- '036, 037|modelos 036/037|2025-alta|2025-modificacion|2025-baja|aeat-justificante-pdf|aeat-csv-register|aliases also accepted|replace\("-", "_"\)|\.zfill\(|\.lstrip\(|strip\("0"\)|fake active|synthetic 037|NotImplementedError|not implemented' src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/_modelo.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/_census_modelos.py` - no matches.
- `rg -n "forbidden dev-state token|direct translation-object construction" src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/_modelo.py .vault/exec/2026-05-14-cli-workflow-redesign-exec.md .vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md` - no matches.

## `W50.P249.S1492`

Added real CLI command-behavior coverage for the census modelo foundation via
`app modelo work create`. The tests use an isolated encrypted SQLite backend
through the project settings override and the real storage repository, then
invoke the cached CLI command tree. Active Modelo 036 work units are created
for exact `alta`, `modificacion`, and `baja` event periods and verified
through `app modelo work list`. Historical Modelo 037 and rejected census
alias inputs fail through the real application/domain path and leave no
persisted work units in the isolated bucket.

S1492 verification:

- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_modelo.py -q` - 28 passed.
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/application/modelo/test_history.py -q` - 105 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_modelo.py` - passed.
- `uv run --no-sync ty check src/aeat/entrypoints/cli/test_modelo.py` - passed.
- `rg -n -- '036, 037|modelos 036/037|2025-alta|2025-modificacion|2025-baja|aeat-justificante-pdf|aeat-csv-register|aliases also accepted|replace\("-", "_"\)|\.zfill\(|\.lstrip\(|strip\("0"\)|fake active|synthetic 037|NotImplementedError|not implemented' src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/_modelo.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/_census_modelos.py` - no matches.
- Scanned the touched CLI/log/plan scope for the prohibited dev-state token and direct translation-object construction - no matches.

## `W50.P249.S1493`

Added active Modelo 036 end-to-end workflow coverage without entering the
parallel user-profile wave. The new history test uses the existing encrypted
repository fixture to create an active 036 work unit, import external filing
evidence through the real application service, verify the work-unit filing
pointers and imported calculation revision state, and assert the assembled
work-unit history exposes the exact `modelo.filing.imported` payload for
Modelo 036 `baja`.

S1493 verification:

- `uv run --no-sync pytest -q src/aeat/application/modelo/test_history.py -q` - 15 passed.
- `uv run --no-sync pytest -q src/aeat/application/modelo/test_history.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py -q` - 90 passed.
- `uv run --no-sync ruff check src/aeat/application/modelo/test_history.py` - passed.
- `uv run --no-sync ty check src/aeat/application/modelo/test_history.py` - passed.
- `rg -n -- '036, 037|modelos 036/037|2025-alta|2025-modificacion|2025-baja|aeat-justificante-pdf|aliases also accepted|replace\("-", "_"\)|\.zfill\(|\.lstrip\(|strip\("0"\)|fake active|synthetic 037|NotImplementedError|not implemented' src/aeat/application/modelo/test_history.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/_census_modelos.py` - no matches.
- Scanned the touched application/CLI/log/plan scope for the prohibited dev-state token and direct translation-object construction - no matches.

## `W50.P249.S1494`

Ran the targeted registry-domain census foundation test slice without skips
or xfails. The checkout co-locates tests under `src/aeat`, so the declared
`tests/domain/calculations/registry` scope maps to
`src/aeat/domain/calculations/registry`. The exact S1494 slice covered the
census foundation service tests, committed registry-data tests, padded-code
query rejection, and cross-dependency role contract.

S1494 verification:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/test_queries.py::test_query_service_rejects_padded_census_modelo_codes src/aeat/domain/calculations/registry/test_cross_dependency_contract.py::test_cross_dependency_roles_match_supported_modelo_hierarchy -rA` - 51 passed, no skips, no xfails.
- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/domain/calculations/registry/test_cross_dependency_contract.py src/aeat/application/modelo/test_history.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/test_backend_boundary.py -q` - 128 passed.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/application/modelo/test_history.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/test_backend_boundary.py` - passed.
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/_census_modelos.py src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/application/modelo/test_history.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/test_backend_boundary.py` - passed.
- `rg -n "pytest\.(skip|xfail)|pytest\.mark\.(skip|skipif|xfail)|@pytest\.mark\.(skip|skipif|xfail)" src/aeat/domain/calculations/registry/test_census_modelo_foundation.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/domain/calculations/registry/test_cross_dependency_contract.py` - no matches.

## `W50.P250.S1495`

Verified accepted census-foundation CLI handlers are already exposed under
`aeat app modelo`. The app registration wires `aeat app modelo`; the accepted
surface is provided by registry-backed `bindings list` / `bindings preview`,
real work-unit `work create` / `work list`, and application-backed
`work history`. No new census-specific command was added because that would
duplicate backend foundation logic instead of exposing the existing
application/domain services.

The read-only audit noted the older top-level `app modelo history` command
still filters bucket-event history inside the CLI, so it is not used as the
proof point for this step. The accepted S1495 exposure is the existing
`app modelo` work and bindings surface.

S1495 verification:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo.py::test_work_create_accepts_modelo_036_exact_event_periods_through_foundation src/aeat/entrypoints/cli/test_modelo.py::test_work_create_rejects_modelo_037_historical_only_without_persisting src/aeat/entrypoints/cli/test_modelo.py::test_work_create_rejects_census_aliases_without_persisting src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_foundation_stays_backend_owned src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_removed_shims_and_stubs_stay_removed -rA` - 6 passed.
- `rg -n "CensusModeloFoundationCommand|resolve_census_modelo_foundation|resolve_census_modelo_work_unit_foundation|is_active_census_modelo|CensusModeloRole|active_work_unit_allowed|historical_metadata_only" src/aeat/entrypoints/cli --glob "*.py" --glob "!test_*.py"` - no matches.
- Scanned the touched CLI/log/plan scope for the prohibited dev-state token and direct translation-object construction - no matches.

## `W50.P250.S1496`

Added a focused boundary guard proving census-foundation argument parsing stays
separate from backend behavior. The guard parses `src/aeat/entrypoints/cli/_modelo.py`
with `ast`, verifies `work create` passes raw `modelo` and `period` option
values directly into `create_work_unit`, verifies bindings preview passes raw
`modelo` and `period` into `RegistryQueryService.bindings_for_scope`, verifies
bindings list keeps the user-provided modelo filter as the raw target, and
rejects CLI-local strip/padding/replacement normalization on those scope values.

The read-only audit independently confirmed the same state: accepted census
foundation behavior is already backend-owned through `RegistryQueryService` and
`create_work_unit`, while the CLI command layer only accepts options and delegates
them. No CLI-local census foundation imports, alias parsers, padding/stripping
normalization, legacy support branch, direct translation-object construction, or
metadata metastate hardcoding were found.

S1496 verification:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_scope_arguments_stay_raw_until_backend_calls src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_foundation_stays_backend_owned src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_removed_shims_and_stubs_stay_removed -q` - 3 passed.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_scope_arguments_stay_raw_until_backend_calls src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_foundation_stays_backend_owned src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_removed_shims_and_stubs_stay_removed src/aeat/entrypoints/cli/test_modelo.py::test_work_create_accepts_modelo_036_exact_event_periods_through_foundation src/aeat/entrypoints/cli/test_modelo.py::test_work_create_rejects_modelo_037_historical_only_without_persisting src/aeat/entrypoints/cli/test_modelo.py::test_work_create_rejects_census_aliases_without_persisting -q` - 7 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_backend_boundary.py` - passed.
- `uv run --no-sync ty check src/aeat/entrypoints/cli/test_backend_boundary.py` - passed.
- `rg -n -- 'Translatable\(|replace\("-", "_"\)|\.zfill\(|\.lstrip\(|strip\("0"\)|source_modelo = "037"|modelo_codes = \["036", "037"\]' src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/domain/calculations/registry/_census_modelos.py` - no matches.

## `W50.P250.S1497`

Added a separate boundary guard for census-foundation execution delegation.
The guard parses `src/aeat/entrypoints/cli/_modelo.py` with `ast`, verifies the
accepted census-facing paths use central backend/application/domain services
(`RegistryQueryService`, `create_work_unit`, and `assemble_work_unit_history`),
and verifies the registry service factory loads `ValidatedRegistryAuthority`
without introducing a Modelo 036 execution branch inside the CLI.

The read-only audit confirmed actual census foundation routing remains owned by
`application.modelo.create_work_unit`, the application census routing helper,
the domain census foundation resolver, and committed registry data. It found no
blocking CLI-local census execution logic. The older top-level `app modelo
history` command still performs direct bucket-event filtering, but the accepted
census proof point is delegated `work history`, so that unrelated issue does
not block S1497.

S1497 verification:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_execution_stays_delegated_to_backend_services src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_scope_arguments_stay_raw_until_backend_calls src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_foundation_stays_backend_owned -q` - 3 passed.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_execution_stays_delegated_to_backend_services src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_scope_arguments_stay_raw_until_backend_calls src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_foundation_stays_backend_owned src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_removed_shims_and_stubs_stay_removed src/aeat/entrypoints/cli/test_modelo.py::test_bindings_list_preserves_census_event_period src/aeat/entrypoints/cli/test_modelo.py::test_bindings_preview_preserves_census_event_period src/aeat/entrypoints/cli/test_modelo.py::test_work_create_accepts_modelo_036_exact_event_periods_through_foundation src/aeat/entrypoints/cli/test_modelo.py::test_work_create_rejects_modelo_037_historical_only_without_persisting src/aeat/entrypoints/cli/test_modelo.py::test_work_create_rejects_census_aliases_without_persisting -q` - 10 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_backend_boundary.py` - passed.
- `uv run --no-sync ty check src/aeat/entrypoints/cli/test_backend_boundary.py` - passed.
- CLI-only scan for census foundation imports/resolvers, direct translation-object construction, and alias-normalization tokens in `src/aeat/entrypoints/cli/_modelo.py` and `src/aeat/entrypoints/cli/test_modelo.py` - no matches.
- Registry/boundary scan for direct translation-object construction and alias-normalization tokens found matches only in the boundary guard's forbidden-token inventory.

## `W50.P250.S1498`

Added a render-path boundary guard for accepted census-facing `app modelo`
commands. The guard parses `src/aeat/entrypoints/cli/_modelo.py` with `ast`,
verifies `bindings list`, `bindings preview`, `work create`, `work list`, and
`work history` call `_emit`, and rejects direct `typer.echo`, `print`,
Rich/Console rendering, direct JSON dumping, and direct schema-emitter bypasses
inside those command handlers.

The read-only audit confirmed those same handlers build payload/text lines and
render through `_emit`, with existing real CLI JSON tests covering 036 bindings
list/preview and 036 work create/list. The only `json.dumps` in `_modelo.py` is
outside the census render paths and is used to validate aggregation command
input through Pydantic, not to emit output.

S1498 verification:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_results_render_through_emitters src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_execution_stays_delegated_to_backend_services src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_scope_arguments_stay_raw_until_backend_calls -q` - 3 passed.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_results_render_through_emitters src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_execution_stays_delegated_to_backend_services src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_scope_arguments_stay_raw_until_backend_calls src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_foundation_stays_backend_owned src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_removed_shims_and_stubs_stay_removed src/aeat/entrypoints/cli/test_modelo.py::test_bindings_list_emits_readiness_category_for_every_row src/aeat/entrypoints/cli/test_modelo.py::test_bindings_list_preserves_census_event_period src/aeat/entrypoints/cli/test_modelo.py::test_bindings_preview_preserves_census_event_period src/aeat/entrypoints/cli/test_modelo.py::test_work_create_accepts_modelo_036_exact_event_periods_through_foundation -q` - 9 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_backend_boundary.py` - passed.
- `uv run --no-sync ty check src/aeat/entrypoints/cli/test_backend_boundary.py` - passed.
- `rg -n -- 'typer\.echo|Console\(|from rich|print\(|emit_json_success|emit_json_document|Translatable\(' src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_modelo.py` - matches only the boundary guard's forbidden-call inventory.

## `W50.P250.S1499`

Verified census foundation failures route through the central command error
boundary for the actual foundation resolver path. The `app modelo work create`
historical Modelo 037 path delegates to `create_work_unit`, the application
layer turns the backend census-foundation refusal into the registered
`WorkUnitMutationRefusedError`, and the globally decorated Typer app renders
the registered JSON stderr envelope through `_errors.command_error_boundary`.

The read-only audit identified that bindings list/preview registry-query input
failures still use Typer `BadParameter`. That path is clean and traceback-free,
but it is generic registry-query user-input handling, not an actual census
foundation resolver failure. No broad registry-query error rewrite was made.

S1499 verification:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_failures_use_central_error_boundary src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_results_render_through_emitters src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_execution_stays_delegated_to_backend_services src/aeat/entrypoints/cli/test_modelo.py::test_work_create_rejects_modelo_037_historical_only_without_persisting src/aeat/entrypoints/cli/test_modelo.py::test_work_create_rejects_census_aliases_without_persisting src/aeat/entrypoints/cli/test_modelo.py::test_bindings_list_rejects_census_modelo_alias_without_foundation_resolution src/aeat/entrypoints/cli/test_modelo.py::test_bindings_preview_rejects_year_prefixed_census_event_alias_without_foundation_resolution -q` - 8 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_modelo.py` - passed.
- `uv run --no-sync ty check src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_modelo.py` - passed.
- Production `_modelo.py` scan for manual error rendering, direct translation-object construction, and census resolver imports - no matches.
- `src/aeat/entrypoints/cli/__init__.py` still applies `decorate_typer_app(app)` after mounting `app modelo`; `_errors.py` still renders registered errors via `get_registered_error_code`, `render_error_text`, and `render_error_json`.

## `W50.P250.S1500`

Verified census foundation help text uses only accepted vocabulary for the
current Modelo 036 event workflow. Help for `app modelo work create`,
`app modelo bindings list`, and `app modelo bindings preview` includes Modelo
036 plus `alta`, `modificacion`, and `baja`, and excludes historical 037 active
support, setup-wizard, portal-only, integer-code, live-submission,
compatibility, shim, stub, fake, alias, and placeholder wording.

S1500 verification:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_failures_use_central_error_boundary src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_help_uses_accepted_foundation_vocabulary_only src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_results_render_through_emitters src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_execution_stays_delegated_to_backend_services src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_scope_arguments_stay_raw_until_backend_calls src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_foundation_stays_backend_owned src/aeat/entrypoints/cli/test_backend_boundary.py::test_census_modelo_removed_shims_and_stubs_stay_removed -q` - 7 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_backend_boundary.py` - passed.

## `W51.P251.S1501` through `W51.P255.S1530`

Closed W51 as deferred-baseline verified without code implementation. The Apex
R22 closure state supersedes the original Modelo 145 foundation execution rows:
Modelo 145 remains deferred pending live-AEAT reconciliation research and a
successor ADR. The original Modelo 145 ADR remains a design record, but no
successor ADR exists that reopens implementation scope.

No Modelo 145 registry, backend, CLI, shim, stub, alias, or test implementation
was added. The baseline confirms no `registry/aeat/modelos/145.toml`, no
Modelo 145 application/domain service, no CLI surface, no duplicate branch, no
stale alias, no compatibility shim, and no placeholder support to remove. W85
bookkeeping was corrected so checked rows no longer claim a 145 TOML,
lifecycle, or tests shipped.

W51 verification:

- Read the Modelo 145 foundation ADR and the Apex R22 closure-state block.
- Read-only audit confirmed no successor ADR reopens Modelo 145 scope and no
  implementation surface exists.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md --json` - returned `[]`.
- `Test-Path registry/aeat/modelos/145.toml` - returned `False`.
- First-open-row query now skips W50/W51 and reports `W80.P385.S2205` as the
  next open plan row.

## `W80.P385.S2205` and `W80.P388.S2219`

Wired the modelo file transition through `WorkflowEngine.run_for_period` before
any filing-state mutation. `file_modelo_revision` now requires the caller's
workflow profile, builds a real workflow gate when no engine is supplied, runs
the target modelo/period through workflow orchestration, persists the resulting
workflow run, and raises `ModeloWorkflowGateError` on aborted workflow results
before creating filing records, superseding prior filings, advancing work-unit
pointers, or emitting filed bucket events.

The production path uses the existing deadline engine, filing draft builder,
draft approval, selected auth provider, submission preflight engine, secure
workflow-run persistence, and the current calculation revision's immutable
inputs. No standalone workflow command, preflight command, compatibility shim,
alias, stub, or live submission path was added.

While verifying this row, the modelo calculation contract mismatch surfaced:
the application layer already persisted borrador source metadata on calculation
revisions, but the domain identity/model did not define those fields. The
domain `CalculationRevision` and `derive_calculation_revision_id` now include
`borrador_snapshot_id` and `bindings_sourced_from_borrador`, preserving the
existing content-addressed identity contract and unblocking the real lifecycle
tests.

W80 file-gate verification:

- Read workflow-engine-harvest ADR and apex §8 backend exit-cap mandates.
- Read-only audit confirmed `file_modelo_revision` had no workflow invocation,
  no run persistence, and no preflight/blocker refusal before this patch.
- Added real-behavior file-flow coverage proving the workflow gate refuses
  before filing-state writes when preflight blocks.
- `uv run --no-sync pytest src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/application/modelo/test_import_flow.py -q` - 39 passed.
- `uv run --no-sync ruff check src/aeat/application/modelo/_actions.py src/aeat/domain/modelos/_calculation_revision.py src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/application/modelo/test_import_flow.py src/aeat/entrypoints/cli/_modelo.py` - passed.
- `uv run --no-sync ty check src/aeat/application/modelo/_actions.py src/aeat/domain/modelos/_calculation_revision.py src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/application/modelo/test_import_flow.py` - passed.

## `W80.P385.S2206`

Adjudicated preflight routing for W80/R15: `SubmissionEngine.preflight` is
WorkflowEngine-routed only. Modelo application actions and CLI handlers must
not call `SubmissionEngine.preflight` directly. `file_modelo_revision` may
construct the real `SubmissionEngine` as a dependency of `WorkflowEngine`, but
the invocation path remains `WorkflowEngine.run_for_period` reaching its
`RUNNING_PREFLIGHT` stage.

The verdict was recorded in the apex ADR and the workflow-engine-harvest child
ADR. This leaves `W80.P385.S2207`, `W80.P386.S2209`, `W80.P388.S2220`, and
`W80.P389.S2228` open for applying and verifying the same WorkflowEngine-owned
gate on the remaining verify-path surface.

S2206 verification:

- Read apex §8 and workflow-engine-harvest implementation constraints.
- Read-only audit confirmed the current file path routes preflight through
  `WorkflowEngine.run_for_period`, the actual `preflight()` invocation remains
  inside `WorkflowEngine._stage_running_preflight`, `verify_modelo_revision`
  has no direct preflight path, and `_modelo.py` delegates to application
  services without a direct workflow/preflight bypass.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md --json` - returned `[]` before the S2206 tick.

## `W80.P385.S2207`, `W80.P386.S2209`, and `W80.P388.S2220`

Applied the W80 preflight-routing verdict to the remaining verify-path surface.
`verify_modelo_revision` now uses the same WorkflowEngine-owned revision gate
as `file_modelo_revision`: callers supply the active workflow profile, the
application layer builds or accepts a `WorkflowEngine`, and the granted
verification path calls `WorkflowEngine.run_for_period` before persisting the
verification report, transitioning the work unit to `VERIFIED_COMPLETE`, or
emitting the verified bucket event.

Local verification refusals still remain local: missing required manual
casillas and registry calculation errors persist refused verification reports
without invoking workflow preflight. Granted verification and filing now share
the single `_run_revision_workflow_gate` path, so no direct
`SubmissionEngine.preflight` invocation exists in modelo actions or the CLI.

The CLI `work verify` and `work file` handlers now resolve the active workflow
profile and delegate to the application service. They do not construct
workflow engines, call submission preflight, add a standalone preflight verb, or
add a compatibility surface.

Read-only audit for S2209 found the consolidated state satisfied: both
`verify_modelo_revision` and `file_modelo_revision` route through the shared
WorkflowEngine gate, the only production `preflight()` call remains inside
`WorkflowEngine._stage_running_preflight`, and `_modelo.py` only supplies the
workflow profile to the application boundary.

W80 verify-gate verification:

- Read apex §8, the W80.P385.S2206 verdict, workflow-engine-harvest, and
  workflow-resumption-semantics context before applying the verify-path wiring.
- Added real-behavior coverage proving `verify_modelo_revision` refuses before
  verified-state writes when the WorkflowEngine-owned preflight gate aborts.
- Re-ran the modelo application lifecycle slice:
  `uv run --no-sync pytest src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/application/modelo/test_import_flow.py -q`
  - 40 passed.
- `uv run --no-sync ruff check src/aeat/application/modelo/_actions.py src/aeat/domain/modelos/_calculation_revision.py src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/application/modelo/test_import_flow.py src/aeat/entrypoints/cli/_modelo.py`
  - passed.
- `uv run --no-sync ty check src/aeat/application/modelo/_actions.py src/aeat/domain/modelos/_calculation_revision.py src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/application/modelo/test_import_flow.py`
  - passed.
- `rg -n "Translatable\(" src/aeat/application/modelo src/aeat/entrypoints/cli/_modelo.py src/aeat/domain/modelos`
  - no matches.
- Broader CLI regression check:
  `uv run --no-sync pytest src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/application/modelo/test_import_flow.py src/aeat/entrypoints/cli/test_modelo.py -q`
  - application lifecycle tests passed, but five pre-existing bindings-command
  tests failed because `RegistryQueryService.bindings_for_scope` is absent.
  Those failures are outside the W80 workflow/preflight gate and were not
  changed in this step.

## `W80.P389.S2227` and `W80.P389.S2228`

Closed the W80 ADR bookkeeping after re-reading apex §4.3, apex §8,
workflow-engine-harvest, and workflow-resumption-semantics. The read-only audit
found the ADR rows were not closable as written because they still used stale
resume placement, stale helper names, file-only WorkflowEngine wording, and a
stale R16 progress-count note.

The apex ADR now ratifies the shipped W80 state:

- `app modelo work resume WORKFLOW_RUN_ID` is the accepted reconciled resume
  path; a flat `app modelo resume` path remains rejected.
- `WorkflowEngine.run_for_period` is the internal gate for both
  `app modelo work verify` and `app modelo work file`.
- `SubmissionEngine.preflight` remains WorkflowEngine-only at
  `RUNNING_PREFLIGHT`; modelo actions and CLI handlers must not call it
  directly.
- R14, R15, and R16 are marked closed by W80 with the current helper name
  `_run_revision_workflow_gate` and without stale plan-count or follow-on
  annotation claims.

The workflow-engine-harvest child ADR now reflects verify and file using the
same internal WorkflowEngine lifecycle gate. The workflow-resumption-semantics
child ADR now reflects the shipped `app modelo work resume` command and the
current backend contract: validate a prior aborted workflow run and emit
current-state retry context linked by `resumed_from_run_id`, without argv
reconstruction, trace replay, mid-stage continuation, bucket events, or
compatibility surfaces.

While closing the ADR row, the audit found the shipped CLI resume handler still
imported a non-existent `WorkflowResumeCommand` and read a non-existent
`prior_workflow_run_id` attribute. The handler now delegates directly to
`resume_modelo_workflow(workflow_run_id)` and renders
`resumed_from_run_id` as `prior_workflow_run_id` in the CLI payload/text output.

W80 ADR closure verification:

- Read-only audit confirmed the required S2227/S2228 amendments and the resume
  handler mismatch before the ADR closure.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_work_resume.py src/aeat/entrypoints/cli/test_backend_boundary.py::test_app_modelo_work_resume_help_exposes_documented_argument src/aeat/application/workflow/test_resume.py -q`
  - 14 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_work_resume.py src/aeat/application/workflow/_resume.py .vault/adr/2026-05-12-cli-workflow-redesign-adr.md .vault/adr/2026-05-12-cli-workflow-redesign-workflow-engine-harvest-adr.md .vault/adr/2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-adr.md`
  - passed.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md --json`
  - returned `[]`.
- `uv run --no-sync ty check src/aeat/entrypoints/cli/_modelo.py src/aeat/application/workflow/_resume.py`
  - still reports the unrelated pre-existing `RegistryQueryService.bindings_for_scope`
  unresolved-attribute diagnostics in the bindings list/preview handlers.

Final review follow-up:

- Review found a high compatibility risk in calculation-revision identity:
  empty borrador provenance must not change ids for already persisted
  non-borrador revisions. The derivation now includes borrador provenance only
  when it is present, and a domain test pins the original no-borrador payload
  shape while proving present borrador metadata still changes the id.
- Review found resume wording that overclaimed new-run/idempotency behavior.
  Apex, child ADR, and W80 plan text now describe the shipped contract:
  `app modelo work resume` validates a prior aborted workflow run and emits
  current-state retry context with `resumed_from_run_id`; the later verify/file
  lifecycle gates own any state transition.
- Review found checked plan rows with flat resume spelling. W80 rows now use
  the reconciled `aeat app modelo work resume` spelling.
