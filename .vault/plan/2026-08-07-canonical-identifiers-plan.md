---
tags:
  - '#plan'
  - '#canonical-identifiers'
date: '2026-08-07'
modified: '2026-08-10'
body_hash: 'sha256:9ccc2ec6c7146ed685f22cdd7581b4bb3ceb5638caa41415070f0fc0e16c829b'
tier: L3
related:
  - '[[2026-08-07-canonical-identifiers-adr]]'
  - '[[2026-08-07-canonical-identifiers-reference]]'
  - '[[2026-08-07-justificante-identity-matching-adr]]'
---

<!-- RETIRED: S26, S27, S28 -->

# `canonical-identifiers` plan

Enroll the AEAT document-identifier taxonomy `2026-08-07-canonical-identifiers-adr`
decided, staged so no Step retypes more than one identifier concept at once.

## Description

Executes `2026-08-07-canonical-identifiers-adr` (including its same-day
Amendment), grounded in `2026-08-07-canonical-identifiers-reference`. Waves
`W01`-`W03` are the original ADR scope: hex-64 primitive consolidation,
AEAT-issued namespace enrollment (expediente id, clave de liquidacion, then
CSV under an evidence-gated Phase), and the resolver plus the
`matches_filing_target` type-level guard delivering the sibling
`justificante-identity-matching-adr`'s deferred "Option 4".

The CSV Phase (`W02.P03`) was originally prioritised within `W02` because
the sibling plan's fix for its own two-filings-per-period defect was said to
depend on a cotejo-derived CSV field this taxonomy's type gates. **That
prioritisation is withdrawn:** the sibling plan has since closed every Step
and shipped without `AeatCsv`, so the dependency no longer exists.
`W02.P02` runs first. `W02.P03` has separately been re-planned: the real
captured receipts its decision Step was to replay do not exist and cannot be
obtained, so that Step is now a documented decision on the two live
declarations rather than an empirical replay, with the limitation stated in
its own Phase note and the Verification section corrected to match.

Waves `W04`-`W08` are the Amendment's scope: the mechanical app-derived
alias-adoption tranche (302 fields, existing aliases only); the newly
surfaced namespaces (`revision_id` adjudication, truncated display ids,
`registry_snapshot_id`, `registry_revision_id`, `certificado_id`, box/form
numbers, M210/M720 closed-set enums); the tax-identity split
(`SubjectTaxId` versus `TaxIdIdentityToken`); the free-text
three-population documentation pass plus the second-pass noun-heuristic
sweep that proved the 589 denominator is a floor; and the storage
key-composition redesign (extending `_namespace_registry.py`, bounded to
Cadrumo's own databases via its own teardown authority, never a filesystem
delete) plus the MCP/CLI golden-schema pinning the wire census showed is
otherwise uncovered. Wave `W09` is the ratchet gate and closeout, now
correctly sequenced last, after every enrollment tranche.

**Declared gap:** the mechanical tranche in `W04` (and the two tax-identity
Steps in `W06`) is scoped per-namespace at package granularity, not per
individual field occurrence. This is a stated, reasoned exception to the
no-compression convention: every occurrence in scope receives the SAME
already-existing alias (a single mechanical transform, not heterogeneous
per-site work), and each Step's execution record MUST enumerate every file
it touched before the Step is checked closed. **Reconciliation target: the
"Classification census" section of `2026-08-07-canonical-identifiers-reference`,
never a scratchpad path.** An earlier draft of this plan pointed the
reconciliation requirement at a coordinating session's `classified589.csv`;
that artefact lives in a different agent's scratchpad namespace, which no
executor in this session or a future one can read, making the gate
unmeetable. The census membership is now promoted into the Reference
document specifically so this gate is checkable. A Step closed without a
file enumeration cross-checked against that section is not verifiably
complete, and every compressed Step (`W04.P06.S29`-`S33`, `W06.P09.S45`,
`W06.P10.S46`) is ONE atomic commit carrying every file it touches - the
one-symbol-one-commit relocation-atomicity rule binds inside a compressed
row exactly as it does inside a single-file row; landing a namespace's
adoption across several commits is not a valid reading of the compression.

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
AEAT-issued namespace work begins. **Execution is deliberately held until
the current tree settles** (four concurrent executors, HEAD moving under
live commits, contended modules); every Step in this Phase, and every
mechanical Step this plan later stages, MUST re-verify its target sites
against current HEAD immediately before editing rather than trusting a
file list gathered when this plan was written - a stale list is the most
likely way a mechanical tranche collides with unrelated concurrent work.

