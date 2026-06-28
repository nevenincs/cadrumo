---
tags:
  - '#research'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-branch-reconciliation-audit]]"
---



# `registry-casilla-identity` research: segment-scoped casilla identity for multi-segment AEAT modelos

Research into the registry casilla-identity model and whether it can
represent AEAT forms that reuse the same five-digit casilla number across
distinct record segments. Triggered by the Modelo 200 cuota-chain finding
recorded in the branch-reconciliation audit: the registry silently carries
a missing-data hole where M200 Liquidacion cuota casillas should be, and
snapshot-build validation passes green. This research grounds the ADR that
must settle a segment-scoped casilla identity and a Diseno-completeness
validator gate.

## Findings

### Current-state analysis

#### F1. The casilla identity model collapses `id` onto the bare number

`CasillaDefinition` in `src/aeat/domain/calculations/registry/_schema.py`
(class at line 1470) declares two separate fields: `id: CasillaId`
(line 1471) and `number: str` (line 1472).

`CasillaId` is defined in `src/aeat/.../registry/_ids.py` line 16 as
`Annotated[str, Field(min_length=1, max_length=64, pattern=_CASILLA_RE)]`
where `_CASILLA_RE` is the regex permitting alphanumerics plus dot,
underscore, colon and dash (line 12). The schema places no constraint
linking `id` to `number`; `number` is an unconstrained `str` with no
pattern, length bound, or relationship to `id`. There is no `_validate`
rule on `CasillaDefinition` linking the two: the `_validate_input_kind`
model-validator at line 1495 checks only `input_kind` / `formula` /
`binding` coherence and `semantic_role` cardinality.

In practice every authored fragment sets `id == number` as the bare
five-digit string. Evidence from the M200 corpus: the fragment
`casillas/0001-liquidacion-cuota-liquida.toml` declares `id = "00592"`
and `number = "00592"`; the ECPN fragment `casillas/0156-estado-de-
cambios-patrimonio-neto-ii-...toml` declares `id = "00562"` and
`number = "00562"`. The convention is universal across the 1004 M200
casilla fragments and across the other modelos. `id` is therefore not an
independent stable key; it is a redundant copy of `number`, and the
registry has no surface on which a casilla number could recur under two
distinct identities.

`CasillaId` is the single typed alias used everywhere a casilla is
referenced: `FormulaExpression.casilla`, `FormulaDefinition.target`,
`DataBindingDefinition`, `ExportFieldDefinition.casilla`,
`ExportRecordDefinition.row_field_casillas` and
`requires_positive_casilla`, `RelationDefinition.source_output`,
`AlgorithmBindingDefinition.target` / `inputs` / `outputs`,
`VerificationExpectationDefinition.computed_casillas` and
`reconciliation_totals`, `ExtractionProfileDefinition.target_casillas`.
Because every reference site uses `CasillaId` and every casilla sets
`id == number`, the bare number is the de-facto join key across the
entire registry graph.

#### F2. Duplicate-id rejection: the registry refuses two casillas with the same `id`

Casillas load from per-modelo TOML through the loader in
`src/aeat/domain/calculations/registry/_loader.py`. Directory-mode
modelos (M200 included) use the fragment layout from the
fragment-architecture ADR: `manifest.toml` plus `revisions/<id>/`
fragment trees merged by `_merge_revision_fragment` (`_loader.py` line
281). The merge appends array record kinds, including `casillas`, in
deterministic path order (`_merge_revision_fragment_field`, line 305);
it performs no deduplication. All casilla fragments for a revision
concatenate into a single `casillas` tuple on `ModeloRevision`
(`_schema.py` line 1765).

