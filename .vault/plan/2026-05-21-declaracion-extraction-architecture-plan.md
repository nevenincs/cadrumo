---
tags:
  - '#plan'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
tier: L3
related:
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
  - '[[2026-05-21-declaracion-extraction-architecture-research]]'
  - '[[2026-05-20-branch-reconciliation-audit]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `declaracion-extraction-architecture` umbrella plan

## Wave `W01` - discovery sweep

Discovery Wave. Haiku and sonnet sub-agents sweep the large, nebulous-edged codebase to produce a migration inventory: every consumer of declaracion extraction and any residue of the deleted DeclaracionExtractor surface, the state of every registry declaracion_pdf extraction profile, registry schemas needing tweaks for the named-field primitive, and the per-modelo AEAT Diseno corpus available to source profiles from. This Wave hard-precedes W02, W03, W04, and W05 because its inventory scopes them; its findings are EXPECTED to surface additional migration and schema-tweak Steps appended to later Waves via the vault plan CLI. Authorised by the declaracion-extraction-architecture ADR, its research, and the branch-reconciliation audit.

### Phase `W01.P01` - consumer and registry-profile inventory sweep

Sub-agent discovery Steps producing the migration inventory that scopes every later Wave.

- [ ] `W01.P01.S01` - Sweep every consumer of declaracion extraction and any residue of the deleted DeclaracionExtractor surface and record callers, exports, and dead references; `src/aeat/adapters/inbound/declaracion/`.
- [ ] `W01.P01.S02` - Inventory every registry declaracion_pdf extraction profile and classify its state as functional numeric, absent, or dead decl.* slug stub; `src/aeat/_data/registry/aeat/modelos/`.
- [ ] `W01.P01.S03` - Identify registry schema fields and constraints needing tweaks for the named-field primitive; `src/aeat/domain/calculations/registry/_schema.py`.
- [ ] `W01.P01.S04` - Catalogue the per-modelo AEAT Diseno and instructions corpus available for modelos 303, 180, 190 and the named-field modelos; `src/aeat/_data/registry/aeat/modelos/`.
- [ ] `W01.P01.S05` - Consolidate the four discovery sweeps into a migration inventory and append the surfaced migration and schema-tweak Steps to W02 through W05 via the vault plan CLI; `.vault/plan/2026-05-21-declaracion-extraction-architecture-plan.md`.

## Wave `W02` - named-field primitive

Umbrella-infrastructure Wave. Extends ExtractionProfileDefinition with the typed named-field primitive (match_strategy and value_kind Literal enums plus an optional label pattern), branches the parser matching core on match_strategy, and adds the snapshot-build validator rule that a declaracion_pdf profile targeting a text-typed casilla must use named_label. The primitive is purely additive: numeric-casilla profiles already working stay unchanged. This Wave depends on W01 and hard-precedes W04, whose named-field profile content cannot be authored until the primitive exists. Authorised by the declaracion-extraction-architecture ADR and its research.

### Phase `W02.P02` - schema extension

Extend ExtractionProfileDefinition with the typed named-field primitive fields.

- [ ] `W02.P02.S06` - Run a git diff collision check on the contended registry schema file before editing in the shared worktree; `src/aeat/domain/calculations/registry/_schema.py`.
- [ ] `W02.P02.S07` - Add the typed match_strategy Literal numeric_casilla or named_label field to ExtractionProfileDefinition holding the strict frozen extra-forbid discipline; `src/aeat/domain/calculations/registry/_schema.py`.
- [ ] `W02.P02.S08` - Add the typed value_kind Literal amount text or enum field to the extraction-profile target descriptor; `src/aeat/domain/calculations/registry/_schema.py`.
- [ ] `W02.P02.S09` - Add the optional named_label pattern field to the extraction-profile target descriptor; `src/aeat/domain/calculations/registry/_schema.py`.
- [ ] `W02.P02.S10` - Add strict roundtrip and anti-tautology tests for the extended ExtractionProfileDefinition named-field fields; `src/aeat/domain/calculations/registry/test_registry_schema.py`.

### Phase `W02.P03` - parser match-strategy branch

Branch the parser matching core on match_strategy without changing the numeric path.

