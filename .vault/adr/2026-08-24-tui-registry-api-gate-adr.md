---
tags:
  - '#adr'
  - '#tui-registry-api-gate'
date: '2026-08-24'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:a03225789b66c36c27ff9679080da83f103746634f9122cc508a002d245db7f4'
related:
  - '[[2026-08-24-tui-registry-api-gate-research]]'
  - '[[2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit]]'
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-08-11-tui-interface-adr]]'
  - '[[2026-08-10-casilla-schema-read-model-adr]]'
  - '[[2026-08-10-casilla-schema-canonical-derivations-adr]]'
  - '[[2026-08-10-casilla-schema-blocker-spine-adr]]'
  - '[[2026-08-08-profile-requirement-grounding-adr]]'
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
  - '[[2026-06-10-period-revision-resolution-adr]]'
  - '[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]'
  - '[[2026-08-24-registry-completeness-closure-adr]]'
  - '[[2026-08-22-source-casilla-integration-adr]]'
  - '[[2026-08-04-modelo-localization-cascade-adr]]'
  - '[[2026-08-09-cli-action-envelope-hardening-adr]]'
  - '[[2026-08-24-tui-modelo-workspace-interface-adr]]'
  - '[[2026-08-25-tui-architecture-workspace-owner-seam-reconciliation-audit]]'
  - '[[2026-08-25-tui-architecture-s160-native-work-capture-owner-atomicity-reconciliation-audit]]'
  - '[[2026-08-25-tui-architecture-s160-approved-amendment-architecture-review-audit]]'
---
# `tui-registry-api-gate` adr: `read-only Modelo workspace projection and capability API` | (**status:** `accepted`)

## Canonical defining-module amendment

This in-place amendment replaces every package-facade and facade-promotion
clause in this record. Workspace V1 models live in
`cadrumo.application.modelo.workspace_models`; producer contracts in
`cadrumo.application.modelo.workspace_producers`; the generated field
denominator in `cadrumo.application.modelo.workspace_manifest`; and assembly
and dispatch in the sole public `cadrumo.application.modelo.workspace` defining
module. The Modelo package namespace is inert.

Native work capture lives in the public
`cadrumo.application.modelo.work_addressing` defining module. Active-profile
pointer capture lives in its exact public defining module under
`cadrumo.application.user_profile`. Each canonical owner exposes native capture
and current-generation operations from the module that defines them; S126
registration imports that module directly and never receives a package
re-export. Lower owners still never import or construct `ModeloWorkspace*`
types.

Every former private definition hard-moves to its canonical public module with
all production, test, registration, receipt, dynamic, and tooling consumers;
the old definition and package export are deleted in the same commit. No shim,
alias, fallback, bridge, private cross-package import, or parallel owner is
permitted. All lifecycle, epoch, baseline, ABA, owner-generation, capability,
cohort, and receipt decisions below remain unchanged.

## Problem Statement

The accepted bounded Casilla review model is sufficient for its existing
read-only screen, but it is not a stable, coverage-proven contract for a complex
Modelo workspace. Direct frontend use of registry snapshots, secure persistence
records, development-only closure joins, or private assemblers would make the
frontend interpret authority and would turn registry evolution into an
untracked interface change.

This record establishes only a versioned, frontend-neutral, read-only
`ModeloWorkspaceProjection` V1 and its capability/refusal facade. It does not
own operation observation, mutation commands, editing, persistence, TUI
information architecture, or visual composition. The evidence and ownership
reconciliation are grounded in `2026-08-24-tui-registry-api-gate-research` and
`2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit`.

## Considerations

- Natural Modelo work addressing and law-determined revision selection are
  accepted authorities; a workspace is their consumer, not a new selector
  (`2026-06-04-modelo-addressing-ux-adr` and
  `2026-06-10-period-revision-resolution-adr`).
- Static revision inspection and a grade-admitted snapshot make different
  authority claims and cannot be represented as one degraded result
  (`2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr`).
- Modelo readiness, registry closure, source connectivity, export proof,
  blocker classification, and recovery action identity already have canonical
  producers. Workspace capability must project those answers without
  recomputing them.
- Complex read surfaces require scalar and repeated-row materialization plus
  typed source lineage, while retaining the accepted row and provenance
  identities (`2026-08-22-source-casilla-integration-adr`).
- Schema is language-neutral. Display text is resolved through the canonical
  localization cascade and locale changes cannot alter domain identity,
  values, or capability (`2026-08-04-modelo-localization-cascade-adr`).
- `ModeloWorkReview` remains the accepted canonical bounded C1 projection with
  one public producer. Workspace V1 is a wider read model around that exact
  facet, not a second assembler or its replacement
  (`2026-08-10-casilla-schema-read-model-adr`).
- Profile readiness retains an explicit per-operation assessment axis whose
  `false` state means nothing on that axis was examined and whose `true` state
  still means only that tokenised required fields were examined. Neither state
  is a Modelo-completeness verdict
  (`2026-08-08-profile-requirement-grounding-adr`).
- Public operation observation is the external amendment established by
  `2026-08-24-tui-operation-observation-adr`. Modelo workspace presentation and
  editing are the external interface/write-side boundary established by the
  accepted `2026-08-24-tui-modelo-workspace-interface-adr`. Neither record is
  implemented merely because Workspace V1 exists.
- The native `work` contribution needs a physical owner coordinate, an atomic
  catalogue observation, and a registry-independent selector before the generic
  owner seam is implementable; the unresolved evidence is recorded by
  `2026-08-25-tui-architecture-s160-native-work-capture-owner-atomicity-reconciliation-audit`.
- The approved amendment still needs an authoritative implicit-pointer
  transition coordinate, a safe physical comparison domain, and independent
  requested/stored revision evidence; those three gaps are isolated by
  `2026-08-25-tui-architecture-s160-approved-amendment-architecture-review-audit`.

## Considered options

- **Grow `ModeloWorkReview` into the workspace contract.** Rejected because it
  would destroy a deliberately bounded projection and destabilize existing
  consumers.
- **Expose registry snapshots or development reports to frontends.** Rejected
  because it leaks compiler grammar and makes presentation code interpret
  authority, applicability, and evidence.
- **Let each frontend assemble schema, values, readiness, and closure.**
  Rejected because it creates multiple joins, refresh rules, and capability
  truths.
- **Combine read state, operation observation, and editing in one workspace
  contract.** Rejected because those concerns have different lifecycle,
  persistence, and decision owners.
- **Create one application-owned read-only Workspace V1 with typed admission,
  capability, refusal, and baseline-consistent facets.** Chosen because it
  gives complex readers one stable boundary while every underlying authority
  retains its single home.

## Constraints

- Workspace V1 lives behind the public `cadrumo.application.modelo` facade. It
  exposes no private registry model, repository, persistence DTO, raw
  exception, frontend type, callback, command request, or untyped payload bag.