Uniqueness is enforced downstream by `RegistryValidator` in
`src/aeat/domain/calculations/registry/_validate.py`. The per-kind
duplicate check is table-driven: `_RECORD_ID_KINDS` (line 92) lists the
casilla kind; `_collect_record_id_lists` (line 122) gathers the
`record.id` of every casilla; `_emit_per_kind_duplicate_failures`
(line 127) appends a duplicate-casilla-id failure for every repeated
`id`. A second cross-kind check, `_emit_combined_primary_id_failures`
(line 145), additionally forbids a casilla `id` from colliding with a
formula, binding, or relation id. Both run at modelo validation
(`_validate_revision`).

Critically, the duplicate check keys on `id`, not on `number`. Because
authors set `id == number`, the check effectively forbids duplicate
numbers, but only because the convention makes `id` and `number`
identical. There is no check on `number` itself. The dict comprehension
`casilla_by_id` built from `casilla.id` at `_validate.py` line 397, and
the snapshot and runtime equivalents (`_authority.py` builds
`_modelos_by_id`; `_queries.py` line 205 emits `casilla_id` from
`casilla.id`), would silently keep the last occurrence on a true `id`
collision, but the validator fires first and turns the collision into a
hard `RegistryValidationError`, so a duplicate `id` never reaches the
snapshot.

The cross-revision validator
`_validate_cross_revision_casilla_consistency` (`_validate.py` line
2983) treats a repeated casilla `id` across revisions of one modelo as a
deliberate stable concept and enforces a fingerprint
(`_CROSS_REVISION_CASILLA_FIELDS` line 2932: label, section, data_type,
semantic_role, legal_refs). This confirms the schema intent: `id` is a
single global concept identity, deliberately stable across revisions.
That intent is exactly what breaks for a form where the same number is
two different concepts within one revision.

#### F3. The Modelo 200 defect is a missing-data hole, not a duplicate-id error

The audit reported that M200 Liquidacion cuota-chain casillas were
silently dropped. The mechanism is subtler and more dangerous than a
silent dict overwrite: because the validator hard-rejects a duplicate
`id`, the registry author could not declare both the ECPN `00562` and
the Liquidacion `00562`. Faced with that, the corpus contains only the
ECPN occurrence and the Liquidacion occurrence was never authored at
all.

Verified directly: a search for `id = "00562"` across the 1004 M200
casilla fragments returns exactly one file, the
`0156-...operaciones-con-socios-o-propietarios.toml` ECPN fragment,
whose label is an ECPN operaciones-con-socios field, section
`estado_de_cambios_patrimonio_neto_ii`, semantic_role
`is_ecpn_operaciones_socios_importe`. The same holds for `00558`,
`00552`, `00611`: each appears exactly once, each is an ECPN-segment
casilla. The Liquidacion cuota integra, tipo de gravamen, base
imponible, and cuota diferencial casillas are absent from the registry.

The snapshot-build validators cannot catch this. Every validator in
`_validate.py` checks referential closure and consistency of what is
declared: duplicate ids (lines 127, 145), unknown formula and binding
targets (lines 570, 581), legal and source-ref closure (lines 565,
568), semantic-role consistency (line 2503), required-role label-pattern
coverage (line 2872). None checks completeness against the AEAT Diseno
de Registros, that the set of declared casillas matches the set the
official form actually contains. A casilla that was never authored is
invisible. M200 therefore loads green while missing filing-grade
calculation casillas.

The blast radius is contained. The
`modelo-200-cuota-ejercicio-a-ingresar-devolver` formula
(`records/formulas.toml` line 2) targets `00599` and reads casilla
`00592` (cuota liquida, a Liquidacion casilla that is correctly
registered) minus the pagos-fraccionados relation; that formula is
sound. The five mis-segmented numbers are referenced only by M200
export page-bindings: e.g. `export/0017-modelo-200-page-014.toml` line
607 declares export field `modelo-200-page-014-casilla-00562` with
casilla `00562`, which currently resolves to the ECPN casilla and will
need re-pointing once the Liquidacion casillas are registered. No
formula, cross-modelo relation, binding, or aggregation depends on the
dropped casillas.

#### F4. Where a casilla is referenced by bare number, the blast radius of an identity change