- [ ] `W02.P03.S11` - Run a git diff collision check on the contended parser file before editing in the shared worktree; `src/aeat/adapters/inbound/declaracion/_parser.py`.
- [ ] `W02.P03.S12` - Branch _find_casilla_hits on match_strategy leaving the numeric_casilla path byte-for-byte unchanged; `src/aeat/adapters/inbound/declaracion/_parser.py`.
- [ ] `W02.P03.S13` - Implement the named_label matching path anchoring on the printed label and capturing via the existing TEXT_VALUE_GROUP; `src/aeat/adapters/inbound/declaracion/_parser.py`.
- [ ] `W02.P03.S14` - Add parser-boundary tests proving the numeric path is unchanged and the named_label path captures text values; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

### Phase `W02.P04` - validator text-casilla gate

Add the snapshot-build validator rule rejecting text-typed casilla targets without named_label.

- [ ] `W02.P04.S15` - Run a git diff collision check on the contended registry referential validator before editing in the shared worktree; `src/aeat/domain/calculations/registry/_validate_references.py`.
- [ ] `W02.P04.S16` - Add the snapshot-build validator rule that a declaracion_pdf profile targeting a data_type text casilla must use named_label; `src/aeat/domain/calculations/registry/_validate_references.py`.
- [ ] `W02.P04.S17` - Add a regression test proving the validator gate fails loud on a text-casilla decl.* slug stub; `src/aeat/domain/calculations/registry/test_referential_integrity.py`.

## Wave `W03` - numeric-casilla tier

Numeric-casilla tier Wave. Authors declaracion_pdf extraction profiles for modelos 303 and 180 from the AEAT Diseno and instructions, replaces modelo 190's abstract decl.* stub targets with the real numeric and labelled targets the form prints, and restores the modelo 130 03 = 01 - 02 cross-check as a verification_expectations stanza. Depends on W01; independent of W02 and W04. Authorised by the declaracion-extraction-architecture ADR, its research, and branch-reconciliation audit row 6.

### Phase `W03.P05` - scoped numeric-tier discovery

Scoped discovery sweep of the AEAT Diseno corpus and casilla data for the numeric-tier modelos.

- [ ] `W03.P05.S18` - Sweep the AEAT Diseno and instructions corpus and casilla registry data for modelos 303, 180, and 190 and append any surfaced schema-tweak Steps via the vault plan CLI; `src/aeat/_data/registry/aeat/modelos/`.

### Phase `W03.P06` - modelo 303 and 180 profile authoring

Author declaracion_pdf extraction profiles for modelos 303 and 180.

- [ ] `W03.P06.S19` - Author the declaracion_pdf extraction profile for Modelo 303 from the AEAT Diseno and instructions; `src/aeat/_data/registry/aeat/modelos/303/`.
- [ ] `W03.P06.S20` - Author the declaracion_pdf extraction profile for Modelo 180 from the AEAT Diseno and instructions; `src/aeat/_data/registry/aeat/modelos/180/`.

### Phase `W03.P07` - modelo 190 stub repair and modelo 130 cross-check

Replace modelo 190's decl.* stub targets and restore the modelo 130 cross-check stanza.

- [ ] `W03.P07.S21` - Replace Modelo 190's abstract decl.* stub target_casillas with the real numeric and labelled targets the form prints; `src/aeat/_data/registry/aeat/modelos/190/`.
- [ ] `W03.P07.S22` - Restore the Modelo 130 03 = 01 - 02 intra-filing cross-check as a verification_expectations stanza; `src/aeat/_data/registry/aeat/modelos/130/`.
- [ ] `W03.P07.S23` - Verify modelos 130, 111, 115, and 123 still parse and validate unchanged after the numeric-tier changes; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

## Wave `W04` - named-field tier

Named-field tier Wave. Corrects or removes the dead modelo 720 and 840 stub profiles, registers modelo 037 which has no registry presence today, and authors named-field declaracion_pdf profiles for modelos 036, 037, 369, 720, and 840 on the W02 primitive. Deferred content of the ADR, in-scope as part of this umbrella plan. Hard-depends on W02; depends on W01. Authorised by the declaracion-extraction-architecture ADR and its research.

### Phase `W04.P08` - scoped named-field discovery

Scoped discovery sweep of the named-field modelo corpus and registry presence.