- A request uses exactly the existing discriminated
  `ModeloVisibleFilingTarget` or `ModeloExactWorkUnitTarget`. The visible target
  is active bucket or explicit bucket plus Modelo, filing year, and period. An
  exact work-unit target is an advanced address whose optional bucket assertion
  must agree with the stored work unit. The generic `ModeloWorkAddress` is an
  internal normalization shape, not a Workspace or native-capture operand. A
  missing exact target refuses. Zero visible matches yield an explicit
  absent-work success; exactly one visible match resolves whether active or
  discarded; any mixed or same-state multiple match refuses ambiguity. An
  active-only lifecycle operation may exclude discarded work from its reusable
  candidate set, but that filter never changes Workspace read addressability.
  The workspace never creates or selects a work unit.
- The request separately chooses `static_inspection` or `graded_snapshot`
  admission. Static inspection is not an authority grade and cannot calculate,
  draft, export, or expose materialized work values. Graded admission names one
  required `RegistryAuthorityGrade`; the law-selected revision either satisfies
  it or the result refuses without downgrade.
- A requested visible-target revision and a stored work-unit revision are
  independent assertion evidence only. The producer always selects from
  Modelo, filing year, and period, evaluates both typed source axes against the
  law-selected result, and reports either mismatch without resolving through
  an asserted id.
- Every capability answer is copied from its canonical public producer with
  its coordinate and evidence. Absence of a producer or measurement is
  `unmeasured`, never available. Workspace V1 does not infer readiness from
  schema population, layout presence, lifecycle state, or neighbouring
  capabilities.
- Every canonical owner contributing to a successful projection exposes through
  its public facade one native atomic projection-plus-generation capture and one
  current-generation read. The application-owned Workspace boundary alone wraps
  that surface in S126 contract, stamp, epoch, and port types. A lower layer never
  imports or returns a `ModeloWorkspace*` type. An owner that cannot provide the
  native atomic pair cannot participate in a successful Workspace projection.
- Locale affects display fields only. The canonical locale resolver supplies
  the key, requested language, resolved language, and fallback or suppression
  disposition. The workspace never reads schema-carried prose, constructs
  locale keys, or falls from one non-Spanish locale to another.
- Boundary models are strict, frozen, discriminated, and typed. Casilla,
  binding, formula operand, relation endpoint, aggregation, source, row, and
  provenance identities retain their canonical namespaces.
- Financial values, raw secret material, and unsafe source identities never
  enter baselines, refusal facts, diagnostics, field-classification manifests,
  or locale metadata. Safe provenance retains only the canonical typed roles
  and approved opaque references or fingerprints.
- A workspace baseline is a safe opaque consistency token, not approval,
  authorization, a mutation precondition, or a persistence identity.
- V1 is the sole supported in-tree workspace version. Missing, unknown, old, or
  future versions return a typed version refusal. A breaking change migrates
  all in-tree consumers atomically and deletes the retired contract; no dual
  reader or compatibility projection remains.

## Implementation

### V1 request, admission, and result

Introduce a minimal version-dispatch envelope plus the strict
`ModeloWorkspaceRequest`, `ModeloWorkspaceResult`,
`ModeloWorkspaceProjection`, `ModeloWorkspaceRefusal`, and
`ModeloWorkspaceBaseline` V1 models. A successful V1 parse and every
coordinate-bearing V1 result carry `contract_version = 1`. The dispatcher reads
only the declared version before constructing a V1 request, so an unsupported
version can refuse without parsing a target or touching secure state. The V1
request contains one canonical work target, one explicit admission request, and
one output language. It contains no revision selector or calculation-revision
selector; `ModeloVisibleFilingTarget.registry_revision_id`, when present,
remains an equality assertion.

After version validation, the result resolves the target and law coordinate,
then discriminates:

- `static_inspection` carries only the validated static registry projection and
  explicitly records that no snapshot was admitted;
- `graded_snapshot` carries the requested, declared, and effective grade plus
  the exact admitted snapshot scope; or
- `refused` carries the failed boundary without a partial snapshot disguised as
  success.

Every coordinate-bearing result after version validation echoes Modelo, filing
year, period, resolved bucket and work state, law-selected revision,
stored-revision assertion outcome, admission kind, review status, evidence
horizon, family dispositions, contract version, field-classification digest,
canonical registry schema identity and fingerprint, locale summary, and
baseline when a projection was assembled. An absent work unit is explicit read
state; the facade never creates one.

### Canonical bounded review facet

`ModeloWorkspaceProjection.work_review` is the canonical bounded C1 facet. When
the admission path permits a work review it is the exact frozen
`ModeloWorkReview` produced for the resolved coordinate by
`build_modelo_work_review(...)`; static inspection and other ineligible paths
carry a typed facet disposition rather than a partial or reconstructed review.
The Workspace producer must not independently join or reinterpret the Casilla
schema, realised values, verification, findings, progress, blockers, or origin
layers owned by that record.

If atomic Workspace capture requires sharing a lower-level materialization,
`build_modelo_work_review(...)` and the Workspace producer delegate to one
application-owned pure semantic assembler over the same captured inputs. The
accepted function remains the sole public `ModeloWorkReview` producer. A
fixed-point test compares the complete Workspace facet with the complete public
producer result, including absent-work and refusal behavior, for every selected
fixture coordinate. Any unequal field, identity, ordering, disposition, or
evidence reference fails C1 parity and therefore C2; a second independently
maintained review join is forbidden.

### Schema, materialization, and provenance projection

Workspace schema records are explanatory application DTOs. They preserve the
canonical Casilla, binding, relation, formula, parameter, continuity, export
exposure, applicability, constraint, legal, and source-reference identities
needed by a reader without exporting registry compiler objects or selectors.

Scalar values remain keyed by `CasillaId`. Repeated materialization preserves
the canonical binding or projection identity and positive row index as separate
typed coordinates; it never flattens a row into a synthetic scalar id. Formula
operands and relation endpoints retain their discriminated namespaces.
Provenance is projected from the canonical calculation-source graph: resolved
source, contributor source, `PRIMARY` or `CONTRIBUTOR` role, safe source
reference, fingerprint, and parent reference. The assembler may select and
redact those records but cannot synthesize an alternate owner, edge, identity,
or causal graph.