- [ ] `W01.P01.S01` - Re-read domain/modelos/_ids.py against current HEAD to confirm the four ids and the duplicate pattern are still declared as described here, then alias WorkUnitId, CalculationRevisionId, FilingRecordId and VerificationReportId from core.identity.Hex64Str, deleting the duplicate pattern declaration. HEAD re-read is DONE as of 2026-08-10: all four aliases and the module-local _HEX_64_PATTERN are still declared verbatim, so the duplication this row exists to close is still live. The aliasing itself does not land as its own commit -- it is inseparable from the relocation in S02, so each symbol's alias-and-move share one index per the relocation-atomicity rule; `src/cadrumo/domain/modelos/_ids.py`.
- [ ] `W01.P01.S02` - Relocate the four aliased ids into core/identity/ and update every consumer import in the same commit per the relocation-atomicity rule. FOUR COMMITS, one per symbol, tagged relocation:<symbol> -- the standing rule is one Step equals one symbol equals one atomic commit, and this row batches four. Ascending blast radius measured against HEAD: VerificationReportId 5 consumer files, FilingRecordId 10, CalculationRevisionId 20, WorkUnitId 27, with exactly ONE dirty consumer across all of them. THIS ROW OMITTED THREE THINGS a compliant execution must still do, rowed here rather than done silently: domain/modelos/_ids.py holds ONLY these four aliases and their __all__, so the LAST of the four commits EMPTIES it and must DELETE the module, because an empty module left standing is a bridge by another name. That deletion orphans docs/api/cadrumo.domain.modelos._ids.rst, which hard-crashes autodoc on the next nitpicky build, so the stub removal rides in the SAME commit and is generated by apidocs scaffold rather than hand-edited. And the module docstring names all four identities by name, so each departure makes it progressively false and the intermediate commits must trim it; `src/cadrumo/core/identity/__init__.py, src/cadrumo/domain/modelos/_ids.py, src/cadrumo/domain/modelos/__init__.py, docs/api/cadrumo.domain.modelos._ids.rst`.
- [x] `W01.P01.S03` - Re-read domain/invoices/_ids.py against current HEAD to confirm InvoiceId's duplicate declaration is still present as described here, then alias it from core.identity.Hex64Str, deleting the duplicate pattern declaration, and relocate it into core/identity/ with its consumer imports updated in the same commit. HEAD re-read is DONE: the duplicate _HEX_64_PATTERN is still declared. SAME OMISSION AS S02, rowed rather than done silently: this module holds ONLY InvoiceId and its __all__, so relocating it EMPTIES the module, which must therefore be DELETED in this commit and its stub docs/api/cadrumo.domain.invoices._ids.rst removed in the same commit via apidocs scaffold, never a hand-edit. Measured blast radius is 5 consumer files, none dirty; `src/cadrumo/domain/invoices/_ids.py, src/cadrumo/domain/invoices/__init__.py, src/cadrumo/core/identity/__init__.py, docs/api/cadrumo.domain.invoices._ids.rst`.
- [ ] `W01.P01.S04` - run the full persistence and pydantic-model roundtrip suite to confirm the relocation changed no shape; `src/cadrumo/tests/`.

## Wave `W02` - AEAT-issued namespace enrollment

Introduces the `IdentifierNamespace` enum and the AEAT-issued typed aliases,
closing the expediente-id divergence between `sede/_schema.py` and
`iva_compensation/_carry_forward.py` under one bound, then separately
deciding and enrolling the CSV shape on a recorded decision, since the
empirical replay this Wave originally planned has no evidence to run
against. Depends on Wave `W01` landing first.

### Phase `W02.P02` - namespace enum and expediente or clave aliases

Declares the closed namespace enum and the `AeatExpedienteId`,
`AeatClaveLiquidacion`, and `AeatPresentationId` aliases at their already
AEAT-evidenced bounds, then retypes every field carrying those concepts
onto the shared alias, tightening the one under-constrained divergence.