- [ ] `W04.P08.S24` - Sweep the named-field modelo corpus and registry presence for modelos 036, 037, 369, 720, and 840 and append any surfaced schema-tweak Steps via the vault plan CLI; `src/aeat/_data/registry/aeat/modelos/`.

### Phase `W04.P09` - dead-stub repair and modelo 037 registration

Correct or remove the dead 720/840 stubs and register modelo 037.

- [ ] `W04.P09.S25` - Correct or remove the dead Modelo 720 declaracion_pdf stub profile so it no longer loads green; `src/aeat/_data/registry/aeat/modelos/720/`.
- [ ] `W04.P09.S26` - Correct or remove the dead Modelo 840 declaracion_pdf stub profile so it no longer loads green; `src/aeat/_data/registry/aeat/modelos/840/`.
- [ ] `W04.P09.S27` - Register Modelo 037 in the registry which has no registry presence today; `src/aeat/_data/registry/aeat/modelos/037/`.

### Phase `W04.P10` - named-field profile authoring

Author named-field declaracion_pdf profiles for modelos 036, 037, 369, 720, and 840.

- [ ] `W04.P10.S28` - Author the named-field declaracion_pdf profile for Modelo 036 using the W02 named_label primitive; `src/aeat/_data/registry/aeat/modelos/036/`.
- [ ] `W04.P10.S29` - Author the named-field declaracion_pdf profile for Modelo 037 using the W02 named_label primitive; `src/aeat/_data/registry/aeat/modelos/037/`.
- [ ] `W04.P10.S30` - Author the named-field declaracion_pdf profile for Modelo 369 using the W02 named_label primitive; `src/aeat/_data/registry/aeat/modelos/369/`.
- [ ] `W04.P10.S31` - Author the named-field declaracion_pdf profile for Modelo 720 using the W02 named_label primitive; `src/aeat/_data/registry/aeat/modelos/720/`.
- [ ] `W04.P10.S32` - Author the named-field declaracion_pdf profile for Modelo 840 using the W02 named_label primitive; `src/aeat/_data/registry/aeat/modelos/840/`.

## Wave `W05` - verification and rollout

Verification Wave. Adds real per-modelo round-trip parse tests against PDF corpus fixtures, confirms the snapshot-build gate is green, and confirms all 26 modelos validate. Depends on every preceding Wave. Authorised by the declaracion-extraction-architecture ADR and its research.

### Phase `W05.P11` - round-trip parse tests and gate verification

Add per-modelo round-trip parse tests and confirm the snapshot-build gate is green.

- [ ] `W05.P11.S33` - Add a real round-trip parse test for Modelo 303 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S34` - Add a real round-trip parse test for Modelo 180 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S35` - Add a real round-trip parse test for Modelo 190 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S36` - Add a real round-trip parse test for Modelo 036 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S37` - Add a real round-trip parse test for Modelo 037 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S38` - Add a real round-trip parse test for Modelo 369 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S39` - Add a real round-trip parse test for Modelo 720 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S40` - Add a real round-trip parse test for Modelo 840 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S41` - Confirm the snapshot-build gate is green and all 26 modelos validate; `src/aeat/domain/calculations/registry/test_committed_registry.py`.

## Proposed Changes

This plan executes the accepted declaracion-extraction-architecture ADR,
which ratifies the registry-profile-driven generic parser as the
canonical declaracion-extraction architecture and formally supersedes the
per-modelo `DeclaracionExtractor` ABC design. It extends the registry
profile schema with a typed named-field primitive, then authors the
registry extraction-profile data the ADR's two tiers require: the
numeric-casilla tier (modelos 130, 303, 111, 115, 180, 190, 123) and the
named-field tier (modelos 036, 037, 369, 720, 840). It closes the
silent-failure defects the branch-reconciliation audit recorded: the
absent 303 and 180 profiles, the dead `decl.*`-slug stub in modelo 190,
the dead 720/840 named-field stubs, and the lost modelo 130
`03 = 01 - 02` cross-check. The ADR, its research, and the
branch-reconciliation audit (rows 5 and 6 of the `271-pdf-import`
backlog) are carried in the `related:` frontmatter and authorise every
Step.

