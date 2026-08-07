---
tags:
  - '#plan'
  - '#canonical-identifiers'
date: '2026-08-07'
modified: '2026-08-07'
body_hash: 'sha256:7830a3904e4c29b6a7de8b69d2d1b68cec7a556243d7ef1e4d5cb57cab11aea4'
tier: L3
related:
  - '[[2026-08-07-canonical-identifiers-adr]]'
  - '[[2026-08-07-canonical-identifiers-reference]]'
  - '[[2026-08-07-justificante-identity-matching-adr]]'
---
# `canonical-identifiers` plan

Enroll the AEAT document-identifier taxonomy `2026-08-07-canonical-identifiers-adr`
decided, staged so no Step retypes more than one identifier concept at once.

## Description

Executes `2026-08-07-canonical-identifiers-adr`, grounded in
`2026-08-07-canonical-identifiers-reference`. The ADR decided a closed
`IdentifierNamespace` enum plus per-namespace typed aliases in
`core/identity/`, staged enrollment rather than a big-bang retype of the
589-field identifier surface, and an honest shape-only resolver. This plan
adopts the sibling `2026-08-07-justificante-identity-matching-adr`'s Site
1-3 call-site fix as already-settled and delivers that record's deferred
"Option 4" typed namespace marker as Wave `W03`. Wave `W01` governs the
hex-64 primitive consolidation, Wave `W02` the AEAT-issued namespace
enrollment (expediente id, clave de liquidacion, then CSV under a separate,
evidence-gated Phase), Wave `W03` the resolver and the type-level guard on
`matches_filing_target`, and Wave `W04` the ratchet gate plus explicit
recording of every deferred surface (NRC, fixed-width export, registry
TOML, locale/wire, and the unclassified remainder of the census).

## Steps

## Wave `W01` - Core primitive consolidation

Collapses the two hand-rolled hex-64 identity declarations
(`domain/modelos/_ids.py`, `domain/invoices/_ids.py`) onto the one existing
`core/identity/` `Hex64Str` primitive before any new namespace lands, so the
taxonomy grows from a clean shared base. No persisted shape changes; this
Wave must land and its roundtrip suite stay green before Wave `W02` begins.

### Phase `W01.P01` - relocate hex-64 identity aliases

Moves the four modelo ids and the invoice id onto the shared `Hex64Str`
primitive with no shape change, proving the relocation is safe before any
AEAT-issued namespace work begins.

- [ ] `W01.P01.S01` - alias `WorkUnitId`, `CalculationRevisionId`, `FilingRecordId`, and `VerificationReportId` from `core.identity.Hex64Str`, deleting the duplicate pattern declaration; `src/cadrumo/domain/modelos/_ids.py`.
- [ ] `W01.P01.S02` - relocate the four aliased ids into `core/identity/` and update every consumer import in the same commit per the relocation-atomicity rule; `src/cadrumo/core/identity/__init__.py`.
- [ ] `W01.P01.S03` - alias `InvoiceId` from `core.identity.Hex64Str`, deleting its duplicate pattern declaration, and relocate it into `core/identity/` with its consumer imports updated in the same commit; `src/cadrumo/domain/invoices/_ids.py`.
- [ ] `W01.P01.S04` - run the full persistence and pydantic-model roundtrip suite to confirm the relocation changed no shape; `src/cadrumo/tests/`.

## Wave `W02` - AEAT-issued namespace enrollment

Introduces the `IdentifierNamespace` enum and the AEAT-issued typed aliases,
closing the expediente-id divergence between `sede/_schema.py` and
`iva_compensation/_carry_forward.py` under one bound, then separately
deciding and enrolling the CSV shape only after empirical replay against
real captured receipts. Depends on Wave `W01` landing first.

### Phase `W02.P02` - namespace enum and expediente or clave aliases

Declares the closed namespace enum and the `AeatExpedienteId`,
`AeatClaveLiquidacion`, and `AeatPresentationId` aliases at their already
AEAT-evidenced bounds, then retypes every field carrying those concepts
onto the shared alias, tightening the one under-constrained divergence.