Every casilla reference in the registry graph is the bare-number string,
typed as `CasillaId`. An identity-model change touches every site:

- Formula expressions: `FormulaExpression.casilla` (`_schema.py` line
  1162), authored as a casilla leaf in `formulas.toml`;
  `expression_casilla_refs` (`_runtime_graph.py` line 10) walks these
  for dependency ordering.
- Formula targets: `FormulaDefinition.target` typed `CasillaId`
  (`_schema.py` line 1348), validated against the casilla set at
  `_validate.py` line 623.
- Export field bindings: `ExportFieldDefinition.casilla` (`_schema.py`
  line 1599); the M200 page-bindings (78 export TOML files) all key on
  bare number; validated at `_validate.py` line 1073 and the
  bidirectional `export_refs` cross-check at line 1076 against
  `CasillaDefinition.export_refs` (`_schema.py` line 1485).
- Export record row fields: `ExportRecordDefinition.row_field_casillas`
  and `requires_positive_casilla` (`_schema.py` lines 1658, 1660).
- Bindings: `DataBindingDefinition` (`_schema.py` line 1313); a
  `source_casillas` selector tuple is read at `_validate.py` line 1485.
- Relations: `RelationDefinition.source_output` typed `CasillaId`
  (`_schema.py` line 1558), cross-modelo output references.
- Algorithm bindings: `AlgorithmBindingDefinition.target`, `inputs`,
  `outputs` (`_schema.py` lines 1538-1540).
- Verification expectations: `computed_casillas` and
  `reconciliation_totals` (validated `_validate.py` lines 1183-1192,
  2281-2283).
- Extraction profiles: `target_casillas` (validated `_validate.py`
  lines 1105, 2257).
- Cross-domain routing: `first_slice_target_casillas` for the M100 renta
  routing table, validated against the snapshot casilla ids at
  `_validate.py` line 2413.
- Runtime and query surface: `_authority.py` builds `_modelos_by_id`;
  `_queries.py` lines 205-206 emit both `casilla_id` and `number` on
  observation rows; `CasillaObservation` and the engine value map key on
  casilla identity per the calculation-grounding rule.

The decisive observation: all of these are single-segment today. Across
the registry only M200 has the multi-segment problem (M202 was a false
alarm; pago fraccionado legitimately has no accounting-statement
casillas; M303 number reuse lives in the fichero-BOE record layout, not
the casilla registry). So the blast radius of a correct identity change
is the M200 corpus, plus any modelo that later acquires multi-segment
casilla data (M220 and the multi-segment fichero-BOE forms).
Single-segment modelos, the overwhelming majority, must be able to stay
on the bare-number form or migrate trivially.

#### F5. Constraints set by the three accepted ADRs

- Schema-hardening ADR (`2026-05-18`, accepted). Registry validation is
  a hard error at snapshot build, never an audit-only or transitional
  warning; the ADR explicitly rejects the validating-but-not-enforcing
  middle state as the very drift pattern it exists to eliminate. New
  casilla fields use the richest applicable typed `data_type` (no text
  fallback); `CasillaConstraints` carry pattern, min_length, max_length,
  and enum where the legal contract specifies a shape. It introduced
  `semantic_role` as an optional per-casilla slot with a snapshot-build
  consistency validator. Any identity-model change must follow the same
  discipline: strict pydantic, additive where possible, hard-error
  validator at the load surface. The ADR notes cross-revision casilla
  deprecation tracking is orthogonal to the atom layer and remains an
  open issue; segment identity is a sibling open issue in the same
  family.
- Spanish-stem terminology ADR (`2026-05-19`, accepted). Tax-domain
  identifiers use canonical Spanish stems; `modelo` is always followed
  by the three-digit modelo number. International identifiers (NIF,
  IBAN, BIC) stay English; infrastructure suffixes compose onto stems. A
  new `segmento` or `registro` field name and any segment-identifier
  values must use Spanish-stem vocabulary; the AEAT Diseno term is
  `registro` (diseno de registro), and the segment tags are AEAT own
  `DP200xxx` codes. A field named `segmento` or `registro` is
  ADR-conformant; `segment` as a bare English noun is borderline and
  should be weighed against the glossary.