This plan is OPEN-ENDED. The codebase is large and the migration edges
are nebulous. Wave `W01` is a discovery sweep whose inventory scopes
every later Wave; Waves `W03` and `W04` each open with a scoped
discovery Phase. Both discovery surfaces are EXPECTED to surface
additional migration and schema-tweak Steps not enumerated at authoring
time. The plan is extended in place via the `vault plan` CLI
(`step add`, `step insert`, `phase add`, `wave add`) as execution
proceeds; the Step set above is the authored floor, not the ceiling.

Conformance constraints apply to every Step. The named-field schema
extension holds the strict, frozen, `extra="forbid"` discipline of the
`2026-05-18` schema-hardening ADR: typed `Literal` enums, no
`dict[str, Any]`, no `cast(...)` escapes. Tax-domain identifiers follow
the Spanish-stem rule of the `2026-05-19` terminology ADR. Profiles and
the modelo 130 cross-check are authored as reviewed registry TOML, not
Python. The named-field primitive is purely additive: numeric-casilla
profiles already working (130, 111, 115, 123) must keep validating and
parsing unchanged. No live AEAT write surface is touched; this is an
inbound-parsing and registry-data concern only.

This is a SHARED worktree. Three files are contended:
`src/aeat/domain/calculations/registry/_schema.py`,
`src/aeat/adapters/inbound/declaracion/_parser.py`, and the registry
referential validator `src/aeat/domain/calculations/registry/_validate_references.py`.
Every Step that edits a contended file runs a `git diff` collision check
before its first edit and aborts on non-authored working-tree changes;
those collision-check Steps are enumerated explicitly as `S06`, `S11`,
and `S15`. No mutating or destructive git is run.

## Parallelization

Waves are hard-sequenced and must land in order `W01`, `W02`, `W03`,
`W04`, `W05`. `W01` discovery precedes all other Waves because its
inventory scopes them. `W02` (the named-field primitive) MUST land
before `W04` (named-field profile content) because `W04` profiles depend
on the primitive. `W03` (numeric-casilla tier) depends on `W01` but is
independent of `W02` and `W04`. `W05` verification depends on every
preceding Wave.

Within a Wave, Phases that share no contended file may run in parallel.
The `W03` profile-authoring Steps for modelos 303, 180, and 190 are
registry-data-only and mutually parallelisable, as are the `W04`
named-field profile-authoring Steps. The `W02` schema, parser, and
validator Phases carry a hard internal order: the schema extension
(`P02`) lands before the parser branch (`P03`) and before the validator
rule (`P04`). Any Step touching a contended file is serialised against
other Steps touching the same file and runs the `git diff` collision
check first.

## Verification

The plan is complete when every Step in every Wave is closed (`- [x]`)
and the following criteria all hold:

- The `W01` discovery inventory exists and has been used to extend the
  plan with any migration or schema-tweak Steps it surfaced.
- `ExtractionProfileDefinition` carries the typed `match_strategy`,
  `value_kind`, and optional label-pattern fields; the schema models
  pass the strict, frozen, `extra="forbid"` discipline; no
  `dict[str, Any]` or `cast(...)` escape was introduced.
- `_find_casilla_hits` branches on `match_strategy`; the numeric path is
  unchanged in behaviour and modelos 130, 111, 115, 123 still parse and
  validate.
- The snapshot-build validator fails any `declaracion_pdf` profile that
  targets a `data_type = "text"` casilla without the `named_label`
  strategy; a regression test proves the gate fails loud.
- Modelos 303 and 180 have functional `declaracion_pdf` extraction
  profiles; modelo 190's `decl.*` stub targets are replaced with real
  targets; the modelo 130 `03 = 01 - 02` cross-check is present as a
  `verification_expectations` stanza.
- The dead modelo 720 and 840 stub profiles are corrected or removed;
  modelo 037 is registered; modelos 036, 037, 369, 720, 840 carry
  named-field `declaracion_pdf` profiles.
- Real per-modelo round-trip parse tests pass against PDF corpus
  fixtures; the snapshot-build gate is green; all 26 modelos validate.
- `vault plan check` and `vault check all` report no issues against this
  plan document.

For tier-specific verification cadence, see the convention ADR
authorising this plan via the `related:` frontmatter.