- [x] `W02.P02.S05` - declare `IdentifierNamespace` as a closed StrEnum split into AEAT-issued and app-derived groups, each member documented with the concept it names; `src/cadrumo/core/identity/_namespace.py`.
- [x] `W02.P02.S06` - declare `AeatExpedienteId` at the sede-schema bound (12-32 chars, AEAT shape pattern) and `AeatClaveLiquidacion` and `AeatPresentationId` at their current field bounds; `src/cadrumo/core/identity/__init__.py`.
- [x] `W02.P02.S07` - Retype every expediente_id model field onto AeatExpedienteId, removing the per-field repeated bound and the duplicated shape validator. DELIVERED WIDER THAN THIS ROW ORIGINALLY NAMED, recorded here so the widening is visible rather than silent. The concept is 4 model fields across 2 modules -- Expediente, JustificanteRef and FiledDeclaracionObservation in the sede schema, plus Declaracion in the declarations schema -- not the single file this row first named, and the module-local compiled expediente pattern plus both hand-written shape validators are deleted with them. A FIFTH divergence the plan never names is folded in: IvaCompensationAnnualSummary.expediente_id declared min_length=1 while its SOLE producer is FiledDeclaracionObservation.expediente_id, so the tight bound is provably satisfiable there and leaving it loose would have kept a real divergence open under a closed checkbox; `src/cadrumo/adapters/outbound/aeat/sede/_schema.py, src/cadrumo/adapters/outbound/aeat/sede/_declarations_schema.py, src/cadrumo/application/calculations/_iva_compensation_history.py`.
- [ ] `W02.P02.S08` - Retype Deuda.clave_liquidacion onto AeatClaveLiquidacion, and retype the second bare-str clave_liquidacion on the operator-facing wire payload in the same change. The Deuda model moved out of the sede schema module before this plan was written, so re-verify both sites against HEAD rather than trusting this row's earlier file reference; `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py, src/cadrumo/entrypoints/cli/_app_live_payloads.py`.
- [ ] `W02.P02.S09` - Land the discriminated expediente pair AND the status narrowing in ONE commit, per the 2026-08-10 ADR amendment. Splitting them leaves the model carrying two disagreeing provenance carriers, which is the state the amendment exists to prevent. Declare a closed five-member StrEnum in core naming the supplying paths with no catch-all member. It COEXISTS with ObservationSourceKind rather than reusing it, on the subject grounds the amendment records, and the enum's own docstring states that distinction so a later reader does not merge them. Add it to IvaCompensationPeriodState as a required field with no default, narrow expediente_id to AeatExpedienteId or None, and add a model validator so an AEAT-capture row must carry an expediente and a row of any other provenance must not. In the same commit narrow status to str or None carrying ONLY the AEAT-printed register status, re-express the domain lot builder's seeded-literal branch against the provenance member, drop the reconstruction path's literal, and emit provenance and register status as separate fields on the wallet CLI surface. Take the provenance as a required parameter on both conduit functions, because two of the five are otherwise unassignable where the model is built; `src/cadrumo/domain/iva_compensation/_carry_forward.py, src/cadrumo/core/, src/cadrumo/application/calculations/_iva_compensation_history.py, src/cadrumo/application/calculations/_iva_compensation_annual_partition.py, src/cadrumo/application/modelo/_filed_revision_observation.py, src/cadrumo/application/live/_filed_observation_persistence.py, src/cadrumo/entrypoints/cli/_modelo_iva_wallet_cli.py`.
- [ ] `W02.P02.S10` - Add the strict roundtrip and anti-tautology proof for the discriminated pair. Populate every defaultable field on IvaCompensationPeriodState non-default, push it through the real encrypted repository and assert strict model equality on load. For the anti-tautology proof delete the persisted provenance field from the on-disk payload, reload through the real production read path, and assert refusal rather than a silent re-default. Add a companion case proving the cross-field validator refuses both impossible pairs, an operator-seeded row carrying an expediente and an AEAT-capture row carrying none; `src/cadrumo/domain/iva_compensation/tests/`.
- [ ] `W02.P02.S11` - retype `ExpedienteDeclarationPayload.expediente_id` from unconstrained bare `str` onto `AeatExpedienteId`, closing the fourth (loosest) divergence sighted on the operator-facing wire contract; `src/cadrumo/entrypoints/cli/_app_live_payloads.py`.
- [ ] `W02.P02.S12` - add a golden-schema pinning test capturing `ExpedienteDeclarationPayload`'s advertised `model_json_schema()` before and after `W02.P02.S11`, so the CLI/MCP contract change is a visible reviewed diff rather than a silent constraint shift; `src/cadrumo/entrypoints/cli/tests/`.
- [ ] `W02.P02.S65` - Measure the legitimate population before closing the discriminated-pair rows, and treat this row rather than the new refusal as their close condition. Load and construct through the wallet-balance projection, the binding-prefill resolver and the M303 carry-ingress path and confirm every legitimate row still constructs and still loads. Assert against the NEW provenance field, never against status. This row previously admitted a vacuous pass: with status still carrying provenance an implementer could satisfy the clause below by reading provenance off status, which is a control passing against the wrong field. So it now carries a second assertion only the ruled design can satisfy, that status is None on every non-AEAT path. The disconfirming observation stands: if any of those three paths carries a row whose provenance is not one of the five enum members, the enum is incomplete and S09 must be reopened rather than the row forced into an approximate member. Record the count of rows exercised per path, because a control exercising zero rows reads identically to one that passes; `src/cadrumo/application/calculations/tests/`.

### Phase `W02.P03` - CSV canonical shape decision and enrollment

Decides the CSV shape on the documented contract and the risk asymmetry
between the two live declarations before any retype, then enrolls
`AeatCsv` and reconciles the three divergent validation strengths and two
normalisation forms to one, enumerating every storage key the change
touches.

**Re-planned: this Phase no longer claims empirical grounding, because none
is available to it.** `S13` and `S22` originally turned on replaying "the
two real captured M303 justificante PDF fixtures". Those do not exist. A
census of the justificante fixture tree finds 63 fixtures across every
modelo, all declaring `synthetic_generated`, none `real_corpus`; the
operator does not file this modelo and has no capture to supply; and AEAT
publishes only blank form templates, never a specimen of an issued
justificante, since a real one is personalised and generated only by a real
filing.

**Substituting the synthetic fixtures would have produced a vacuous gate
rather than a weaker one, which is why this Phase was re-planned instead.**
Not one of the 63 fixture PDFs carries a CSV token at all - their declared
roles are formula-verification and parser-anchor, neither of which is a
receipt. A replay against them would have decided the CSV shape from
evidence that does not contain a CSV, and would have reported green while
proving nothing.

`S13` is therefore a documented decision on the two live declarations and
the risk asymmetry between them, not a replay, and it records that the
shape rests on the documented contract rather than on a real artefact.
`S22` becomes a shape-conformance regression over the adopted bound. The
Verification section is corrected to match, so the plan is no longer
unclosable on evidence that will never exist.

**The original prioritisation is withdrawn.** This Phase was sequenced
first within `W02` because the sibling `justificante-identity-matching`
plan's fix for its own two-filings-per-period defect was said to depend on
this Phase's `AeatCsv` type. That plan has since closed every one of its
Steps and shipped without `AeatCsv`, so the dependency no longer exists and
`W02.P02` should run first.