- Fragment-architecture ADR (`2026-05-19`, accepted). The registry
  authoring layout is per-record-kind fragment trees; the runtime models
  `ModeloDefinition`, `ModeloRevision`, `RegistryCatalogues`, and
  `RegistrySnapshot` must stay stable; final pydantic validation and
  existing registry validation remain the authority for id uniqueness
  and reference closure. The loader merges fragments with no
  deduplication, so the identity model is the only thing preventing two
  same-number casillas, and the fragment layout makes adding the missing
  M200 casillas a matter of authoring new per-casilla fragment files,
  not editing a monolith. The ADR also requires cache fingerprints to
  cover every TOML read.

#### F6. The AEAT Diseno de Registros structure, the segment identifier is a natural disambiguator

The M200 Diseno de Registros corpus lives under
`src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_200/files/`
as xls and xlsx workbooks plus PDF variants, indexed by a manifest
JSON. AEAT publishes the M200 record design as a multi-sheet workbook:
each sheet is one record segment (`DP200010` ECPN, `DP200014`
Liquidacion, `DP200032` Banco de Espana, `DP200042` aseguradoras,
`DP200DID`, and others), and within a sheet the casilla appears as a
five-digit bracketed tag in the field description. The codebase already
parses this structure: `_record_design.py` extracts each workbook sheet
into a `RecordDesignSheet` (sheet name plus ordered `RecordDesignField`
rows, class at line 49); `extract_record_design_xls_workbook` (line
110) iterates the workbook sheet names. The `RecordDiscriminator` model
(`_schema.py` line 1633) already exists precisely because AEAT models
several Tipo-2 record sub-shapes that share literal prefixes; the
registry already acknowledges record-segment multiplicity on the export
side.

The segment identifier (the `DPxxxxxx` code, or its sheet name) is
therefore a first-class, AEAT-authoritative disambiguator already
present in the source corpus. A casilla true identity in the AEAT form
is the pair (record-segment, number), not number alone. The registry
`id == number` model discards the segment dimension that the official
source carries explicitly.

One structural subtlety the ADR must handle precisely: the M200 export
TOML files are named `modelo-200-page-NNN` and `modelo-200-did`; these
are declaration pages of the PDF form, distinct from the fichero-BOE DR
segments. The casilla `export_refs` already enumerate page-level
positions (casilla `00552` carries page-010, page-014, and did export
refs). The ADR must scope identity to the fichero-BOE record segment
(`DPxxxxxx`), the axis on which a number genuinely means two different
things, not to the PDF page, which is a layout coordinate, not a
semantic segment.

### Option evaluation, sub-decision A: segment-scoped casilla identity

#### A1. Composite id equals segment plus number (form DP200014 colon 00562)

The `id` becomes a compound string; `number` stays the bare five-digit
value. The duplicate-id validator (`_validate.py` line 127) keeps
working unchanged because the two composite ids are distinct. The
`CasillaId` regex already permits the colon separator so no pattern
change is needed.

- Migration cost: high and broad. Every reference site in F4, formula
  target and casilla leaf, export casilla, relation source_output, and
  every casilla tuple, must switch from the bare number to the composite
  form. For single-segment modelos the composite is a segment prefix on
  every casilla, so even M100, M303, and M111 would have to rewrite
  every reference, or accept an inconsistent corpus where some modelos
  use bare numbers and others use composites.
- Single-segment simplicity: lost. The majority of modelos pay the
  composite-id tax for a problem only M200 and M220 have, unless the
  schema permits a bare id to coexist with composite ids, which
  reintroduces ambiguity.
- ADR conformance: the hard-error validator survives. A DP-prefixed
  segment code is AEAT own vocabulary so the Spanish-stem rule is
  satisfied. Fragment layout unaffected.
