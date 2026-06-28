---
tags:
  - '#adr'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-action-tracker-v2-reference]]"
  - "[[2026-05-31-core-authority-types-v2-reference]]"
  - "[[2026-05-31-core-authority-constants-v2-reference]]"
  - "[[2026-05-31-core-authority-imports-v2-reference]]"
  - "[[2026-05-31-core-authority-duplicates-v2-reference]]"
  - "[[2026-05-31-core-authority-semantic-v2-reference]]"
  - "[[2026-05-31-core-authority-indirections-v2-reference]]"
  - "[[2026-05-30-identity-primitives-adr]]"
  - '[[2026-05-31-core-authority-research]]'
---
# `core-authority` adr: `core-as-single-authority-for-all-cross-module-definitions` | (**status:** `accepted`)

## Problem Statement

Six independent AST-level and GPU-accelerated semantic audits of 1,655 Python files
under src/aeat/ reveal a codebase where cross-module shared definitions -- enums,
constants, Protocols, TypeAliases, Literals, error hierarchies -- are declared wherever
they first appear and consumed across layer boundaries in both legal and illegal
directions. The audits surface 226 enum declarations distributed across domain /
application / adapter / core / entrypoint with no placement rule beyond intuition;
2,435 constant declarations with 193 same-name multi-declarations and 267 cross-module
constants not consolidated into core/external_constants.py; 84 Protocol declarations
scattered across all five layers including 26 in the adapter layer that should invert
through application-layer ports; and 9 illegal import-direction pairs totalling 471
edges (36 core-to-domain, 13 core-to-application, 4 core-to-adapters, 7
domain-to-application, 119 domain-to-adapters, 5 domain-to-entrypoint, 286
application-to-adapters, 1 application-to-entrypoint, 52 adapters-to-application). The
identity-primitives ADR established a placement rule for *_id aliases and four
enforcement clauses; this ADR extends that rule set to cover every category of
cross-module definition and mandates core/ as the single authoritative source for
definitions consumed by more than one non-owning layer.
## Considerations

The identity-primitives ADR precedent (Rule 1 placement principle, Rule 2 directional
rule, Rule 4 naming and module pattern, Rule 9 enforcement test) provides the structural
skeleton. That ADR scope was limited to *_id typed aliases; the present audits show the
same violation pattern applies to every definition kind.

The existing aeat-architecture-boundaries project rule prohibits bare dict[str, Any] at
persisted boundaries and forbids shims, compatibility layers, and duplicate legacy APIs.
The aeat-calculation-grounding rule treats type-system escapes as boundary leaks. The
aeat-registry-authority-flow rule keeps the registry compiler pipeline self-contained.
The aeat-source-hygiene rule prohibits dead code. All four rules are violated by the
current multi-declaration surface; this ADR makes them structurally enforceable.

The protect list in the action tracker identifies 13 sites classified as legitimate
architectural patterns: the core/identity/ re-export wall, the
adapters/persistence/storage/ re-export wall, the aeat.application.auth hybrid canonical
site, two lazy __getattr__ cycle-breakers in domain.transactions and domain.profile,
one side-effect import in application.user_profile, one in domain.renta, three
importlib.import_module cycle-breakers in core/profile.py, the tr brevity alias
pattern, third-party boundary aliases (PlaywrightError, PikepdfError, etc.), 28
conditional imports guarding optional packages, the per-portal ENTRY pattern (42
declarations), and the _snapshot.py plugin loader. These 13 sites are excluded from
every rule below.

## Constraints

- core/ may be imported by any layer; the inverse is illegal. The 53 illegal outbound
  edges from core/ (36 domain + 13 application + 4 adapters) must be eliminated.
- The hexagonal direction is entrypoints -> {application, adapters} -> domain -> core.
  Domain packages MUST NOT import from application/, adapters/, or entrypoints/.
  Application packages MUST NOT import from adapters/ or entrypoints/ except through
  explicit Protocol ports declared in the application layer.
- Existing load-bearing shapes -- hex-64 record aliases, UUIDv4 profile identity,
  registry alias shapes, bucket identity constraint -- are frozen and must not be
  redefined by this ADR.
- The registry compiler pipeline (TOML -> loader -> strict schema -> validated authority
  -> snapshots) remains self-contained. Registry-internal types stay inside the registry
  package unless consumed by more than one non-registry layer.