- [ ] `W02.P03.S13` - Record the canonical CSV shape ruled by the ADR amendment of 2026-08-10, superseding this row's prior instruction to record that no empirical replay was possible. That instruction rested on a falsified premise and the evidence exists in three independent forms. First, three real AEAT-issued CSVs captured from live Sede sessions and byte-identical across two capture rounds (FNBB57PE9KZ5TN4R, MZRSYDRL5JMPJPRT, TUD4V9XAUV7QJ8QV), each exactly 16 uppercase alphanumeric characters. Second, 34 distinct CSV tokens across the 60 committed parser-anchor fixture PDFs, every one 16 uppercase alphanumeric. Third, a default-lane regression at adapters/inbound/justificante/tests/test_corpus_sidecar_roundtrip.py lines 244-249 that already asserts isalnum and isupper and a length between 8 and 24 on every parsed fixture. Adopt core/_aeat_csv.py's 8-32 uppercase-alphanumeric contract as canonical and retire JustificanteCsv's 4-64-no-pattern bound rather than keeping it as a second opinion. State in the Step record that the 8-24 assertion already running is strictly inside 8-32, so the retype tightens the field without being able to break the parse path; `src/cadrumo/domain/justificante/`.
- [ ] `W02.P03.S14` - enumerate every secure-object storage key derived from the CSV value, starting from `extract_identifier` in the justificante persistence adapter, informing (not gating, per the schema-rewrite authorisation) the key-composition redesign in `W08`; `src/cadrumo/adapters/persistence/profile/justificante.py`.
- [ ] `W02.P03.S15` - declare `AeatCsv` in `core/identity/` at the shape decided in `W02.P03.S13`; `src/cadrumo/core/identity/__init__.py`.
- [ ] `W02.P03.S16` - retype `JustificanteRef.csv` onto `AeatCsv`, removing its now-redundant field validator; `src/cadrumo/adapters/outbound/aeat/sede/_schema.py`.
- [ ] `W02.P03.S17` - Retype Justificante.csv onto AeatCsv, deleting the JustificanteCsv alias outright rather than re-pointing it, and delete its docstring claim that the receipt domain owns the bound because it owns the artefact the value is read from. That sentence asserts the ownership the 2026-08-10 ADR amendment overturns, and leaving it standing over a retyped alias leaves source prose describing the rejected design where the next reader meets it first; `src/cadrumo/domain/justificante/_schema.py`.
- [ ] `W02.P03.S18` - retype the two bare-`str` CSV fields onto `AeatCsv`; `src/cadrumo/application/live/_justificante.py`.
- [ ] `W02.P03.S19` - retype the bare-`str` CSV field onto `AeatCsv`; `src/cadrumo/adapters/inbound/borrador/_schema.py`.
- [ ] `W02.P03.S20` - unify CSV normalisation to one form across the verify adapter and the calendar-evidence consumer, matching whichever form `W02.P03.S13` proved correct; `src/cadrumo/application/overview/_calendar_evidence.py`.
- [ ] `W02.P03.S21` - add a strict roundtrip test for `Justificante` populating every defaultable field non-default, plus an anti-tautology proof corrupting the persisted CSV value and asserting refusal; `src/cadrumo/domain/justificante/tests/`.
- [ ] `W02.P03.S22` - Add a shape-conformance regression over the adopted 8-32 CSV bound pinning its accept and refuse boundaries explicitly, and correct this row's prior claim that the parser-anchor fixtures carry no CSV token. They do. All 60 carry one, 34 distinct, every one 16 uppercase alphanumeric, drawn into the page body by the fixture generators and recorded in each sidecar's replacements_applied list. Construct the boundary value set from the decided bound, covering the shortest and longest accepted forms and the nearest refused ones on each side of both the length and the character-class axis. Keep the existing corpus sidecar roundtrip regression running unchanged alongside it and treat it as this row's control rather than as background. It is the measurement that the legitimate population still passes, and this row does not close until it is green across all 60 fixtures. State in the Step record which claim each instrument proves, shape conformance by the boundary set and artefact fidelity by the fixture replay; `src/cadrumo/domain/justificante/tests/`.
- [ ] `W02.P03.S23` - Retype extract_csv_from_url's return annotation from bare str to AeatCsv, resolving this row's OBSOLETE AS WRITTEN state on measurement rather than deleting it. The row assumed the sibling justificante-identity-matching plan would hand off a new persisted cotejo-derived CSV field. It did not. Its chosen Option 4 recovers the CSV non-persistingly from FiledDeclaracionArtefact.source_url through extract_csv_from_url, so there is no new field, but there is a real successor target. That function already shape-validates its result with is_aeat_csv, the exact canonical contract AeatCsv carries, so the retype documents an invariant the function already enforces rather than adding a constraint. Confirm all four consumers still type-check; `src/cadrumo/adapters/outbound/aeat/sede/_declarations_remote.py`.

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