- Verdict: correct but disproportionately costly; punishes the 25
  single-segment modelos to fix one.

#### A2. Keep number, add a segmento or registro field, make the pair segmento-plus-number the uniqueness key

The `CasillaDefinition` keeps `id` and `number` but gains an optional
`segmento` string field (Spanish-stem; the AEAT DR term is registro). A
new model-validator and a registry-level uniqueness check enforce that
the pair of segmento and number is unique per revision rather than `id`
alone. For single-segment modelos `segmento` is unset and nothing
changes. For M200, the Liquidacion and ECPN 00562 casillas carry the
same number but distinct segmento values and both become declarable.

The open question this option must resolve is what `id` is once it is no
longer equal to number. Two coherent sub-shapes:

- A2a: the `id` becomes the composite, auto-derived or authored, and
  reference sites that need to disambiguate use it; bare-number
  references resolve only when unambiguous. This is A1 in disguise for
  the reference sites.
- A2b: the `id` stays the bare number for single-segment modelos and the
  reference resolver becomes segment-aware: a bare-number reference
  inside a formula or export scoped to a known segment resolves within
  that segment. Formulas and export records already have segment
  context, an export record is a segment, and a formula target casilla
  fixes a segment. This keeps single-segment modelos completely
  untouched and confines composite identifiers to the genuinely
  ambiguous M200 sites.

- Migration cost: A2b is the lowest of all options for single-segment
  modelos, zero changes, segmento defaults to unset. M200 pays the cost:
  add segmento to its 1004 fragments (mechanical, one value per fragment
  derivable from the DR sheet the casilla came from) and author the
  missing Liquidacion casillas. Reference-site cost is confined to M200
  export bindings, which already carry page context.
- Single-segment simplicity: preserved under A2b. The field is optional;
  the validator uniqueness key degrades to number alone when segmento is
  unset.
- ADR conformance: a hard-error segmento-plus-number validator fits the
  schema-hardening discipline exactly, it generalises the existing
  duplicate-id check. Additive optional field, existing TOMLs validate
  unchanged. Spanish-stem: segmento or registro is the conformant field
  name. Fragment layout: a new optional scalar on a record kind, fully
  supported.
- Verdict: strongest. It models the real AEAT structure, the pair of
  registro and casilla, keeps the 25 single-segment modelos at zero
  cost, and the uniqueness validator is a natural generalisation of code
  that already exists.

#### A3. Stable semantic slug as id (form liquidacion-cuota-integra)

The `id` becomes a human-authored slug independent of number; number
stays as the AEAT display number. Two M200 00562 casillas get distinct
slugs. The casilla fragment filenames already follow this pattern so the
vocabulary exists.

- Migration cost: highest. Every reference site must move from the bare
  number to a slug, and slugs are author-chosen, so the change is not
  mechanical; it needs a slug assigned to all roughly 12,500 casillas
  corpus-wide and every formula, export, relation, and binding
  rewritten.
- Single-segment simplicity: lost, even trivial single-segment modelos
  get a slug indirection over a number that was a perfectly good key.
- ADR conformance: the slug overlaps conceptually with `semantic_role`
  from the schema-hardening ADR, two parallel semantic-naming surfaces
  would invite drift. Slugs are Spanish so stem-conformant, but the
  duplication with semantic_role is an architecture smell.
- Upside: a slug is genuinely stable across AEAT renumbering years, rare
  but real. That benefit does not outweigh the corpus-wide rewrite and
  the semantic_role overlap.
- Verdict: over-reaches. Solves a renumbering problem nobody has filed,
  at the cost of the largest migration, and competes with
  semantic_role.

### Option evaluation, sub-decision B: Diseno-completeness validator gate

The defect in F3 is that a never-authored casilla is invisible. No
identity-model change fixes that; A1, A2, and A3 only make the missing
casilla declarable, not required. B is independently necessary. The gate
must answer: does the set of casillas declared for this revision match
the set the AEAT Diseno de Registros actually contains?