- The SnapshotRepository Protocol and three concrete live repository classes in
  application/live/ may not be dissolved; only their Protocol registration stance
  changes under Rule 9-A.
- The per-portal ENTRY pattern (42 declarations in domain/portals/_entries/) is a
  structural naming convention, not a same-name duplicate. Rule 7 does not apply to it.
## Implementation

### Rule 1 -- placement principle (extended from identity-primitives ADR)

A cross-module definition -- enum, constant, Protocol, TypeAlias, Literal alias,
TypedDict, error class, or NewType -- lives at the lowest layer that owns its constraint
shape and satisfies one or more of:
  - (a) it is imported by code outside the declaring layer;
  - (b) it carries a validator, checksum, or pattern constraint beyond a trivial length guard;
  - (c) it is consumed by adapters, persistence, or core/ as part of an inbound-port contract.

A definition used only within its own package stays in that package. A definition
consumed by more than one non-owning layer moves to core/.

Detection clause: a definition whose import sites span more than one layer directory and
is not declared in core/ is a Rule 1 violation.

### Rule 2 -- directional rule (extended from identity-primitives ADR)

The legal import direction is: entrypoints -> {application, adapters} -> domain -> core.
Imports in the reverse direction are illegal with three explicit exceptions:
  - Exception A: registry aliases declared in domain/calculations/registry/_ids.py may
    be imported by any layer per the registry-authority-flow precedent.
  - Exception B: any site on the protect list is exempt.
  - Exception C: TYPE_CHECKING-guarded annotation-only imports are permitted when no
    runtime import path exists and the annotation is not used for runtime isinstance checks.

Detection clause: any production import where the importer layer ranks lower than the
imported layer in the hexagonal order, not covered by Exception A, B, or C, is a Rule 2 violation.

### Rule 3 -- error-class hierarchy

All layer-specific error classes MUST descend from a CoreError root declared in
core/errors/_base.py. A bare Exception or ValueError subclass registered in
core/errors/_registry.py is a Rule 3 violation. Two classes with the same registration
name in _registry.py is a Rule 3 violation requiring renaming of the lower-layer class.

Detection clause: any class appearing more than once in core/errors/_registry.py is a
Rule 3 violation. Any class in _registry.py not descending from CoreError is a Rule 3 violation.
### Rule 4 -- naming and module pattern (extended from identity-primitives ADR)

- Enum declarations: _enums.py within the owning package, or core/ for cross-layer enums.
- Constant declarations: _constants.py within the owning package, or
  core/external_constants.py for external-facing or cross-layer constants.
- Protocol declarations: _protocols.py within the owning package for inbound ports,
  or core/ for infrastructure-level Protocols consumed by multiple layers.
- TypeAlias / Literal / Annotated alias: _types.py or _ids.py within the owning package;
  cross-layer aliases move to core/.
- No module may import a private name (leading underscore) from another package internal
  module unless within the same package.
- No UPPER_SNAKE_CASE constant with the same name and value as an existing declaration
  in another module may be declared a second time; the second site imports from canonical.

Detection clause: any import of a _-prefixed name from a cross-package module is a Rule 4
violation. Any UPPER_SNAKE_CASE constant in more than one production module with the
same name is a Rule 4 violation (excluding the protect list).

### Rule 5 -- bare-str identity primitive scope (extends identity-primitives ADR Rule 9)