- [ ] `W03.P04.S24` - HELD pending the deciding Step in this Phase. Do not land resolve_identifier_namespace until a production site is named that genuinely needs to ask which namespaces a bare value is consistent with. The 2026-08-10 ADR amendment records why. This row's only planned enrollment was matches_filing_target's presentation_id parameter, which no longer exists, and IdentifierNamespace already ships with no consumer outside its own module and test. Landing the resolver now would add a second dormant symbol beside the first; `src/cadrumo/core/identity/_namespace.py`.
- [ ] `W03.P04.S25` - HELD with S24 and executed in the same action as it. Add unit coverage proving the resolver returns more than one namespace for a value shaped to overlap two members and exactly one for a value shaped to only one, but only once a real consumer exists to justify the resolver at all; `src/cadrumo/core/identity/tests/`.
- [ ] `W03.P04.S64` - Decide whether resolve_identifier_namespace is enrolled or dropped, and record the outcome before S24 executes. Search production for a site holding an AEAT identifier value whose namespace is UNKNOWN at the point of use. A semantic sweep run for the 2026-08-10 ADR amendment found none, returning only the enum's own module, its own test and an in-flight census tool. The disconfirming observation that decides this row: a genuine consumer holds a value whose namespace cannot be read off its own field type. If every candidate turns out to hold a value whose namespace is already fixed by its field type, record that the resolver is DROPPED and retire IdentifierNamespace with it rather than leaving an exported concept nothing uses. Do not manufacture a caller to justify the symbol; `src/cadrumo/core/identity/`.

## Wave `W04` - Mechanical app-derived alias adoption

Applies the FOUR already-existing app-derived aliases (`TransactionId`,
`BucketId`, `InvoiceId`, `BucketEventId`) at bare-`str` sites the
classification census confirmed are the same concept, unchanged constraint
shape. No new type is declared in this Wave. Depends on Wave `W01` landing
first (so `TransactionId` etc. are already relocated into `core/identity/`);
independent of Waves `W02`/`W03`.

### Phase `W04.P06` - adopt existing aliases at classified bare-str sites

Each Step retypes every classified bare-`str` occurrence of one namespace
name onto its existing alias, landed as ONE atomic commit per Step. Per the
Description's declared gap, this is package-batch-scoped; the Step's
execution record must enumerate every file touched, reconciled against the
"Classification census" section of `2026-08-07-canonical-identifiers-reference`.

- [ ] `W04.P06.S29` - retype every classified `transaction_id`/`parent_transaction_id`/`old_transaction_id`/`previous_transaction_id`/`merged_transaction_id` pydantic model field onto `TransactionId` across the ledger application package, function parameters and non-model locals excluded; `src/cadrumo/application/ledger/`.
- [ ] `W04.P06.S30` - retype every classified `transaction_id` pydantic model field onto `TransactionId` across the aggregation package's ledger models, then the renta-ledger-expenses model; `src/cadrumo/application/aggregation/`.
- [ ] `W04.P06.S31` - retype every classified `bucket_id` pydantic model field onto `BucketId` across the persistence-adapter package; `src/cadrumo/adapters/persistence/profile/`.
- [ ] `W04.P06.S32` - retype every classified `invoice_id` pydantic model field onto `InvoiceId` across the invoices application and domain packages; `src/cadrumo/application/invoices/`.
- [x] `W04.P06.S33` - retype every classified `bucket_event_id`/`event_id` pydantic model field onto the existing `BucketEventId` alias at the sites not already using it; `src/cadrumo/application/modelo/_reconciliation_records.py`.
- [ ] `W04.P06.S34` - run the full persistence and pydantic-model roundtrip suite and the CLI/MCP schema-conformance gate to confirm the four adoptions changed no wire shape for already-valid values; `src/cadrumo/tests/`.

## Wave `W05` - Newly surfaced namespaces

Adjudicates the `revision_id` conflation per-site, retypes truncated
display ids onto the existing `Hex16Str`, and declares the AEAT-issued and
app-derived namespaces the census surfaced beyond the original four.
Depends on Wave `W01` (for `CalculationRevisionId`) landing first.

### Phase `W05.P07` - revision id adjudication and truncated display ids

Closes the `revision_id` conflation the census found living inside the
enrollment work itself, and moves the two truncated display forms onto the
primitive already built for them.

- [ ] `W05.P07.S35` - adjudicate each of the twelve bare `revision_id` sites against its actual producer (registry `ModeloRevision.id` versus the hex-64 `CalculationRevisionId`), recording the per-site decision in the Step record before retyping any of them; `src/cadrumo/domain/calculations/registry/_snapshot_coordinate.py`.
- [ ] `W05.P07.S36` - retype every site adjudicated in `W05.P07.S35` onto `CalculationRevisionId` or the new `RegistryRevisionId` alias per its recorded disposition; `src/cadrumo/domain/calculations/registry/`.
- [ ] `W05.P07.S37` - retype `short_work_unit_id` and `short_calculation_revision_id` onto the existing `core.Hex16Str` primitive rather than the full-length aliases; `src/cadrumo/domain/modelos/`.

### Phase `W05.P08` - new AEAT-issued and app-derived namespace members

Declares the namespace members and aliases the census found with no
existing type at all.