#### B1. Expected-set expressed as registry data, a per-segment expected-casilla manifest

Author, per modelo-revision, a small TOML stanza listing the expected
casilla numbers per segment, derived once from the official DR. The
validator compares declared segmento-plus-number pairs against the
manifest and hard-errors on any missing or extra pair.

- Pro: explicit, reviewable, version-controlled; lives beside the
  casilla fragments under the fragment layout; no PDF or XLS parsing at
  load time.
- Con: the manifest is hand-authored and can itself drift from the real
  DR; it is a second surface to maintain. Mitigated by deriving it
  mechanically from `_record_design.py` extraction at authoring time and
  treating the manifest as a checked-in snapshot.

#### B2. Expected-set extracted live from the Diseno corpus at snapshot build

The validator calls the `_record_design.py` extraction against the
modelo DR workbook or PDF, collects the casilla tags per sheet, and
compares to the declared casillas.

- Pro: no hand-authored manifest; the AEAT source is the oracle, zero
  drift between gate and authority.
- Con: couples snapshot build to PDF and XLS parsing (pdfplumber, xlrd,
  openpyxl, pypdfium2), heavy, slow, and the ten PDF-only Disenos were
  noted as not machine-verified. The cache-fingerprint contract of the
  fragment-architecture ADR would have to extend to DR corpus files.
  Snapshot build is a hot path; parsing a 10 MB workbook on every load
  is unacceptable.

#### B3. Hybrid, an extraction-derived manifest re-verified on a separate audit cadence

Author the B1 manifest by running the B2 extraction once (a build-time
or audit-time tool), check the manifest into the registry, and have the
snapshot-build gate use the cheap manifest (B1). A separate,
non-load-path audit test re-runs the B2 extraction and asserts the
manifest still matches the corpus, so manifest drift is caught by CI,
not by every load.

- Verdict: best. Snapshot build stays fast and pure-data via B1; the
  manifest cannot silently drift because the audit test re-derives it;
  the ten PDF-only Disenos degrade gracefully, they get a manifest
  authored from a manual read, flagged with an explicit
  manual-extraction marker, and the audit test skips the machine
  re-derivation for them with a recorded reason rather than a silent
  gap.

#### Where the gate runs

The completeness check belongs in `RegistryValidator` alongside the
existing per-revision validators in `_validate.py`, the same surface as
`_emit_per_kind_duplicate_failures` and the semantic-role validators, so
it inherits the hard-error-at-snapshot-build discipline the
schema-hardening ADR mandates. It runs per `ModeloRevision`, keyed by
the pair of modelo id and revision id, against that revision
expected-casilla manifest. A revision with no manifest yet should fail
closed, with an explicit no-manifest-declared error, rather than pass
green; otherwise the gate is opt-in and the M200 class of bug recurs for
the next un-manifested modelo.

## Recommendation

### A: adopt A2b, keep number, add an optional segmento field, make segmento-plus-number the uniqueness key

The `CasillaDefinition` gains an optional `segmento` string field, unset
by default. The final field name is to be confirmed against the
Spanish-tax glossary: registro is the literal AEAT DR term, segmento
reads more naturally as the disambiguator, either is ADR-conformant, and
segment as a bare English noun is not. The registry uniqueness check
generalises from id-unique to segmento-plus-number-unique per revision,
degrading to number-unique when segmento is unset. The `id` stays the
bare number for single-segment modelos; for multi-segment modelos `id`
is the composite of segmento and number, or is dropped in favour of the
segmento-plus-number pair as the sole key. The ADR should decide whether
`id` survives at all, given that F1 shows it is currently pure
redundancy. Reference resolution becomes segment-aware: a formula or
export record already fixes a segment context, so a bare-number
reference resolves within it; only genuinely cross-segment references
need the composite.