**Amendment (S284): a schema record's `label` is either a real localization
or an honest technical identifier, never a bare id presented as one.**
`modelo_localization.py` derives locale keys for modelo, revision, construct,
and casilla identities only; formula, binding, relation, and parameter
identities have no key-derivation function and no locale-catalogue entry
anywhere in the tree. Checked whether any of the four are ever
operator-facing before ruling: every existing consumer (`work_review.py`'s
findings, the discovery CLI's missing-binding diagnostics) already displays
these identifiers as themselves -- registry names, never translated prose --
so the absence of a locale convention is not an oversight to fill, it is the
correct reflection of what these identities are.

`ModeloWorkspaceSchemaRecordV1.label` is now the discriminated
`ModeloWorkspaceRecordLabelV1 = ModeloWorkspaceLocalizedTextV1 |
ModeloWorkspaceTechnicalLabelV1`. A CASILLA row's label is the existing
`ModeloWorkspaceLocalizedTextV1` (`kind="localized"`), carrying a real
resolved locale summary. A FORMULA, BINDING, RELATION, or PARAMETER row's
label is `ModeloWorkspaceTechnicalLabelV1` (`kind="technical"`), carrying
only its own `identifier` -- no locale summary, because none was resolved
and claiming one would be false. This is the same shape of decision as
S283's `None`-versus-`()`: a field whose type could not previously express
"this row's name was never translated" now can, and a bare identifier can
no longer silently masquerade as a localization that happened.

**Amendment (S277): each schema-record join is the registry's own declared
edge, never a name-matched inference.**

- **`formula_operands` is the INPUT direction only.** `FormulaExpression` is a
  self-recursive registry-declared tree (an operator node carries `args`; a
  leaf carries exactly one populated identity field --
  `casilla_id`/`binding`/`date_binding`/`parameter`/`relation`/`literal`/
  `dispatch_table`); walking that tree and mapping each populated leaf 1:1 to
  its matching `ModeloWorkspaceFormulaOperandReferenceV1` variant needs no
  inference at all. A casilla row's `formula_operands` lists the entries
  where that walk names `casilla_id` equal to the row's own id -- the
  formulas that READ this casilla as an operand. The OUTPUT direction
  (`FormulaDefinition.target_casilla_id`, which formula this casilla's value
  comes from) is a provenance-facet concern, already covered above by "the
  canonical calculation-source graph," and is never represented by
  `formula_operands`, which is why the field is plural and multi-kind
  discriminated: one casilla can be read as an input by many different
  formulas, but is the output of at most one.
- **`relation_endpoints` matches `RelationDefinition`'s own named fields
  exactly.** `source_casilla_id: CasillaId` names the source side;
  `target_binding: BindingId` names the target side. A casilla row's
  `relation_endpoints` includes a `ModeloWorkspaceRelationSourceEndpointReferenceV1`
  wherever `relation.source_casilla_id` equals that casilla; a binding row's
  includes a `ModeloWorkspaceRelationTargetEndpointReferenceV1` wherever
  `relation.target_binding` equals that binding. No other casilla or binding
  may ever claim either endpoint of a relation it is not named on.
- **`constraints` is self-owned; no cross-casilla join exists or is needed.**
  `CasillaConstraints` is embedded directly on `CasillaDefinition.constraints`
  (never a separate registered collection with its own id), so a casilla's
  constraint entry is always its own -- there is no "which casilla owns a
  multi-casilla constraint rule" question in the current registry shape,
  because no constraint rule spans more than the one casilla that embeds it.
- **`applicability` has no casilla-level registry edge and MUST stay empty on
  every casilla, binding, formula, relation, or parameter row.**
  `ApplicabilityRuleDefinition` is scoped to the REVISION
  (`revision.applicability`, resolved as a single per-modelo rule via
  `resolve_applicability_rule_from_authority`), never to a specific casilla;
  no field anywhere in the registry schema points an `ApplicabilityRuleId`
  reference at a casilla. Populating a per-casilla `applicability` field
  from a revision-wide rule would misrepresent a fact about the WHOLE
  MODELO's applicability as though it were specific to one casilla. The rule
  itself is exposed only via its own `reference.kind == "applicability"`
  schema record, never attached to another row.

If a future registry revision introduces a genuine casilla-scoped
applicability edge, that is a new registry field to add and re-ground this
amendment against -- never a Workspace-side inference from the
revision-scoped rule.

**Amendment (S283): a STATIC_INSPECTION casilla row is bounded to identity
alone; `legal_refs` and `constraints` are `None` for it, never `()`.**
`RegistryRevisionInspection`'s own docstring states it retains "the source,
casilla, binding, projection, and legal IDENTIFIERS to validate generated
static artefacts" and "cannot calculate, render, or file anything" --
identifiers, not definitions, is a deliberate boundary, not an oversight.
Enrolling `CasillaDefinition` (or its `constraints`/`legal_refs` slices) onto
the inspection would contradict that stated design: `CasillaConstraints`
carries `min_value`, `max_value`, `enum` (`schema_surfaces.py:121-126`) --
declared regulatory values, exactly the filing-adjacent content the boundary
exists to exclude. A CASILLA row for STATIC_INSPECTION therefore carries no
`CasillaDefinition`-sourced fields at all.

The harder part is representing that absence honestly.
`ModeloWorkspaceSchemaRecordV1.legal_refs` and `.constraints` are now typed
`... | None`, defaulting to `()` for every existing (graded) caller: `None`
means this admission's producer never carries the underlying data for this
reference kind; `()` means it does, and none is declared. Collapsing both
into a bare empty tuple would have been a silent under-declaration in a
field whose whole purpose is legal grounding -- the same failure class as
inferring a capability disposition, and the same rule applies: absence must
be representable and distinguishable from a declared nothing. A STATIC_INSPECTION
casilla row's `legal_refs` and `constraints` are always `None`.

FORMULA, BINDING, RELATION and PARAMETER rows are unaffected by this
boundary: `FormulaDefinition`, `DataBindingDefinition` and
`RelationDefinition` each declare `legal_refs` directly, so those row kinds
carry real tuples (possibly empty by genuine declaration) under
STATIC_INSPECTION exactly as they would under a graded snapshot. Only the
CASILLA row's `CasillaDefinition`-sourced fields are affected.

Left open, deliberately out of this amendment's scope because the governing
Step did not name it: `source_refs` has the identical shape of problem for a
casilla row (`CasillaDefinition.source_refs` is equally absent from the
inspection) but stays a plain empty-tuple-defaulting field for now. A future
Step should decide whether `source_refs` gets the same `None` treatment
rather than this amendment silently deciding it by omission.

### Generated field-classification denominator

One generated manifest recursively derives the complete registry
model-and-field universe from the current validated public schema types,
including nested types, discriminated variants, and collection element types.
Every reachable leaf field path and variant branch is classified exactly once
as `projected`, `derived`, or `backend_only`. A projected row names its
Workspace V1 destination; a derived row names its canonical producer and
derivation; a backend-only row names its owner and bounded reason. Counts,
hand-maintained field lists, and permanent allowlists are not denominators.

The fixed-point gate independently regenerates the manifest and refuses an
unclassified, duplicate, stale, or missing field path. The manifest is
conformance evidence, not runtime registry authority, and it never causes a
backend-only field to enter the public payload.

**Amendment (S278): STATIC_INSPECTION gets its own complete manifest over its
own type universe, never a filtered view of the graded manifest.** The prior
text described one generator without naming its root, and the only generator
built walked `RegistrySnapshot` -- a type universe a static inspection never
loads (`RegistryRevisionInspection` "cannot calculate, render, or file
anything," and structurally carries neither materialization, verification,
nor filing state). Reusing that manifest for static inspection, with
per-entry availability layered on top, was considered and rejected: it is the
same "one degraded result presented as a complete one" pattern this record
already rejects for the REGISTRY projection itself ("Static revision
inspection and a grade-admitted snapshot make different authority claims and
cannot be represented as one degraded result"), and the identical reasoning
applies to the manifest with no less force.

`generate_modelo_workspace_field_manifest_for_inspection` roots a second walk
at `RegistryRevisionInspection` itself, reusing the SAME classification
function (`_classify_node`/`_projected_destination`) applied to a second root
-- not a second, independently authored copy of the classification rules,
since the underlying registry-compiler types (`FormulaDefinition`,
`DataBindingDefinition`, `RelationDefinition`, and the identity kinds they
carry) are the identical types both roots reach, just through different
container shapes. The two admissions' manifests carry distinct digests over
distinct traversal roots and are never compared against each other's
coordinate. `RegistryRevisionInspection` carries no full `ModeloRevision`, so
its manifest has no `derived.export_layout.*` root; the `selector.*` roots
are shared unchanged, since selector models are a pure function of
`BindingSourceKind`, independent of which admission is reading.
`ModeloWorkspaceFieldManifestPortV1` accepts either admission's authority
object and dispatches to the matching generator.

### Canonical capability and refusal facade

Workspace V1 reports the closed read-only capability set for schema inspection,
calculation materialization, verification readiness, filing-draft readiness,
and filing-export readiness. Each record is `available`, `not_applicable`,
`refused`, or `unmeasured` and carries the exact target and revision coordinate,
canonical producer identity, safe evidence references, and source disposition.

**Amendment (S279): the capability-to-producer mapping is exact, not
name-matched.** Static inspection captures exactly `registry`, `work`,
`locale_catalogue`, and `field_manifest`; it does not read `bounded_review`,
`calculation`, `readiness`, or `closure` (see "Locale and consistency
boundary" above). That is four contributors excluded from static inspection
against four non-schema capabilities, and the correspondence is fixed by each
contributor's own stated role, not inferred from the capability's enum
spelling:

| Capability | Canonical producer contributor | Grounding |
|---|---|---|
| `schema_inspection` | `field_manifest` (`workspace_field_manifest`) | Schema inspection is reading the classified field denominator; `field_manifest` is its sole producer. `W03.P20.S278` resolved static inspection's own manifest root, so `field_manifest` is a real STATIC_INSPECTION contributor and `schema_inspection` is `available` for that admission -- the one capability static inspection answers `available` for. |
| `calculation_materialization` | `calculation` (`calculation_materialization`) | Identical producer-identity string; no inference required. |
| `verification_readiness` | `bounded_review` (`modelo_work_review`) | `ModeloWorkReview` is the accepted canonical bounded review projection tracking verification state, findings, and progress (`2026-08-10-casilla-schema-read-model-adr`) -- the review facet IS the verification-readiness fact. |
| `filing_draft_readiness` | `readiness` (`modelo_readiness`) | `ProjectionModeloReadiness`'s axes (`profile_ready`, `registry_ready`, `binding_ready`, `ledger_ready`) are exactly the preflight gate checked before a filing draft can be produced, discussed immediately below this table in the existing "Modelo readiness is selected from..." paragraph. |
| `filing_export_readiness` | `closure` (`registry_closure`) | The closure report's own limb is named `filing-export` in the existing "Registry completeness is selected from..." paragraph below -- an exact limb-name match. |

**Amendment (S279): `not_applicable` is reserved for a coordinate-level fact
about the FILING TARGET, never for a contributor an admission structurally
never reads.** The single existing rule -- "absence of a producer or
measurement is `unmeasured`, never available" -- governs both cases: a graded
snapshot whose canonical producer declined to answer, AND a static inspection
whose admission kind never invokes the contributor at all, are both
"absence of a producer" for that read. Static inspection's four excluded
capabilities (`calculation_materialization`, `verification_readiness`,
`filing_draft_readiness`, `filing_export_readiness`) are therefore
`unmeasured`, not `not_applicable` -- reversing the disposition this record
previously accepted without this table, which had reasoned from
`RegistryRevisionInspection`'s own docstring ("cannot calculate, render, or
file anything") rather than from this rule. That docstring answers a
different question -- whether the admission COULD ever produce the fact --
not the question the disposition enum encodes, which is whether THIS read's
canonical producer answered. `not_applicable` remains reserved for a graded
snapshot that DID invoke the right producer and that producer declared the
capability inapplicable to the specific target (for example, a source
disposition of `not_required` for the filing target's regime) -- a
target-level fact from a producer that ran, never an admission-level fact
about a producer that never ran.

Modelo readiness is selected from the canonical
`ProjectionModeloReadiness` without collapsing its axes. The Workspace DTO
preserves `profile_ready`, `per_operation_requirements_assessed`,
`registry_ready`, `binding_ready`, `ledger_preflight_required`, nullable
`ledger_ready`, the corresponding missing requirements/issues/refusals, and
the aggregate `ready` value exactly as produced. It does not rename or erase an
unassessed axis. In particular, `ProjectionModeloReadiness.ready` alone can
never produce capability disposition `available`: the aggregate currently
does not prove that the per-operation profile axis was assessed, and
`per_operation_requirements_assessed = true` proves only the tokenised subset,
not complete Modelo requirements. `available` requires a separately stamped,
explicit verdict from the canonical producer responsible for that exact
capability and coordinate. Without that verdict, or when its declared
assessment is incomplete or unknown, the capability is `unmeasured` rather
than inferred.

Registry completeness is selected from the canonical cross-authority closure
report and its temporal, source-connectivity, and filing-export limbs. Blockers
retain their native code and total `OperatorActionAxis` projection. An optional
recovery `ActionReference` is copied from the action catalogue; it is guidance
only and grants no invocation authority. If a canonical production producer or
join has not landed, the workspace reports `unmeasured` and never recreates a
development-only join.

A domain refusal contains a stable code, affected capability or admission
boundary, requested coordinate, selected coordinate when resolution reached
one, safe typed facts, canonical evidence references, responsible
owner/disposition, reconsideration condition, and optional canonical action
reference. The pre-parse version refusal remains the minimal version-only arm.
Localized command prose and raw exceptions never enter either arm. Global
registry completeness need not be satisfied for Workspace V1 to render; an
evidence-backed refusal is valid workspace data.

### Native-owner capture and application-owned Workspace contract seam

The semantic projection and its consistency generation remain owned by each
canonical contributor. Each owner exposes through its canonical public facade
one native operation that atomically returns an immutable or snapshot-isolated
owner projection together with an owner-local ABA-safe monotonic generation,
plus one native read of the current generation. The generation advances on
every owner-state transition that can change the contributed projection,
including A -> B -> A. It is not a payload digest, timestamp, value-equality
marker, Workspace baseline, or counter minted by Workspace code.

Native generations are monotonic within one owner process incarnation. S126
epoch schema version 2 adds one safe opaque `comparison_domain` beside the
unchanged native integer generation. The native owner derives that domain from
its canonical physical owner scope and the application process incarnation;
the S126 registration copies it unchanged and never derives it from the
semantic contributor name. Raw roots, buckets, namespaces, keys and pointer
paths never enter the domain token or a Workspace payload. Epoch equality,
successor comparison and second-pass currentness first require exact domain
equality; a different root, physical owner scope, or process incarnation
refuses as `workspace_changed` without comparing generation integers.

The complete version-2 epoch coordinate -- owner, kind, schema version,
comparison domain and unchanged native generation -- participates in the
sorted contributor epoch digest, Workspace baseline token and every cursor or
facet continuation token. S126's producer-contract and inventory digests change
because their declared epoch schema version becomes 2; the runtime comparison
domain itself belongs only to the captured epoch and epoch digest, never the
static producer stamp. Revalidation requires that same domain before any
ordinal comparison. There is no schema-version-1 reader or dual epoch path.
The incarnation coordinate grants no authorization, contains no owner data,
and is not a substitute owner generation or a durable shadow counter. Lower
owners return their native projection, native integer generation and neutral
opaque comparison-domain token only; they never import or mint a
`ModeloWorkspace*` type.

The Workspace-specific contract remains owned exclusively by
`cadrumo.application.modelo`. For each contributor kind, the application
declares exactly one `ModeloWorkspaceProducerContractV1` and exactly one
`ModeloWorkspaceAtomicProjectionPortV1` realization over the owner's public
native capture surface. That realization performs exactly one native capture,
derives the safe Workspace contribution only from the captured immutable or
otherwise snapshot-isolated value,
constructs `ModeloWorkspaceProducerStampV1` from the application contract, and
preserves the owner's generation and opaque comparison domain unchanged in
`ModeloWorkspaceEpochV1` using epoch schema version 2.
`read_current_stamp_and_epoch` combines the same contract-derived stamp with
the canonical owner's native current-coordinate read. A lower layer never
imports, constructs, or returns a `ModeloWorkspace*` type.

This registration is application composition, not a second semantic owner,
compatibility adapter, or bridge. It owns no contributor state, cache,
generation, selector, review or readiness calculation, closure join, source
graph, or locale resolution; it cannot reread a repository, loader, or owner
while projecting a captured value. No shim, fallback, non-`__init__` re-export
bridge, adapter-package implementation, or alternate owner API is permitted.
Promotion through the canonical owner's package facade remains mandatory. If
an owner cannot provide atomic native capture and current-generation semantics,
that contributor cannot be registered and Workspace returns
`consistency_unavailable`.

The contributor fixed point is exact:

| Kind | Canonical semantic owner | Producer identity |
|---|---|---|
| `registry` | `domain.calculations.registry` | `validated_registry_projection` |
| `work` | `application.modelo.work_addressing` | `resolved_work_target` |
| `bounded_review` | `application.modelo.work_review` | `modelo_work_review` |
| `calculation` | `application.modelo.calculation` | `calculation_materialization` |
| `readiness` | `application.state_projection` | `modelo_readiness` |
| `closure` | `application.registry` | `registry_closure` |
| `locale_catalogue` | `locales` | `locale_catalogue` |
| `field_manifest` | `application.modelo.workspace_manifest` | `workspace_field_manifest` |

`ModeloWorkspaceProducerContractInventoryV1` inventories these eight
application-owned S126 registrations, not contracts implemented by lower-layer
owners. Each contract fingerprints the safe application projection schema.

**Amendment (S274):** the fingerprint is derived from the projection's
SERIALIZATION JSON schema alone, not from requiring the validation and
serialization schemas to coincide. A port projects outward, so the
serialization shape is the contract a consumer actually receives; the
validation shape is an input-acceptance detail the fingerprint does not need
to identify. The property this fingerprint must hold is a round trip --
`model_validate_json(instance.model_dump_json())` reproduces the instance --
not shape coincidence between the two schemas. A bare `Decimal` field
validates as `anyOf[number, string]` but serializes as `string` alone; that
string parses straight back to the same `Decimal`, so it round-trips cleanly
and was never a broken contract, only an equality check with the wrong
proxy. The original equality requirement was exercised only against a
string-and-enum manifest and had never met a Decimal-bearing model before
S167 tried to register the registry snapshot, the work review, and the
calculation revision -- the three contributors that carry financial data by
nature and were consequently unregisterable. Retyping their Decimal fields to
satisfy the fingerprint was rejected: it would change how financial amounts
serialize everywhere those models are used, far beyond Workspace, which
inverts which of the two is load-bearing.

One S126 capture calls its canonical owner's native capture exactly once,
projects only that captured value, and returns the application projection,
contract-derived stamp, and unchanged native generation. The second-pass read
returns the unchanged contract-derived stamp and the same owner's current
native generation. Neither operation may mint an owner generation or obtain a
second semantic value. Missing, duplicate, stale, misidentified, or
unclassified registrations fail the generated fixed-point gate.

### Native WORK capture and registry separation

The native `work` capture is a work-only read over the canonical public
`ModeloVisibleFilingTarget | ModeloExactWorkUnitTarget` input. It returns the
existing strict frozen `ModeloWorkResolution` together with the native owner
generation. It does not call registry authority, select a legal revision,
create or mutate work, translate into a Workspace model, or perform a second
repository read. The broad address DTO and any union containing it stay inside
command normalization and cannot widen this public capture boundary.

Exactly one pure selector operates on a supplied captured
`WorkUnitCatalogue`. In visible-read mode it considers every lifecycle state:
zero matches produces `ABSENT`, one active or discarded match produces
`RESOLVED`, and every multiple set -- active, discarded, or mixed -- refuses as
ambiguous. Exact lookup refuses absence but returns a single discarded unit so
downstream read and terminal-state policy can observe it. The active-only
create-or-reuse mode delegates to the same selector while limiting its natural
candidate set to active work; it is not a second scan or selection authority. A
requested revision is retained as assertion evidence and never narrows the
candidate set.

Native capture is blocked until the persistence port can return the catalogue
and its persistence revision from one and the same `SecureObjectRecord`. A
document load followed by a revision reload is not an atomic observation. Both
singleton wire-shape kernels must satisfy the one-record invariant, and the work
repository protocol and concrete repository must expose that invariant without
an application-side storage path. The selector consumes only that captured
catalogue; all substitutable repository scans and raw-selector copies converge
on it or are deleted.

The physical native owner coordinate is the canonical resolved storage or
repository root, resolved bucket, work-catalogue namespace and singleton object
key. When the caller omits `bucket_id`, the root-scoped active-bucket pointer
coordinate that supplied the bucket is part of the owner observation; an
explicit bucket has no implicit-pointer dependency. These physical coordinates
remain internal and never enter a Workspace payload, refusal, baseline, cursor,
or producer stamp.

The canonical active-bucket pointer transition authority is the existing
active-profile pointer owner, exposed through the public
`cadrumo.application.user_profile` facade and backed solely by the public
`cadrumo.core` pointer IO primitive. Its public transaction owns the canonical
custody-root lock. The facade promotes one frozen native pointer observation and
one capture/current-coordinate pair over that transaction; the core IO
primitive alone serializes and atomically replaces its record. Under the lock,
the observation returns the resolved optional bucket together with the durable
native monotonic transition coordinate from that same record. Clear publishes
an absent-selection tombstone rather than deleting the coordinate. Every
successful state-changing write, restore or clear publishes exactly one
successor coordinate; idempotent no-change operations do not advance it. The
pointer owner alone persists this coordinate as its revision -- it is not a
Workspace or WORK generation.

All production pointer readers and writers migrate atomically to that public
transaction and IO record; there is no dual record reader or legacy mutation
path. Raw mutation outside it, a second pointer lock, and a WORK-owned pointer
counter are forbidden. Thus a completed A -> B -> A remains distinguishable
even when no WORK capture ran between the two pointer transitions or another
process performed them under the same custody-root lock.

An implicit-bucket WORK capture composes two native coordinates rather than
shadowing either owner: the pointer observation and the one-record catalogue
observation for its selected bucket. It captures the pointer under the pointer
owner's custody-root lock, captures that bucket's catalogue and revision, then
re-reads the pointer owner's current coordinate. Equality accepts the pair;
change triggers a bounded retry from the pointer capture, and exhaustion
refuses `workspace_changed`. Its currentness read repeats the same dependency
order and compares both coordinates. The native WORK integer generation is a
pure injective order-preserving composition of the authoritative pointer and
catalogue monotonic integers, so either successor advances it and completed
pointer ABA remains visible without mutable WORK generation state. The opaque
comparison domain binds the physical root, pointer-owner physical identity,
resolved bucket, catalogue namespace and key, and process incarnation. An
explicit bucket capture excludes the pointer coordinate, lock, retry and domain
limb; its native generation is the catalogue generation unchanged.

Concurrent captures of the same accepted coordinate pair singleflight onto the
same result. A catalogue A -> B -> A and an implicit pointer A -> B -> A each
remain visible through their own authoritative monotonic coordinate; a stale
capture can never become current again. Distinct roots have independent
physical domains and their integers are never compared. Neither Workspace nor
WORK persists a generation, hashes payload equality into one, or keeps a
root-global shadow counter.

Registry and work stay separate owners. S128 first performs exactly one native
WORK capture. Exact absence terminates as the declared refusal; natural absence
continues because its filing coordinate is complete. S128 then performs exactly
one S159 registry-native capture from the Modelo, filing year, and period in the
captured work resolution.

S125 carries two fixed, independent typed assertion axes on the resolved target:
`requested_revision_assertion` and `stored_revision_assertion`. Each record has
its fixed source discriminator, an optional asserted revision id and exactly one
of `not_present`, `matched` or `mismatched`; `not_present` requires no id and the
other outcomes require one. The requested axis reflects only the optional
visible-target assertion. The stored axis reflects only the optional revision
persisted on the resolved work unit. Natural absence therefore has a
`not_present` stored axis, an exact target has a `not_present` requested axis,
and a visible persisted target can carry both without collapsing their
evidence. The former single `revision_assertion` field is deleted with no alias
or compatibility reader.

After the S159 capture, one pure application assertion evaluates both axes
independently against the same law-selected revision. A success echoes both
outcomes; any mismatch produces a typed refusal that preserves every evaluated
axis and identifies each mismatching source, including the two-mismatch case.
The assertion never reloads work, calls a raw registry loader, feeds either
asserted revision into selection, or hides an axis in generic facts. Only after
this dependency-ordered WORK-then-REGISTRY pair and both-axis assertion may
S128 capture the remaining admission-specific contributors.

The atomic singleton observation, pure captured-catalogue selection and
consumer convergence, and S159-backed pure revision assertion are prerequisites
to the native WORK surface and therefore to S128 assembly. The native capture,
current-generation reader, and any new public native records are promoted
atomically through the sole `cadrumo.application.modelo` facade with every
consumer update. The old raw-loader assertion path and substitutable scans are
deleted in that cutover. No shim, alias, fallback, non-`__init__` re-export
bridge, private cross-package import, or parallel capture/selector path is
permitted.

### Locale and consistency boundary

Each localized field carries its canonical key plus requested language,
resolved language, and exact resolution disposition. Required Spanish absence
refuses; a non-Spanish miss may use only the canonical Spanish fallback. The
same semantic record has identical identities, values, provenance, and
capabilities in every locale.

`ModeloWorkspaceProjection` is one logical point-in-time read, and the
application owns its complete semantic join. Static inspection captures exactly
`registry`, `work`, `locale_catalogue`, and `field_manifest`; it does not read
bounded review, calculation, readiness, or closure state. Graded snapshot
captures all eight registered contributors. Assembly follows this exact
protocol for the selected admission set:

1. invoke the application-owned WORK registration exactly once; its native
   capture resolves the public visible or exact operand over one atomically
   observed catalogue without a preliminary work read;
2. invoke the REGISTRY registration exactly once from the captured filing
   coordinate, apply both independent revision-assertion axes through the one
   pure assertion operation, then capture each remaining admission-specific
   registration exactly once;
3. assemble only from those captured projections, with no live owner re-read
   hidden inside the join;
4. ask each same registration for its current coordinates; it combines the
   unchanged S126 contract stamp with the canonical owner's native
   current-generation read, and both coordinates must equal the capture; and
5. only after every comparison succeeds, mint one safe opaque
   `ModeloWorkspaceBaseline` over the sorted contributor tuple, resolved
   request coordinate, selected revision, Workspace contract version, complete
   schema-version-2 contributor epoch digest including every comparison domain,
   registry schema identity and fingerprint, locale-catalogue stamp, and field-
   manifest digest.

An unknown or changed epoch or producer stamp causes a bounded whole-assembly
retry and then a typed `workspace_changed` or `consistency_unavailable`
refusal. No baseline is minted before validation, and A -> B -> A invalidates
the capture. Every collection without an authoritative finite bound is
delivered through a typed bounded facet, page, or expansion. Those delivery
shapes carry and revalidate the same sorted contributor tuple, contract
version, schema identity and fingerprint, selected revision, and baseline.
Unpinned pagination and a contributor that cannot atomically return projection
plus ABA-safe epoch are forbidden. The token contains no raw value, secret,
source identity, or reusable authorization.

### Version and conformance gate

The facade accepts exactly Workspace V1. A V1 success or domain refusal echoes
`contract_version = 1`; a version refusal echoes the requested version and the
sole supported version without presenting the rejected payload as V1.
Unsupported versions refuse before target or secure-state resolution.
Conformance proves strict round trips; visible and exact address parity;
ambiguity and revision-assertion refusal; inspection-versus-snapshot
separation; grade and family-disposition parity; locale resolution; schema and
manifest fixed point; schema-identity and fingerprint parity; scalar and
repeated-row coordinates; provenance edges; readiness and closure parity;
complete `ModeloWorkReview` facet fixed-point parity with its sole public
producer; full-versus-faceted baseline consistency; stale and mid-read refusal;
producer-contract/stamp drift; torn-read refusal; and ABA A -> B -> A
invalidation. Readiness fixtures include aggregate `ready = true` with
`per_operation_requirements_assessed = false`, assessed-but-token-partial
requirements, and mixed profile/registry/binding/ledger axes. They prove exact
axis parity and prove that no case becomes `available` from `ready` or
assessment alone without the separately stamped canonical capability verdict.
The suite also covers version refusal, forbidden imports, sensitive-data
non-retention, and the live C2 dependency-receipt validator.

Conformance also proves a one-to-one fixed point between the eight S126
registrations and the eight canonical native owner surfaces; exact contributor
identities and admission-specific capture sets; exactly one native capture per
S126 capture; immutable or snapshot-isolated captured values; unchanged owner
generations and comparison domains; epoch-schema-v2-only decoding; same-domain
comparison; distinct-root, switched-root and cross-incarnation refusal before
integer comparison; comparison-domain participation in contributor epoch
digests, baselines and cursors; and absence of any application-minted,
persisted, reset, or substituted owner generation. Domain, locale, and other
lower-layer modules importing or returning a `ModeloWorkspace*` type fail the
boundary gate.

WORK conformance additionally proves one-record catalogue/revision atomicity;
visible absence and exact-absence asymmetry; discarded-only resolution; mixed
and multiple ambiguity; active-only lifecycle exclusion; one pure selector over
the captured catalogue; physical-root/bucket/namespace isolation; pointer-owner
atomic observation and mutation under the canonical custody-root lock;
between-WORK-observations implicit pointer A -> B -> A; catalogue A -> B -> A;
implicit pointer/catalogue retry and currentness; explicit-bucket pointer
exclusion; same-observation singleflight; currentness refusal; distinct-root
independence; exactly one WORK capture before the S159 REGISTRY capture; natural
absence with a `not_present` stored axis and both requested-axis presence cases;
visible work with both axes; exact work with only the stored axis;
requested-only, stored-only and simultaneous mismatch refusals; and no raw
loader, generic-fact assertion, or second owner read.

### C2 complex-read gate and external prerequisites

Existing bounded `ModeloWorkReview` and backend campaigns may continue. The C2
complex-read cohort remains blocked until all of these receipts exist:

1. this ADR is accepted and Workspace V1 is exported from the public
   application facade;
2. for a TUI consumer, `2026-08-24-tui-modelo-workspace-interface-adr` is
   accepted and its `ModeloWorkspaceC1ExitReceiptV1` at
   `.vault/reference/2026-08-24-tui-modelo-workspace-interface-c1-exit-receipt.md`
   is green; that record retains ownership of destinations, view models,
   bounded rendering, and visual conformance;
3. the authority-grade decision is accepted or formally reconciled and both
   admission paths use its public contracts;
4. canonical readiness and closure producers are public and their Workspace
   parity tests are green, although individual revisions may still carry
   evidence-backed refusals;
5. the generated current-HEAD field-classification manifest has zero
   unclassified paths and its digest is recorded;
6. every canonical owner publishes its native atomic capture surface, every
   application registration publishes a current stamped producer contract, and
   the native-surface/S126 one-to-one fixed point is green;
7. the complete V1 conformance suite above is green; and
8. the machine-readable
   `.vault/reference/2026-08-24-tui-registry-api-gate-c2-dependency-receipt.md`
   validates as `ModeloWorkspaceC2DependencyReceiptV1` under
   `validate_modelo_workspace_c2_dependency_receipt` on current HEAD.

`ModeloWorkspaceC2DependencyReceiptV1.predecessors` is the closed, ordered
`ModeloWorkspaceC2PredecessorTupleV1`:

1. this accepted ADR's stem, accepted commit, and body hash;
2. the accepted `2026-08-24-tui-modelo-workspace-interface-adr` stem, accepted
   commit, and body hash;
3. the `ModeloWorkspaceC1ExitReceiptV1` path above, producing commit, and
   artifact digest;
4. the accepted or formally reconciled authority-grade decision stem,
   disposition, commit, body hash, and reconciliation-artifact digest when
   reconciliation was required; and
5. the native-owner surface inventory and seam-conformance digest plus the
   `ModeloWorkspaceProducerContractInventoryV1` schema version, producing
   commit, and artifact digest.

The C2 receipt additionally records the sorted native-owner surfaces, producer
contracts and stamps, captured epoch tuple/digest, process-incarnation refusal
proof, Workspace version and schema fingerprint, generated field-manifest
digest, baseline and locale proofs, source ancestry, and exact complex-read
routes opened. Its validator rejects an absent or reordered
predecessor, a proposed/unapproved decision, a non-ancestor producing commit,
artifact or body-hash drift, missing or mismatched producer stamps, epoch-
protocol drift, a non-green C1 receipt, or a route outside C2. Mocks, prose
attestations, and a receipt produced from a different tree cannot open the gate.

C2 authorizes only complex read-only workspace consumers. It does not create
`modelo.edit`, authorize a command, enroll an operation, or open verify, file,
export, amendment, lifecycle, secret, or recovery interactions. Public
operation observation is external to this record through
`2026-08-24-tui-operation-observation-adr`. Workspace/editor information
architecture and every write-side contract are external through
`2026-08-24-tui-modelo-workspace-interface-adr`. Acceptance of its read-side
contract gates TUI C2; its edit implementation receipts and the operation
observation amendment gate their respective later cohorts. None is inferred
from Workspace V1.

## Rationale

The application layer is the only layer permitted to join law-selected registry
authority, secure work state, calculation materialization, readiness, closure,
and localization without reversing dependencies. An explicit inspection versus
snapshot discriminator prevents advisory schema visibility from becoming a
false authority claim. A generated field denominator makes projection coverage
explicit and fixed-point checked, while baseline-pinned facets preserve one
logical read at realistic scale without requiring eager materialization of the
entire graph.

Keeping operation observation and editing outside this record preserves their
accepted or still-missing owners. It also gives C2 a falsifiable endpoint:
complex readers can proceed once one read contract is public and proven, without
silently treating operation or editor design as complete. This is the narrow
choice supported by `2026-08-24-tui-registry-api-gate-research` and
`2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit`.

## Consequences

- Complex read-only Modelo surfaces gain one stable contract for schema,
  values, rows, lineage, readiness, closure, locale, and typed refusal.
- Static inspection remains visibly weaker than a grade-admitted snapshot; no
  downgrade can look like successful calculation or filing authority.
- Registry evolution creates a generated classification obligation for every
  new field, while backend-only grammar remains private.
- Large workspaces may be read through typed baseline-pinned facets without
  mixed registry, work, calculation, readiness, closure, or locale epochs.
- Work reads retain discarded terminal state and natural absence without
  widening creation semantics, while persistence revision and active-pointer
  transitions make torn or ABA work captures observable. The pointer owner,
  not WORK or Workspace, remains the transition-counter authority.
- Safe epoch comparison is confined to one opaque physical-scope and process-
  incarnation domain; baselines and cursors cannot accidentally compare equal
  integers from distinct roots or processes.
- Requested-target and stored-work revision evidence remain independently
  inspectable on success and refusal, including absent work and simultaneous
  mismatch, without widening either assertion into selection authority.
- `ModeloWorkReview` remains the canonical bounded C1 record and appears
  unchanged as the Workspace review facet; Workspace V1 neither expands it nor
  duplicates its semantic join.
- Registry incompleteness remains visible as owner-backed refused or unmeasured
  capability data; it does not destabilize the contract or become synthetic
  readiness.
- Operation observation, editing, persistence, and visual architecture remain
  blocked on their own accepted decisions and receipts.
- C2 can close as a read milestone without operation or editor implementation,
  once its external interface decision and read receipts pass. Later cohorts
  cannot cite this ADR as mutation, operation, secret-custody, or editor
  authority.

## Amendment 2026-08-26: `field_manifest_digest` is exclusively the S278 field-classification digest

`ModeloWorkspaceSchemaIdentityV1.field_manifest_digest` names ONE concept: the
S278 field-classification manifest digest this record's static-inspection and
graded-snapshot generators produce (`ModeloWorkspaceFieldManifestPortV1`,
`resolve_static_inspection_schema_identity`) — a deterministic walk over the
public registry TYPE denominator for display rendering. It is never a
digest of `CalculationCompletenessManifest` (the registry's required
calculation-closure casilla set, a tax-semantic concept this ADR does not
own) or any other manifest a future consumer might be tempted to store under
the same field name because the shape happens to fit. `2026-08-24-modelo-edit-contract-adr`
is amended in the same change: its baseline's schema identity is now its own
type, `ModeloEditSchemaIdentityV1`, carrying `completeness_manifest_digest`
rather than reusing this field. The Workspace producer's own construction-site
docstring had already flagged the exact collision this amendment closes.

## Amendment (S291): a period-level ledger-preflight issue is a distinct subject, never a fabricated transaction

`LedgerPreflightIssue.transaction_id` (`application/ledger/preflight.py:120`)
is `TransactionId | Literal["__period__"]`: exactly one issue kind
(`_unsupported_period_issue`, fired when the period has no date span) is
scoped to the whole period rather than one transaction. The prior
`ModeloWorkspaceLedgerIssueV1.transaction_id: TransactionId` had no
representable arm for that case. Dropping the issue would be a silent
under-declaration on exactly the axis an operator consults before filing;
pinning it to a fabricated transaction id would point the operator at a
transaction that has nothing to do with the problem. Neither is acceptable.

`ModeloWorkspaceLedgerIssueV1.transaction_id` is replaced with `subject:
ModeloWorkspaceLedgerIssueSubjectV1`, a discriminated union of
`ModeloWorkspaceLedgerTransactionSubjectV1` (`kind="transaction"`, carrying
`transaction_id`) and `ModeloWorkspaceLedgerPeriodSubjectV1`
(`kind="period"`, carrying nothing else). This is the same shape as S284's
`ModeloWorkspaceRecordLabelV1`: a field whose type previously could not
express a real closed-domain alternative now can, and neither silent drop
nor fabricated identity is representable any longer.

## Amendment (S290): a provenance record's subject is carried, not derived, and comes from a domain gap now closed

`ModeloWorkspaceProvenanceRecordV1.subject` requires a casilla or binding
identity a trace explains; `CalculationSourceRef` (the persisted domain
lineage row) carried only resolver identity, resolved binding source,
source-object reference and fingerprint, with no field naming the subject
and no shared key to any other persisted structure to join on. Verified
before ruling: `CasillaObservation.source_refs` is a different namespace
(legal-catalogue `SourceRefId`s, not resolver-mesh source refs);
`operand_refs`/`operand_casilla_refs` are formula-tree lineage, not
resolver-mesh source lineage; `row_casilla_provenance` covers only
row-materialized casillas. No recoverable join exists.

That verification also surfaced that the omission is not the documented
design choice it first appeared to be. `CalculationSourceRef`'s docstring
states it deliberately drops `legal_refs`/`source_refs` to avoid duplicating
per-casilla regulatory grounding already carried by `CasillaObservation` on
the same revision. It says nothing about a subject identity, and the
anti-duplication rationale does not extend to one: a subject identity is not
grounding, and carrying it duplicates nothing already on the revision. The
application-side `CalculationSourceProvenance` (the pre-persistence row) had
already carried `source_casilla_ids` all along; the domain-side persisted
projection simply never carried it across the boundary.

`CalculationSourceRef` gains `source_casilla_ids: tuple[CasillaId, ...] = ()`,
passed straight through at the `_source_provenance_refs`
application-to-domain boundary (`application/modelo/_calculation_actions.py`)
from the `CalculationSourceProvenance` row already holding it, and folded
into the content-addressed revision id derivation
(`_source_provenance_revision_id_payload`) so a save-drops-field regression
on it is not invisible. An empty tuple is honest, not fabricated: it means
the originating resolver call site did not associate this row with a
casilla, which is common today (verified: `_modelo_bindings.py`'s ledger IVA
aggregation provenance never populates the field). Backfilling every
resolver call site to populate it is explicitly OUT of this amendment's
scope; a resolver that never links a casilla simply produces no provenance
record for that source until it does.

`ModeloWorkspaceProvenanceRecordV1.subject` is unchanged in type
(`ModeloWorkspaceSchemaReferenceV1`, already a discriminated union including
`ModeloWorkspaceCasillaReferenceV1`) — no new Workspace type was needed.
`graded_snapshot_provenance_facet` fans one `CalculationSourceRef` out into
one record per casilla in its `source_casilla_ids`; a ref with an empty
tuple produces zero records rather than a record with a fabricated or
inferred subject.