- [ ] `W05.P08.S38` - declare `RegistrySnapshotId` as a new `IdentifierNamespace.APP_REGISTRY_SNAPSHOT_ID` member and alias for the composite `modelo:revision_id:filing_year:period` string, explicitly distinct from `core.identity.SnapshotId`; `src/cadrumo/core/identity/_namespace.py`.
- [ ] `W05.P08.S39` - declare `RegistryRevisionId` as a new `IdentifierNamespace.APP_REGISTRY_REVISION_ID` member and alias for the human-authored registry version tag; `src/cadrumo/core/identity/_namespace.py`.
- [ ] `W05.P08.S40` - retype the three `registry_snapshot_id` sites and the `registry_revision_id` sites onto the two new aliases; `src/cadrumo/domain/calculations/registry/`.
- [ ] `W05.P08.S41` - declare `AeatCertificadoId` as a new `IdentifierNamespace.AEAT_CERTIFICADO_ID` member and alias at the 13-digit-or-longer bound its docstring already states, and retype `RemoteNotification.certificado_id` onto it; `src/cadrumo/adapters/outbound/aeat/sede/_notifications.py`.
- [ ] `W05.P08.S42` - declare `AeatBoxNumber` as a new `IdentifierNamespace.AEAT_BOX_NUMBER` member and alias, distinct from the registry's own `CasillaId`, and retype `display_number`, `form_number`, `from_number`, and `to_number` onto it; `src/cadrumo/adapters/outbound/aeat/sede/_notifications.py`.
- [ ] `W05.P08.S43` - check whether M210's `official_tipo_renta_code` catalogue is already enumerated in registry TOML; `if so, declare a `StrEnum` sourced from that catalogue rather than re-declaring the values, and retype the five sites onto it, explicitly NOT as an `IdentifierNamespace` member; `src/cadrumo/domain/modelos/_calculation_revision.py`.
- [ ] `W05.P08.S44` - declare `M720OperationKindCode` and `M720AssetClassCode` as `StrEnum`s in `core/` sourced from registry TOML if enumerated there, and retype `operation_kind_code` / `asset_class_code` onto them, explicitly NOT as `IdentifierNamespace` members; `src/cadrumo/domain/modelos/`.

## Wave `W06` - Tax-identity split

Applies the `SubjectTaxId` versus `TaxIdIdentityToken` split this ADR
decided across the 27 tax-identity-shaped sites, neither type used at any
of them today. Independent of Waves `W02`-`W05`; depends only on `core/identity`
already existing (it does).

### Phase `W06.P09` - self and profile-owned tax identity

Retypes the filer's-own and declared-family-member tax-identity fields onto
the checksum-enforced `SubjectTaxId`. Typing constrains SHAPE only, never
cross-field agreement (ADR Consequences); this Phase's Step therefore also
audits for the missing invariant, not only the missing type.

- [ ] `W06.P09.S45` - retype every classified `tax_id` and `spouse_tax_id` pydantic model field onto `SubjectTaxId` as ONE atomic commit, EXCLUDING `ModeloDraft.profile_tax_id`/`.subject_tax_id` at `domain/filing/_schema.py:261,265` which already carry this alias, per-file enumeration recorded in the Step record reconciled against the Reference's "Classification census" section; `src/cadrumo/`.
- [ ] `W06.P09.S62` - for every model retyped in `W06.P09.S45` that holds more than one tax-identity field meant to name the same party, check whether it already carries a cross-field consistency validator (the pattern is `ModeloDraft._enforce_draft_invariants` at `domain/filing/_schema.py:290`); `add one where missing, and record in the Step record every model checked and its disposition; `src/cadrumo/`.

### Phase `W06.P10` - counterparty-facing tax identity

Retypes counterparty-facing tax-identity fields onto the checksum-free
`TaxIdIdentityToken`, preserving the ability to hold a non-resident
counterparty's identifier.

- [ ] `W06.P10.S46` - retype every classified `supplier_tax_id`, `customer_tax_id`, `party_tax_id`, `counterparty_tax_id`, `donor_tax_id`, and `member_tax_id` pydantic model field onto `TaxIdIdentityToken` as ONE atomic commit, per-file enumeration recorded in the Step record reconciled against the Reference's "Classification census" section; `src/cadrumo/`.
- [ ] `W06.P10.S47` - add a roundtrip regression proving a non-Spanish-shaped counterparty tax id (a real EU VAT-shaped value) still validates under `TaxIdIdentityToken` after the retype, guarding against the split being applied backwards; `src/cadrumo/core/identity/tests/`.
- [ ] `W06.P10.S63` - for every model retyped in `W06.P10.S46` that holds more than one tax-identity field meant to name the same counterparty, check whether it already carries a cross-field consistency validator; `add one where missing, and record in the Step record every model checked and its disposition, per the same shape-versus-agreement limit named in the ADR Consequences; `src/cadrumo/`.

## Wave `W07` - Free-text documentation and denominator second pass

Documents the three free-text sub-populations without retyping them, and
runs the noun-vocabulary second-pass sweep the amendment requires before
the census can be treated as complete enough to gate the ratchet's initial
baseline.

### Phase `W07.P11` - free-text categorisation and second-pass sweep

TODO: Phase intent paragraph required by the convention ADR.