Rationale: A2b is the only option that, first, models the real AEAT
structure, a casilla identity in the official Diseno is the pair of
registro and numero; second, keeps all 25 single-segment modelos at
literally zero migration cost via the optional-field default; third,
generalises the existing duplicate-id validator rather than replacing
it, preserving the schema-hardening hard-error discipline; fourth, is
purely additive, so every existing TOML still validates. A1 and A3 both
impose a corpus-wide rewrite on modelos that have no segment problem; A3
additionally collides with semantic_role.

Migration impact: confined to M200 and to future M220 and multi-segment
fichero-BOE forms. For M200, add segmento to the 1004 existing casilla
fragments, which is mechanical because the value is the DR sheet each
casilla belongs to and is recoverable from `_record_design.py`
extraction; author the missing Liquidacion cuota-chain casillas, cuota
integra 00562, tipo de gravamen 00558, base imponible 00552, cuota
diferencial 00611, and 00621, as new fragments under the M200 casillas
directory with segmento set to DP200014; re-point the M200 page-014
export bindings, currently resolving 00562 to the ECPN casilla, to the
Liquidacion casilla. Per the calculation-grounding rule every restored
casilla carries its legal_refs and source_refs triple; per the
no-tautological-tests rule the restored cuota formulas derive expected
values from AEAT workbooks or BOE worked examples, never hand-computed
from the formula under test. A strict roundtrip test for the extended
`CasillaDefinition` and an anti-tautology proof, mutate a fragment to
drop segmento and assert the uniqueness gate or a segmento-plus-number
collision surfaces, follow the roundtrip-discipline rule.

### B: adopt B3, an extraction-derived checked-in Diseno-completeness manifest, gated at snapshot build and re-verified on a separate audit cadence

Express the expected casilla set as registry data, a per-modelo-revision
manifest listing expected segmento-plus-number pairs, derived once by
running `_record_design.py` extraction against the official Diseno
corpus and checked into the fragment tree. Add a completeness validator
to `RegistryValidator` in `_validate.py` that hard-errors at snapshot
build on any missing or extra casilla relative to the manifest, keyed
per the pair of modelo id and revision id. A revision with no manifest
fails closed. A separate audit-cadence test, not on the load path,
re-runs the extraction and asserts the manifest still matches the
corpus, so the manifest cannot drift silently; PDF-only Disenos that
resist machine extraction carry an explicit manual-extraction marker
with a recorded reason rather than a silent skip.

Rationale: the M200 defect is a missing-data hole, an identity-model
change alone makes the missing casilla declarable but never required. B
is independently necessary. B3 keeps snapshot build fast and pure-data,
no PDF parsing on the hot path, eliminates manifest drift via the audit
re-derivation, and degrades gracefully for the ten PDF-only Disenos.
Placing the gate in `RegistryValidator` inherits the schema-hardening
ADR hard-error-at-load discipline; fail-closed on a missing manifest
prevents the gate from being silently opt-in, the exact failure mode
that let M200 load green.

Migration impact: author a completeness manifest for every modelo
already carrying casilla data, M036, 100, 111, 115, 123, 130, 131, 200,
232, 353, 369 and others, derived mechanically from the DR corpus. The
M200 manifest will, on first run, immediately fail the new gate,
surfacing the missing Liquidacion casillas as a hard error and forcing
the A2b restoration. Modelos with no casilla data yet, 220, 303, 347,
349, 390, 190, 193, 720, acquire their manifest when their casillas are
first authored; until then the fail-closed rule means they cannot have a
casilla-bearing revision load without a manifest, which is the desired
pressure.

### Sequencing

A and B are complementary and must land together: A2b makes the missing
M200 casillas declarable; B makes them required. Recommended order
within the ADR plan: land the A2b schema change and its validator first,
additive, no corpus breakage, then the B3 manifest plus gate, which once
the M200 manifest is authored hard-fails until the A2b restoration of
the Liquidacion casillas is complete. This makes the M200 fix
self-enforcing: the gate stays red until the cuota-chain casillas are
correctly registered under segmento DP200014.