Bare str fields are prohibited for any field whose name ends in _id, _kind, _status,
or _state on a pydantic model that is a persisted record boundary or a wire payload,
when a typed alias exists for that identity domain. This extends the identity-primitives
ADR prohibition -- which covered only *_id -- to the full *_id/*_kind/*_status/*_state
suffix set.

Detection clause: any pydantic field ending in _id, _kind, _status, or _state whose
annotation is str (or Optional[str]) with only a length/pattern constraint, on a model
at a persisted or wire boundary, when a typed alias exists, is a Rule 5 violation.

### Rule 6 -- constant centralisation

A constant encoding an external AEAT endpoint URL, a regulatory reporting threshold
(Decimal), an encoding label, or a cross-service identifier must live in
core/external_constants.py. URL constants consumed inside domain oracle modules MUST be
accessed via Settings.external_constants() at the call site; module-scope AnyUrl
constants in domain oracle modules are Rule 6 violations.

Detection clause: any UPPER_SNAKE_CASE constant whose value matches a URL pattern or a
Decimal regulatory threshold declared outside core/external_constants.py or a Settings
model is a Rule 6 violation.

### Rule 7 -- enum consolidation

An enum is a Rule 7 violation when it is semantically identical (same member names and
ordering contract) to another enum declared in a different package, or 100% duplicated
by a second declaration in the same codebase. The canonical declaration is the one in
the lower-numbered layer or, within the same layer, the one in the package that owns
the domain concept. The non-canonical declaration is renamed or deleted.

Detection clause: any two enum classes sharing all member names in any order, declared
in different packages, are a Rule 7 candidate requiring consolidation or explicit
documented divergence.
### Rule 8 -- Protocol ownership and conformance

Protocols declaring inbound ports for domain aggregates live in
domain/<aggregate>/_protocols.py. Protocols for application services live in
application/<service>/_protocols.py. Protocols consumed by more than one layer live in
core/. Concrete classes satisfying a Protocol must either (a) explicitly inherit from
the Protocol when @runtime_checkable and no import cycle results, or (b) pass a
structural mypy isinstance assertion in a non-tautological CI-gate test. The 89
domain/_repository.py files importing persistence shapes from the adapter layer violate
Rule 2; each must declare its repository interface as a Protocol in
domain/<agg>/_protocols.py.

Detection clause: any domain/ file importing from adapters/ is a Rule 8 violation.
Any Protocol class not declared in a _protocols.py module or in core/ is a Rule 8
candidate for review.

### Rule 9-A -- SnapshotRepository Protocol enforcement (resolves open question 9)

The SnapshotRepository Protocol is enforced via structural mypy conformance (Rule 8
option (b)). The three concrete live repositories (LiveBorradorRepository,
LiveCensusRepository, LiveExpedientesRepository) do not explicitly inherit from
SnapshotRepository because doing so would introduce a runtime import cycle. A
non-tautological CI-gate test asserts isinstance(repo, SnapshotRepository) for each
concrete instance using @runtime_checkable. Explicit (SnapshotRepository) inheritance
is not mandated.

Detection clause: the Rule 9-A test passes only when all three concrete repositories
satisfy isinstance(<instance>, SnapshotRepository) with @runtime_checkable active.

### Rule 9-B -- domain.calculations passthrough init (resolves open question 10)

The domain/calculations/registry/__init__.py passthrough re-exporting six symbols for
five callers is a borderline shim and is NOT added to the protect list. The five callers
must migrate to direct imports from domain.calculations.registry.*. Once migrated, the
passthrough symbols are removed from the __init__.py; the __init__.py itself is retained
as a package marker only.

Detection clause: any import from domain.calculations package init rather than
domain.calculations.registry.<module> is a Rule 9-B violation after the migration closes.

### Rule 10 -- STRICT_FROZEN config deduplication (resolves open questions 5 and 8)

A single canonical STRICT_FROZEN_CONFIG: ConfigDict is declared in core/_models.py and
exported via core/__init__.py. Every production pydantic model using a frozen strict
config imports STRICT_FROZEN_CONFIG from core/. Module-local _STRICT_FROZEN private
constants are Rule 10 violations after the migration Step closes. A pre-condition audit
verifies all 10 current declarations carry identical ConfigDict values before the merge
executes; any differing declaration receives a unique module-local name with documented
rationale.

Detection clause: any private _STRICT_FROZEN constant in a production module without a
documented intentional divergence is a Rule 10 violation.
### Rule 11 -- enforcement-test extension

The import-direction test in src/aeat/diagnostics/ is extended to 10 cumulative clauses
(4 inherited from identity-primitives ADR + 6 new):

- Clause 5: any domain.<a> module importing from domain.<b>._enums for a != b is a
  sibling-domain enum import violation.
- Clause 6: any domain.<a> module importing from domain.<b>._constants for a != b is a
  sibling-domain constant import violation.
- Clause 7: any domain.<a> module importing from domain.<b>._protocols for a != b is a
  sibling-domain protocol import violation.
- Clause 8: any production module importing a _-prefixed name from a cross-package
  module other than _ids.py is a private-name escape violation.
- Clause 9: any two production modules outside the protect list declaring an
  UPPER_SNAKE_CASE constant with the same name and same literal value is a same-name
  multi-declaration violation.
- Clause 10: any pydantic field at a persisted or wire boundary ending in _kind,
  _status, or _state using bare str with only a length/pattern constraint when a typed
  alias exists is a Rule 5 violation.

The test MUST live in src/aeat/diagnostics/ and participate in the CI gate. Its absence
or reduction below 10 clauses is a Rule 11 violation.
## Rationale

**Rule 1** extends the identity-primitives placement test to all definition kinds using
the same clause-a-b-c discriminator. The 226-enum inventory shows 18 already in core/
(correct); the rest need per-enum adjudication. The principle prevents both
over-centralisation and under-centralisation.

**Rule 2** closes all nine illegal import-direction pairs (471 edges). The three
exceptions preserve established precedents without inventing new ones.

**Rule 3** is motivated directly by FIX-001: two classes with the same name in
core/errors/_registry.py produce undefined catch behaviour. A CoreError root makes the
hierarchy a tree with well-defined catch order at every call site.

**Rule 5** extends the identity-primitives prohibition from *_id to the full
*_id/*_kind/*_status/*_state suffix set. The 54 bare-str sites the types-v2 audit
surfaces include fields outside the pure identity suffix, and the architecture-boundaries
prohibition of bare dict[str, Any] applies equally to bare str at typed boundaries.

**Rule 6** resolves open question 5 in favour of Settings.external_constants() lazy
calls: module-scope AnyUrl bindings in domain oracle modules are eliminated and URL
configuration becomes injectable without per-call-site boilerplate.

**Rule 7** resolves open questions 3 and 7 in part. The IVA rate entries are treated as an
oversight pending BOE confirmation; MERGE-013 executes after a BOE cross-reference step.

**Amendment (W13 honesty review):** CalendarCCAA is NOT a 100% geographic duplicate of CCAA.
Execution evidence (S31/S32) established incompatible value formats (ISO 3166-1 alpha-2 codes
in CCAA vs lowercase Spanish names in CalendarCCAA) and different member sets (CalendarCCAA has
24 members, CCAA includes territories not in CalendarCCAA). MERGE-002 is closed as wontfix.
CalendarCCAA remains in domain/deadlines/_festivos.py as a domain-specific calendar enum;
CCAA remains in domain/profile/_ccaa.py as the profile geographic enum. These are different
domain concepts with the same general shape but incompatible value contracts.

**Rule 8** resolves open question 4. Domain _repository.py protocols live in
domain/<agg>/_protocols.py because the domain aggregate defines the contract. No new
core/persistence/ module is introduced; core/ would otherwise carry knowledge of every
aggregate repository shape, reversing the dependency semantics.

**Rule 9-A** resolves open question 9. Structural mypy conformance is sufficient;
explicit SnapshotRepository inheritance would introduce a runtime import cycle.

**Rule 9-B** resolves open question 10. The passthrough is a borderline shim; five
migrations is tractable. A protect-list entry would ratify the pattern in perpetuity.

**Rule 10** resolves open questions 5 and 8. A single canonical constant in core/ is
correct when all 10 declarations are identical; the pre-condition audit prevents silent
collapse of intentionally distinct configs.

**Rule 11** resolves open question 1 (bare-str scope extended to all four suffixes at
persisted/wire boundaries) and makes every resolved question CI-enforceable.

**MERGE-009 / validate_identity**: the silent-accept behaviour is classified FIX (not
MIGRATE). Malformed NIF acceptance at the core/identity/ boundary is a correctness
defect; it is addressed in the same priority tier as FIX-001.

**ProfileFactValue** (open question 6): the canonical declaration is
domain/calculations/registry/_schema.py:944 because the registry owns the fact-value
contract used in formula evaluation. domain/user_profile/_values.py:48 is the
non-canonical copy and is deleted.
## Alternatives Considered

**Alternative 1: keep enum declarations in place and document cross-layer imports.**
This is the current state; it produces the 471 illegal-edge count and 193 same-name
multi-declaration count. Documentation does not prevent future violations;
enforcement-test clauses do.

**Alternative 2: move every cross-layer definition to a single core/types.py flat
module.** Collapses all 226 enums and 267 cross-module constants into one file. Rejected:
core/types.py would carry knowledge of every domain concept, inverting dependency
semantics, and creates a single-file bottleneck harder to review than per-package
_enums.py/_constants.py.

**Alternative 3: route all adapter-to-application imports through a new core/ports/
module.** Would require every application service to declare its port in core/. Rejected:
core/ would carry application-semantic port definitions; the application layer is the
correct home for service ports.

**Alternative 4: introduce domain/persistence/ to own all repository protocols.**
Creates a domain package with no records, no services, and no domain-concept ownership.
Rejected by the same reasoning the identity-primitives ADR used to reject
domain/storage/_ids.py.

**Alternative 5: require explicit (SnapshotRepository) inheritance for all three
concrete live repositories.** Would create a new application-layer import cycle with no
runtime benefit. Structural mypy provides equivalent enforcement guarantee.

**Alternative 6: add the domain.calculations passthrough to the protect list and close
RELOC-039 as wontfix.** Five direct-import migrations is not disproportionate; a
protect-list entry would ratify a shim in perpetuity contrary to the
aeat-architecture-boundaries no-shim rule.
## Consequences

### Latent bugs requiring immediate action

- **FIX-001**: adapters/outbound/aeat/export/_errors.py class ExportFormatError renames
  to AeatExportFormatError. Four call sites at adapters/outbound/aeat/export/ update.
  The canonical ExportFormatError in application/export/_errors.py is the sole
  registered entry in core/errors/_registry.py. Rule 3.
- **FIX-002**: domain/calculations/registry/_export_parse.py:402 argument order for
  _parse_decimal swaps to _parse_decimal(raw, field). A regression test asserting
  correct decimal extraction from a known fixture string is required before the commit
  lands.

### Symbols that must relocate (RELOC actions)

- **RELOC-001 through RELOC-003**: OUTPUT_LANGUAGE_ENV_VAR, DEFAULT_OUTPUT_LANGUAGE,
  SUPPORTED_OUTPUT_LANGUAGES from core/i18n/_render.py to core/external_constants.py.
- **RELOC-004 through RELOC-008**: five URL constants in domain oracle modules converted
  to Settings.external_constants() call-site reads (Rule 6).
- **RELOC-012, RELOC-013**: THRESHOLD_347_EUR merged into core/external_constants.py as
  M347_THRESHOLD_EUR (MERGE-001); THRESHOLD_720_EUR_PER_CLASS moved to
  core/external_constants.py as MODELO_720_REPORTING_THRESHOLD_EUR.
- **RELOC-015 through RELOC-020**: six application modules importing from the adapter
  layer each introduce an application-layer Protocol port (Rule 8 / MIGRATE-001,
  MIGRATE-002).
- **RELOC-021, RELOC-022**: CANCELLED (MERGE-002 is wontfix per W13 amendment). CCAA and
  CalendarCCAA are distinct domain enums with incompatible value formats; no migration occurs.
  Both remain in their respective packages.
- **RELOC-025 through RELOC-027**: 53 illegal outbound edges from core/ eliminated by
  moving referenced symbols into core/ or removing the core/ dependency (MIGRATE-006,
  MIGRATE-007, MIGRATE-008).
- **RELOC-028 through RELOC-030**: 89 domain/_repository.py adapter imports extracted to
  domain/<agg>/_protocols.py Protocols (MIGRATE-003); 7 domain-to-application edges
  corrected (MIGRATE-005); 5 domain-to-entrypoint edges hard-removed (MIGRATE-004).
- **RELOC-031, RELOC-032**: adapter ExportFormatError rename (FIX-001/RENAME-001); 52
  adapter-to-application edges broken via application-layer Protocol ports (MIGRATE-001,
  MIGRATE-002).
- **RELOC-037, RELOC-038**: BundleId and EvidenceId moved to
  application/evidence/_ids.py per identity-primitives ADR Rule 6.
- **RELOC-039**: five callers of domain.calculations package init migrate to
  domain.calculations.registry.* direct imports (Rule 9-B).
- **RELOC-040**: SnapshotRepository Protocol conformance asserted via @runtime_checkable
  plus isinstance test for all three concrete live repositories (Rule 9-A).
### Semantic duplicates that must consolidate (MERGE actions)

- **MERGE-001**: M347_THRESHOLD_EUR / THRESHOLD_347_EUR consolidated to
  core/external_constants.py; four callers updated.
- **MERGE-002**: WONTFIX (W13 amendment). CalendarCCAA is a distinct domain-specific calendar
  enum with incompatible value format and different member set from CCAA. Not a merge candidate.
  CalendarCCAA remains in domain/deadlines/_festivos.py.
- **MERGE-003**: RENAME not MERGE (W13 amendment). domain/user_profile/_values.py::ProfileFactValue
  renamed to UserProfileFactValue to eliminate name collision with
  domain/calculations/registry/_schema.py::ProfileFactValue (different shapes: 6-member union
  vs 3-member union). These are intentionally different types in different domains.
- **MERGE-005**: reconciliation status enums (RentaReconciliationStatus,
  ReconciliationStatus, ModeloReconciliationVerdict) unified under single core type.
- **MERGE-006, MERGE-007**: three _hash_file copies collapsed to
  core/hashing.sha256_file; five independent SHA-256 one-liner call sites migrate.
- **MERGE-009**: validate_identity in core/identity/ hardened to reject malformed NIFs;
  domain function calls core/identity/validate_identity; regression test added.
  Classified FIX, not MIGRATE.
- **MERGE-011, MERGE-012**: CoreError root introduced; all five ValidationError
  subclasses and three NotFoundError subclasses descend from it.
- **MERGE-013**: WONTFIX (W13 amendment). The 3-entry percentage-lookup mapping in
  domain/iva/_rate.py and the 5-entry VAT-classification mapping are intentionally different:
  they serve different domain operations (rate lookup vs classification) and the 2-entry
  difference reflects different legal categories, not a data gap. BOE review confirmed the
  two mappings are not duplicates.
- **MERGE-014**: _STRICT_FROZEN consolidated to STRICT_FROZEN_CONFIG in core/_models.py
  after pre-condition audit confirms identical values across all 10 declarations
  (Rule 10).
- **MERGE-015**: _ActorLabel renamed to domain-specific labels (BucketActorLabel,
  ModeloActorLabel, etc.) eliminating the five-way name collision.

### Dead constants that must be deleted (DELETE actions)

- **DELETE-001 through DELETE-008**: eight zero-consumer constants across
  application/workflow/, domain/fincas/, and core/external_constants.py deleted.

### Name collisions that must be disambiguated (RENAME actions)

- **RENAME-002**: ModeloCapability Literal renamed to ModeloFilingCapability.
- **RENAME-003**: duplicate ParityStatus collapsed to single definition in _parity_tapes.py.
- **RENAME-004**: duplicate EvidenceTier collapsed to single definition in _schema.py.
- **RENAME-005**: _VerifyVerdict Literal at entrypoints/cli/_app_live.py:29 removed;
  VerifyVerdict imported from application/live/_verify.py.
- **RENAME-009**: ERROR_CODES renamed to AggregationErrorCodes and
  OperatorSurfaceErrorCodes in their respective modules.

### Promote actions

- **PROMOTE-001**: 54 bare-str identity-primitive sites enrolled in typed aliases (Rule 5).
- **PROMOTE-002**: domain repository Protocol method signatures annotated with SubjectTaxId.
- **PROMOTE-003**: CoreError root introduction (MERGE-011).
- **PROMOTE-004**: AggregationSourceKind re-exported via core/__init__.py.

### Enforcement test mandate

The diagnostics test in src/aeat/diagnostics/ carries 10 cumulative clauses (4 from
identity-primitives ADR plus 6 from Rule 11). Its absence or reduction below 10 clauses
is a Rule 11 violation.

## References

- `2026-05-31-core-authority-action-tracker-v2-reference` -- 91 action rows, 10 open questions, 2 latent bugs
- `2026-05-31-core-authority-types-v2-reference` -- 226 enums, 84 Protocols, 268 collective type-alias inventory
- `2026-05-31-core-authority-constants-v2-reference` -- 2,435 constants, 193 same-name multi-declarations, 267 cross-module gap
- `2026-05-31-core-authority-imports-v2-reference` -- 5x5 layer matrix, 471 illegal edges across 9 direction pairs
- `2026-05-31-core-authority-duplicates-v2-reference` -- 449 duplicate names, 152 cross-layer duplicates
- `2026-05-31-core-authority-semantic-v2-reference` -- GPU-accelerated semantic pairs, FIX-001 and FIX-002 surface
- `2026-05-31-core-authority-indirections-v2-reference` -- 19 rename-on-import aliases, 28 conditional imports, protect-list classification
- `2026-05-30-identity-primitives-adr` -- identity-primitive placement precedent this ADR extends