- [x] `W07.P11.S48` - document the three free-text sub-populations (AEAT-bounded prose, counterparty-issued document numbers, externally-controlled non-AEAT identifiers) as a code comment on `IdentifierNamespace` naming representative fields for each, explicitly stating none are namespace members; `src/cadrumo/core/identity/_namespace.py`.
- [x] `W07.P11.S49` - author and run `dev/identifier_noun_census.py`, an AST sweep matching field docstrings against a noun-vocabulary heuristic (`identificador`, `clave`, `número`, `referencia`) independent of the original suffix heuristic that missed `clave_liquidacion`; `commit the script AND its output table (every match, file, line) into this Step's execution record as the named gate proving the sweep ran, not merely that it should; `dev/identifier_noun_census.py`.
- [x] `W07.P11.S50` - triage the second-pass sweep's findings from `W07.P11.S49` into the existing namespace set, a new namespace, or an explicit non-identifier exclusion, recording the disposition of each; `src/cadrumo/core/identity/_namespace.py`.

## Wave `W08` - Storage key-composition redesign and external-contract pinning

Resolves the object-key-grammar pre-hash inconsistency deliberately, bounded
strictly to Cadrumo's own databases via the app's own teardown authority,
and pins the MCP/CLI external contract the wire census found otherwise
uncovered. Depends on Waves `W02`, `W04`, `W05`, `W06` having landed (so the
namespaces feeding key composition and the schemas being pinned already
carry their final types).

### Phase `W08.P12` - object-key-grammar decision

TODO: Phase intent paragraph required by the convention ADR.

- [ ] `W08.P12.S51` - decide, and record the reason, whether every PII-shaped fold-in in `object_key_grammar` (`{member_nif}`, `{perceptor_nif}`, `{perceptor_tax_id}`) is pre-hashed uniformly or intentionally left raw beneath the outer `HashedLookup` HMAC, given the column is deterministically hashed either way; `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`.
- [ ] `W08.P12.S52` - apply the `W08.P12.S51` decision to every `SecureObjectNamespaceDefinition.object_key_grammar` declaration that currently diverges from it; `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`.
- [ ] `W08.P12.S53` - discard and re-derive the affected Cadrumo profile databases via `resume_config_reset` / `BucketMaintenanceService.delete` for any namespace whose rendered key changed, never a filesystem-level delete; `src/cadrumo/application/config_reset.py`.
- [ ] `W08.P12.S54` - record the operator re-authentication step (Cl@ve Móvil) required to re-acquire the discarded live captures as an explicit OPERATOR action in the Step record, not an automated action; `.vault/exec/`.

### Phase `W08.P13` - golden-schema pinning for the external MCP/CLI contract

TODO: Phase intent paragraph required by the convention ADR.

- [ ] `W08.P13.S55` - enumerate every registered `OutputSchema` class carrying an identifier field this plan retyped, cross-referenced against the wire census's roughly-fifty-class sweep; `src/cadrumo/entrypoints/cli/`.
- [ ] `W08.P13.S56` - add a golden-schema pinning test capturing each enumerated class's `model_json_schema()` output (the CLI envelope shape) and, for classes backing an MCP tool, the MCP `output_schema` from `_output_schema_for`, asserting the pinned constraints match the enrolled type; `src/cadrumo/entrypoints/mcp/tests/`.
- [ ] `W08.P13.S57` - confirm `test_json_schema_conformance.py`'s existing key-parity gate still passes and add a note in its module docstring cross-referencing the new content-pinning test, since the existing gate self-describes as structural-shape-only; `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`.

## Wave `W09` - Ratchet gate and closeout

Adds the structural enrollment gate that keeps the taxonomy from decaying
as new identifier-shaped fields are added, proves the gate's own bite, and
records every surface this plan deliberately left unenrolled. Depends on
every prior Wave landing first, so the gate's enrolled baseline reflects
the full staged taxonomy rather than a partial one.

### Phase `W09.P14` - structural enrollment gate and closeout recording

Delivers the property-keyed ratchet test and makes the plan's own known
gaps explicit rather than implied-complete.

- [ ] `W09.P14.S58` - author the identifier-enrollment ratchet test asserting every production pydantic field whose name matches the namespace vocabulary carries a `core.identity` namespace alias rather than bare `str`, with `Declaracion.estado`, `Deuda.situacion`, and the three free-text sub-populations from `W07.P11.S48` as named, documented exclusions; `src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py`.
- [ ] `W09.P14.S59` - prove the gate's bite: add a throwaway bare-`str` field named to match the namespace vocabulary on a scratch model outside `src`, confirm the gate reds, then remove it and confirm the gate is green again; `src/cadrumo/tests/test_identifier_namespace_enrollment_gate.py`.
- [ ] `W09.P14.S60` - record NRC, fixed-width fichero-BOE tax-id width (owned by the separate Modelo 200 misattribution ADR), registry TOML id-shaped values (no measured denominator), and any second-pass finding from `W07.P11.S49` not triaged into an enrolled namespace as explicit deferred follow-ups in this plan's Verification section, each with a named next reference rather than a silent close; `.vault/plan/2026-08-07-canonical-identifiers-plan.md`.

## Parallelization

Waves `W01` -> `W02` -> `W03` are sequenced as originally decided. `W04`,
`W05`, and `W06` each depend only on `W01` and are mutually independent of
each other and of `W02`/`W03` (disjoint files, disjoint namespaces), so may
run in parallel once `W01` closes. `W07` is independent of every other Wave
and may run at any time after this plan is approved. `W08` depends on
`W02`, `W04`, `W05`, and `W06` all having landed, since it re-derives
storage keys built from namespaces those Waves finalise and pins schemas
those Waves retype. `W09` depends on every other Wave. Within a Phase,
Steps retyping disjoint files may be parallelized per the no-compression
rule's file-level granularity; Steps sharing one file stay sequential to
avoid contended edits.

**Release condition:** every Wave is held pending the current executors
closing out the in-flight tree churn, not because the plan is unready.
Every Step re-verifies its target file(s) against current HEAD immediately
before editing, per `W01.P01`'s note, since this plan's file lists were
gathered at authoring time and the tree is expected to have moved by
execution time.

**Correction (2026-08-10): the parallelism claimed above is not available, and
acting on it would collide.** The section asserts that `W04`, `W05` and `W06`
are mutually independent of each other and of `W02`/`W03` on the grounds of
"disjoint files". They are disjoint in their CONSUMERS. They are not disjoint
in their PRODUCER: every enrollment Wave declares or promotes an alias into
`src/cadrumo/core/identity/__init__.py`, so every Wave's atomic commit contains
that one file.

Two executors given different Waves would therefore contend on the facade
rather than on the packages the Waves name, and neither could take a clean
pathspec commit — the facade would carry both their edits. The same applies to
the five `W01.P01` relocation commits, each of which promotes its symbol into
the same file.

The practical consequence, which supersedes the ordering above: **the
enrollment Waves serialize on the facade.** They may still be *planned*
independently, and their consumer sweeps genuinely are disjoint, but they must
LAND one at a time. The ratified execution order is `W02.P02`, then the
`W01.P01` relocations in ascending blast-radius order, then `W02.P03`.

This is recorded rather than silently worked around because the original claim
reads as a licence to fan the Waves out across several executors, and it is the
first instruction a future reader would act on.

**A second correction to the Release condition below it:** the condition states
every Wave is held pending in-flight tree churn. That hold was revoked on
2026-08-10. Deferring a Wave because another campaign holds a path strands the
work permanently, since no other campaign will close this plan's rows — the
contended path is a technique problem, answered by building each edit from
`git show HEAD:<path>` and staging a HEAD-anchored own-only patch, never by
waiting. Measured per symbol at execution time, the contention the hold was
protecting against was one dirty consumer file, not the twenty the aggregate
suggested.


## Verification

The plan is complete when every Step above is closed (`- [x]`) and:

- The full roundtrip and anti-tautology suites for every retyped model
  (`W01.P01.S04`, `W02.P02.S10`, `W02.P03.S21`, `W04.P06.S34`,
  `W06.P10.S47`) pass.
- The ratchet gate (`W09.P14.S58`) is green against the fully-enrolled
  baseline and its bite proof (`W09.P14.S59`) is recorded in that Step's
  execution record.
- `matches_filing_target` still has NO `presentation_id` parameter, and the
  existing refusal test that raises `TypeError` on one continues to pass. The
  original criterion here required that parameter to type-check under a
  narrowed type. It was retired with `W03.P04.S26` by the 2026-08-10 amendment
  to the governing ADR: the sibling record removed the parameter outright and
  rejected the typed marker as superseded, so the absence is the guard and
  reintroducing the parameter in order to type it would roll back an accepted,
  landed fix.
- The CSV shape-conformance regression (`W02.P03.S22`) passes at both
  boundaries of the adopted bound, AND the corpus sidecar roundtrip regression
  stays green across all 60 parser-anchor fixtures. That second condition is
  the control, not background: it is the measurement that the tightened bound
  still admits the legitimate population. The criterion previously recorded
  here said no real-captured fixture exists, none is obtainable, and the
  original demand was therefore unmeetable. That is withdrawn as falsified:
  the fixtures carry 34 distinct CSV tokens, the roundtrip regression already
  asserts uppercase-alphanumeric and a length between 8 and 24 on every parsed
  fixture in the default lane, and three real captured values are recorded in
  this vault's research and audit records.
- The discriminated expediente pair (`W02.P02.S09`, `S10`) closes only when its
  population control (`W02.P02.S65`) passes, with the count of rows exercised
  per path recorded. The new refusal firing is not the close condition.
- Every golden-schema pinning test from `W08.P13.S56` passes, and the
  `test_json_schema_conformance.py` structural gate still passes.
- Every Step whose action names a per-namespace batch (`W04.P06`,
  `W06.P09`, `W06.P10`) carries a file enumeration in its execution record
  reconciled against the Reference's "Classification census" section, and
  landed as one atomic commit per Step.
- Every discarded Cadrumo profile database from `W08.P12.S53` was
  re-derived through `resume_config_reset` / `BucketMaintenanceService.delete`
  only, confirmed by inspection of the Step's execution record, never a
  filesystem-level delete.

**Explicitly deferred, not covered by this plan's completion** (recorded
per `W09.P14.S60`): NRC capture and persistence (no existing field to
retype); fixed-width fichero-BOE tax-id width (owned by the separate
Modelo 200 misattribution ADR, must not be touched here); registry TOML
id-shaped values (architecturally clean per the wire census, but no
measured denominator equivalent to the Python count); any second-pass
sweep finding (`W07.P11.S49`) not triaged to a disposition by
`W07.P11.S50`; and the enrollment of `resolve_identifier_namespace`, which
is held behind `W03.P04.S64` pending a first real consumer and may resolve
to dropping the resolver and its enum rather than landing them. A future
plan referencing this one's ADR is the sanctioned next step for any of
these, not a silent assumption that this plan's closure covers them.