- [ ] `W02.P02.S05` - declare `IdentifierNamespace` as a closed StrEnum split into AEAT-issued and app-derived groups, each member documented with the concept it names; `src/cadrumo/core/identity/_namespace.py`.
- [ ] `W02.P02.S06` - declare `AeatExpedienteId` at the sede-schema bound (12-32 chars, AEAT shape pattern) and `AeatClaveLiquidacion` and `AeatPresentationId` at their current field bounds; `src/cadrumo/core/identity/__init__.py`.
- [ ] `W02.P02.S07` - retype the eleven `expediente_id` fields onto `AeatExpedienteId`, removing the per-field repeated bound and the duplicated shape validator; `src/cadrumo/adapters/outbound/aeat/sede/_schema.py`.
- [ ] `W02.P02.S08` - retype `Deuda.clave_liquidacion` onto `AeatClaveLiquidacion`; `src/cadrumo/adapters/outbound/aeat/sede/_schema.py`.
- [ ] `W02.P02.S09` - retype `PeriodComplianceState.expediente_id` onto `AeatExpedienteId`, closing the min-length-1 divergence, with a strict roundtrip proving every already-persisted observed value still validates; `src/cadrumo/domain/iva_compensation/_carry_forward.py`.
- [ ] `W02.P02.S10` - add an anti-tautology proof for the tightened expediente-id bound: corrupt a persisted fixture value below the new bound and assert refusal; `src/cadrumo/domain/iva_compensation/tests/`.

### Phase `W02.P03` - CSV canonical shape decision and enrollment

Decides the CSV shape empirically against real captured receipts before any
retype, then enrolls `AeatCsv` and reconciles the three divergent
validation strengths and two normalisation forms to one, enumerating every
storage key the change could orphan.

- [ ] `W02.P03.S11` - replay the two real captured M303 justificante PDF fixtures against the three candidate CSV shapes (`is_aeat_csv` 8-32 uppercase pattern, `JustificanteCsv` 4-64 no pattern, and the two normalisation forms) and record in the Step record which shape and normal form both fixtures actually satisfy; `src/cadrumo/domain/justificante/`.
- [ ] `W02.P03.S12` - enumerate every secure-object storage key derived from the CSV value, starting from `extract_identifier` in the justificante persistence adapter, and record for each whether the decided shape and normal form leaves it unchanged; `src/cadrumo/adapters/persistence/profile/justificante.py`.
- [ ] `W02.P03.S13` - declare `AeatCsv` in `core/identity/` at the shape decided in `W02.P03.S11`; `src/cadrumo/core/identity/__init__.py`.
- [ ] `W02.P03.S14` - retype `JustificanteRef.csv` onto `AeatCsv`, removing its now-redundant field validator; `src/cadrumo/adapters/outbound/aeat/sede/_schema.py`.
- [ ] `W02.P03.S15` - retype `Justificante.csv` (via the `JustificanteCsv` alias) onto `AeatCsv`; `src/cadrumo/domain/justificante/_schema.py`.
- [ ] `W02.P03.S16` - retype the two bare-`str` CSV fields onto `AeatCsv`; `src/cadrumo/application/live/_justificante.py`.
- [ ] `W02.P03.S17` - retype the bare-`str` CSV field onto `AeatCsv`; `src/cadrumo/adapters/inbound/borrador/_schema.py`.
- [ ] `W02.P03.S18` - unify CSV normalisation to one form across the verify adapter and the calendar-evidence consumer, matching whichever form `W02.P03.S11` proved correct; `src/cadrumo/application/overview/_calendar_evidence.py`.
- [ ] `W02.P03.S19` - add a strict roundtrip test for `Justificante` populating every defaultable field non-default, plus an anti-tautology proof corrupting the persisted CSV value and asserting refusal; `src/cadrumo/domain/justificante/tests/`.
- [ ] `W02.P03.S20` - re-run the live-captured justificante fixture parse regression to confirm the enrolled shape still accepts both real receipts; `src/cadrumo/domain/justificante/tests/`.

## Wave `W03` - Resolver and type-level namespace guard

Lands the shape-only resolver with its documented ambiguity limit, then
delivers the sibling `justificante-identity-matching` ADR's deferred
"Option 4" by retyping `matches_filing_target`'s `presentation_id`
parameter so a register-namespace value is refused at the type-checker
boundary. Depends on Wave `W02` landing first.

### Phase `W03.P04` - shape resolver and matches_filing_target hardening

Delivers the resolver the operator asked for, honest about where shape
alone cannot disambiguate, and closes the recurrence risk the sibling ADR
named as future hardening.

- [ ] `W03.P04.S21` - land `resolve_identifier_namespace` returning every `IdentifierNamespace` a value's shape is consistent with, with its docstring stating any pair of namespaces whose shapes overlap; `src/cadrumo/core/identity/_namespace.py`.
- [ ] `W03.P04.S22` - add unit coverage proving the resolver returns more than one namespace for a value shaped to overlap two members, and exactly one for a value shaped to only one; `src/cadrumo/core/identity/tests/`.
- [ ] `W03.P04.S23` - retype `matches_filing_target`'s `presentation_id` parameter from bare `str | None` to `AeatPresentationId | AeatCsv | None`; `src/cadrumo/domain/justificante/_schema.py`.
- [ ] `W03.P04.S24` - update the corrected pinning test from the sibling ADR to assert the new parameter type is honoured, without reintroducing `presentation_id=expediente_id` at any call site; `src/cadrumo/domain/justificante/tests/`.
- [ ] `W03.P04.S25` - confirm by inspection that none of the three call sites the sibling ADR corrected regressed to passing an `AeatExpedienteId`-typed value into the now-narrower parameter; `src/cadrumo/application/live/_filed_observation_persistence.py`.

## Wave `W04` - Ratchet gate and closeout

Adds the structural enrollment gate that keeps the taxonomy from decaying
as new identifier-shaped fields are added, proves the gate's own bite, and
records every surface this plan deliberately left unenrolled. Depends on
Wave `W03` landing first.

### Phase `W04.P05` - structural enrollment gate and closeout recording

Delivers the property-keyed ratchet test and makes the plan's own known
gaps explicit rather than implied-complete.

- [ ] `W04.P05.S26` - author the identifier-enrollment ratchet test asserting every production pydantic field whose name matches the namespace vocabulary carries a `core.identity` namespace alias rather than bare `str`, with `Declaracion.estado` and `Deuda.situacion` as named, documented exclusions; `src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py`.
- [ ] `W04.P05.S27` - prove the gate's bite: add a throwaway bare-`str` field named to match the namespace vocabulary on a scratch model outside `src`, confirm the gate reds, then remove it and confirm the gate is green again; `src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py`.
- [ ] `W04.P05.S28` - record NRC, fixed-width fichero-BOE and worksheet export serialisation sites, registry TOML id-shaped values, and the unclassified remainder of the 589-field census as explicit deferred follow-ups in this plan's Verification section, each with a named next reference rather than a silent close; `.vault/plan/2026-08-07-canonical-identifiers-plan.md`.

## Parallelization

Waves are sequenced: `W01` before `W02` before `W03` before `W04`, per the
plan's own dependency chain (each Wave's alias or gate depends on the prior
Wave's types existing). Within `W02`, Phase `P02` (expediente id, clave de
liquidacion) and Phase `P03` (CSV) touch disjoint files and may run in
parallel once `W01` closes. Within a Phase, Steps retyping disjoint files
(for example `W02.P02.S07` and `W02.P02.S08`, both in the same file, stay
sequential; `W02.P02.S09`, a different file, may run in parallel with
either) may be parallelized per the no-compression rule's file-level
granularity; Steps sharing one file stay sequential to avoid contended
edits.

## Verification

The plan is complete when every Step above is closed (`- [x]`) and:

- The full roundtrip and anti-tautology suites for every retyped model
  (`W01.P01.S04`, `W02.P02.S10`, `W02.P03.S19`) pass.
- The ratchet gate (`W04.P05.S26`) is green against the enrolled baseline
  and its bite proof (`W04.P05.S27`) is recorded in that Step's execution
  record.
- `matches_filing_target` (`W03.P04.S23`) type-checks under the project's
  static type gate with the narrowed parameter type.
- The two real-captured M303 justificante fixtures still parse
  (`W02.P03.S20`).

**Explicitly deferred, not covered by this plan's completion** (recorded
per `W04.P05.S28`): NRC capture and persistence (no existing field to
retype); fixed-width fichero-BOE and worksheet export serialisation sites
(byte-exact-format risk not yet assessed); registry TOML id-shaped values;
locale and wire-payload identifier surfaces; and the unclassified remainder
of the 589-field identifier-shaped census beyond the concepts this plan
names. A future plan referencing this one's ADR is the sanctioned next step
for any of these, not a silent assumption that this plan's closure covers
them.
