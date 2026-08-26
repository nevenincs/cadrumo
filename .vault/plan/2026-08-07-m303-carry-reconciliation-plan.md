---
tags:
  - '#plan'
  - '#m303-carry-reconciliation'
date: '2026-08-07'
modified: '2026-08-10'
body_hash: 'sha256:05acc31eabaaaafb8f289560e4b7da876c07dadfe9d003d3b16eac6398530448'
tier: L1
related:
  - '[[2026-06-21-m303-carry-reconciliation-adr]]'
  - '[[2026-08-09-m303-carry-reconciliation-prior-domiciliation-s21-reference]]'
---
# `m303-carry-reconciliation` plan

Close the two reach-and-duplication findings a code review raised against the
refunded-aware carry fix, without touching its arithmetic.

## Description

The review of the Modelo 303 refunded-aware carry fix returned REVISION
REQUIRED on two grounds, neither of them about the figures. The money
arithmetic, the legal grounding and the absent-posterior reading all checked
out under execution: the identity `available == posterior + generated` holds on
every branch, and the governing ADR says verbatim what the fix claims, with
RD 1624/1992 art. 30 and Ley 37/1992 art. 116 both present. This plan does not
reopen any of that.

The first finding is that the repaired drift gate watches a hand-listed tuple
of three modules. The gate's own stated reasoning for replacing an import
inventory was that an inventory asserts something the code is free to change,
and that reasoning applies verbatim to its own subject list. Nine twin
declarations of the compensation vocabulary survive outside the watched set,
three of them in the module that sits on the live local filing path. Rename the
end-of-period available casilla in a later revision and the watched modules get
rebound while that module keeps resolving its stale literal, so the refunded
rewrite silently stops finding the row it must re-stamp and a refunded period
carries its full generated credit into the next quarter with no gate red. That
is the exact drift the gate is named for, one module over. Step `S01` replaces
the subject list with discovery and rebinds the twins.

The second finding is that the same live local filing module encodes the
refunded rule by hand rather than through the derivation this fix made
canonical, so a regulatory change lands in one place and not the other. It also
rewrites only the value, leaving the formula id, operand refs and operand
values intact, so a refunded local observation asserts the provenance
`87 + generada` beside a posterior-only figure. The sede path does the
deliberate opposite and refuses when refs and formula disagree, so two paths
handle one case incompatibly and the local one ships a provenance claim its own
figure contradicts. Step `S02` routes it through the canonical derivation and
drops the contradicted provenance.

Step `S03` removes an algebraically vacuous assertion in the derivation's own
disposition test, where `generated` is defined as `available - posterior` on the
resultado basis and the identity therefore cannot fail. Step `S04` records four
deferred findings as follow-up rows without implementing them.

One correction the plan carries forward: the existing compensation tests are
NOT grounded parity. Their fixtures are synthetic hand-built observed-casilla
rows with authored figures; what is real is the shape, the canonical casilla ids
and the source locators naming the official boxes. They are legitimate wiring
and invariant coverage, but they would not fail if the AEAT formula were wrong.
No Step here may describe them as grounded, and no new test may manufacture
decimal expectations and call itself parity.

## Steps

- [x] `S01` - Discover token-naming modules by AST scan instead of a hand-listed tuple, and rebind the nine surviving twin declarations to the authority; `src/cadrumo/application/calculations/tests/test_iva_compensation_casillas.py src/cadrumo/application/calculations/__init__.py src/cadrumo/application/calculations/_iva_compensation_annual_partition.py src/cadrumo/application/modelo/_filed_revision_observation.py src/cadrumo/application/modelo/_iva_wallet_gate.py`.
- [x] `S09` - Rebind the four further twin literals discovery found in the registry binding validator, which a hand-listed inventory of nine had also missed; `src/cadrumo/domain/iva_compensation/_filed_derivation.py src/cadrumo/domain/iva_compensation/__init__.py src/cadrumo/domain/calculations/registry/_bindings.py src/cadrumo/application/calculations/_iva_compensation_casillas.py`.
- [x] `S02` - Route the local filing path refunded rewrite through the canonical derivation and drop the contradicted formula provenance to match the sede path; `src/cadrumo/application/modelo/_filed_revision_observation.py src/cadrumo/application/modelo/tests`.
- [x] `S03` - Replace the algebraically vacuous available equals posterior plus generated assertion on the resultado basis with an independent check; `src/cadrumo/domain/iva_compensation/tests/test_filed_derivation_disposition.py`.
- [x] `S04` - Record the four deferred review findings as follow-up rows without implementing them; `.vault/plan/2026-08-07-m303-carry-reconciliation-plan.md`.
- [x] `S05` - DEFERRED - report a refunded basis rather than resultado once disposition recovery from the justificante Tipo de declaracion makes the branch reachable; `src/cadrumo/domain/iva_compensation/_filed_derivation.py`.
- [x] `S06` - DEFERRED - assert the disposition-blind available reconstruction in the annual partition instead of relying on a transitive upstream rewrite in another package; `src/cadrumo/application/calculations/_iva_compensation_annual_partition.py`.
- [x] `S07` - DEFERRED - refuse a persisted compensation pair where a directly filed disponible casilla overwrites available without generated following it; `src/cadrumo/application/calculations/_iva_compensation_history.py`.
- [x] `S08` - DEFERRED - feed the recovered refund disposition into the IVA wallet gate, the fourth unimplemented implementation bullet of the governing decision record; `src/cadrumo/application/modelo/_iva_wallet_gate.py`.
- [x] `S10` - Add a standing real-site regression restoring an actual twin at every discovered module and confirming the verdict names it; `src/cadrumo/application/calculations/tests/test_iva_compensation_casillas.py`.
- [x] `S11` - Establish a sound channel for recovering the filed result disposition before S05 through S08 are attempted, and record the two mis-readings that would otherwise satisfy their precondition falsely. FIRST trap. The persisted source metadata key aeat_tipo_solicitud is NOT the disposition. Its own docstring states it distinguishes an original filing from an amendment, so it is the original-versus-complementaria axis. The Spanish nouns tipo de solicitud and tipo de declaracion are near-identical and that confusion is the likely failure. SECOND trap. The justificante parser extracts only the two printed amounts, total_a_ingresar and total_a_devolver, and carries no disposition code at all. A present devolver amount identifies DEVOLUCION, but COMPENSACION and NEGATIVA both present with neither amount, and suppressing compensacion carry-forward turns on exactly that distinction, so an amounts-based inference cannot decide the case the refund gate exists to decide. Gate. The row names the channel that actually carries the code, or records that none does and that parsing the printed Tipo de declaracion is required, and a test proves COMPENSACION and NEGATIVA stay distinguishable through whichever channel is chosen rather than collapsing to one reading; `src/cadrumo/adapters/inbound/justificante/_extract.py, src/cadrumo/domain/justificante/_schema.py, src/cadrumo/core/_result_disposition.py`.
- [x] `S12` - Surface the filed disposition from the parsed fichero, which already holds it. REFUSED shape, do not add casillas 72 and 73: the AEAT diseño declares 70, 71, 74, 75, 76 and 77 and not 72 or 73, our export layout carries exactly that set, and AEAT models the disposition as a HEADER at offset 13 plus sin-actividad at offset 391, so two casillas would disagree with the official structure about the concept's kind. THREE FINDINGS FROM THE FIRST WORK, recorded so they are not re-derived. ONE, the value is usable as-is: every field regardless of kind is read through _parse_field_value and appended as a ParsedExportFieldValue carrying raw, a decoded value and a source_locator, so a text header yields a decoded string and the projection change is small. TWO, parsed.fields today has exactly one consumer, _verify_submitted_file_context, which reads only DRAFT-kind fields to cross-check modelo, year and period, so every header field is parsed and discarded. THREE, and this is the blocking design question: NO sibling modelo represents a non-casilla fichero fact anywhere. ObservedCasillaValue requires a casilla_id, there is no ObservedHeaderValue or equivalent, and no observation path surfaces a header. Inventing the first such representation is a design decision to be taken deliberately and NOT settled inside a projection fix, so choose the representation before writing the projection; `src/cadrumo/adapters/outbound/aeat/sede/_declarations_observations.py, src/cadrumo/adapters/outbound/aeat/sede/_schema.py`.
- [x] `S13` - Recover the filed disposition from the printed declaracion render ONLY for a filing where no submitted_file artefact exists, and establish first whether that population is non-empty, because if the pull stores a submitted file for every filed modelo 303 this row has no subject and should be closed rather than built. Blocked on S12. Where the fichero is held the disposition is a direct read of the tipo de declaracion byte and no render parsing is warranted. IF the render path is taken, RECOVERY KEYS ON WHICH SLOT CARRIES A VALUE, NEVER ON A PRINTED LETTER. The C, I and D letters beside those sections are pre-printed form furniture present on all four bundled AEAT facsimiles including the two that elected ingreso, so a pattern matching the letter reports the same disposition for every filing while appearing to read the form. The pair needing separation is COMPENSACION versus DEVOLUCION, since the sign of casilla 71 already separates NEGATIVA from both through derive_result_disposition. Counts to state precisely rather than repeat: ResultDisposition declares TEN members, of which AEAT's modelo 303 diseño admits EIGHT, and the two the enum adds belong to other modelos. Unproven on evidence and not to be asserted otherwise: no bundled facsimile elected devolucion and none filed sin actividad, so box 73 and the sin-actividad flag have proven slots and unexercised values; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/extraction_profiles/, src/cadrumo/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/extraction_profiles/`.
- [x] `S14` - MEASURED LIMITATION, recorded so it is not re-derived per modelo. An extraction profile structurally cannot target a non-casilla record field. ExtractionProfileDefinition exposes target_casillas as its only targeting collection, and ExtractionTargetDefinition declares casilla_id as a required CasillaId with no header_key alternative, so there is no shape in which a profile addresses the tipo de declaracion at offset 13 or the sin-actividad flag at offset 391. This generalises past modelo 303 to every non-casilla header AEAT prints and encodes, which is why it is its own row rather than a note on the M303 work. Decide the representation before any extraction change: either widen the targeting model to address header fields alongside casillas, or accept that header facts are recovered from the parsed fichero rather than from a profile and route them that way. The fichero route needs no schema change at all, since parse_export_payload already returns the header fields and only the observation projection discards them, so widening the profile is the more expensive option and must be justified rather than assumed; `src/cadrumo/domain/calculations/registry/_schema_extraction.py`.
- [x] `S15` - Fix the fichero layout parse refusing every non-refund submitted file, and stop the silent degradation that hid it. Measured by parametrising one exporter-produced payload over four dispositions. Only DEVOLUCION parses. COMPENSACION, INGRESO and NEGATIVA all fail identically with payload ended before export record modelo-303-page-did, expected 823 got 18, because a devolucion filing carries the bank-details record AEAT needs an account to pay into and the other three do not, while the layout parser requires that record unconditionally. The consequence is far wider than the disposition. For the three most common dispositions NO field of a real submitted fichero can be read back through the layout at all, and observed_casillas_from_submitted_file degrades silently to its positional fallback instead of reporting that the layout parse failed. That silent fallback is why this was invisible. Gate. The record is optional in the layout when the disposition does not require it, a non-refund payload parses and yields its fields, and a layout parse failure surfaces as a reported failure rather than a silent fallback. Three parametrised tests currently pin the broken behaviour and MUST flip to green as part of this change rather than being deleted. Note the payloads are exporter-produced so they exercise our layout against our own writer, and no bundled AEAT specimen exists to confirm a real fichero matches; `src/cadrumo/_data/registry/aeat/modelos/303/revisions, src/cadrumo/adapters/outbound/aeat/sede, src/cadrumo/domain/calculations/registry`.
- [x] `S16` - Surface a recorded submitted-file layout refusal to the operator through the Notice channel, completing the fail-hard-and-loud directive rather than enhancing it. The refusal itself now raises with modelo, resolved revision, ejercicio, period, expediente id, artefact digest and the parser's own reason. Its single production consumer catches it and writes metadata submitted_file_extraction_error, then degrades to the declaration-PDF path. Measured. Nothing in the codebase reads that metadata key. No Notice, no CLI field, no operator surface. So the capture is strictly louder than the silent positional fallback it replaced, which produced silence plus fabricated values plus a fabricated 1.0 extraction coverage that passed the coverage gate, and it is still not loud where the operator is. Notices are the only sanctioned diagnostic channel, so the advisory belongs there and MUST NOT be a bespoke advisory or next field inside a result payload. Gate. A capture whose submitted-file layout parse fails emits an advisory Notice naming the modelo and the failed record, proven by a test that makes the parse fail and asserts the Notice reaches the envelope, with a positive control proving a successful capture emits no such Notice; `src/cadrumo/adapters/outbound/aeat/sede, src/cadrumo/application/live`.
- [x] `S17` - Stop the M303 export omitting the bank-account record on a domiciliacion filing, and separate that from the Nota 3 rectificativa case it cannot currently see. FILING-GRADE. _did_page_suppressed reads only the declaration_type header and suppresses on not result_disposition_is_refund, measured across every code as D V X not suppressed and C I N U G suppressed. U is DOMICILIACION, domiciliacion del ingreso en cuenta de cargo, and the DID field AEAT names is Domiciliacion/Devolucion - IBAN, one field serving both purposes, with the bundled diseno listing U as a payment form. So a domiciliacion filing exports with no account for AEAT to debit, a silent omission of data AEAT requires on the surface a human files from. G is deliberately NOT claimed here because cuenta corriente tributaria may legitimately settle without a debit account, and unclear is recorded as unclear rather than folded into the fix. SECOND HALF, and it is a CAPABILITY gap in the predicate's inputs rather than a threshold to adjust, so it MUST NOT be fixed by widening the disposition set. Nota 3 of the bundled diseno states that a rectificativa whose casilla 111 has content must carry bank data even when the payment form is not devolucion, except where the page-3 domiciliacion-cancellation field is marked. The predicate sees neither casilla 111 nor that marker, so it cannot express the rule at all and the inputs have to reach it. Establish before building whether casilla 111 and the page-3 marker are available at the call site or need threading from a caller that does not supply them, and report rather than widen the signature blind. Grounding note. required = false on the DID record is now backed by two independent AEAT signals, that only the envelope constants carry Obligatorio on the DID page while every data field's Validacion is blank, and that the record total of 823 POSICIONES matches the figure the layout parse reported. Gate. A domiciliacion export carries the account record, a devolucion export is unchanged, and a non-refund non-domiciliacion export still omits it, each proven against an exporter-produced payload rather than a byte count; `src/cadrumo/application/filing, src/cadrumo/core`.
- [x] `S18` - Record a charge account on the profile so a domiciliacion del ingreso can be exported at all. This is the capability the export refusal currently stands in for. Measured. The profile carries exactly one bank account, RefundAccount, whose own docstring calls it the cuenta-devolucion account AEAT pays a Modelo 303 refund INTO, and a search of the export path found no charge or cargo account concept anywhere, only an AEAT portal catalogue entry for the domiciliacion procedure page. So a U election cannot be exported truthfully today and the export refuses rather than reusing the refund account, because a refund account is where a taxpayer receives money and not an authorisation to debit them. AEAT's record design carries ONE dual-purpose IBAN field at position 23 labelled Domiciliacion/Devolucion - IBAN, which means the record has somewhere to put a charge account, NOT that the two accounts are the same account. That distinction is exactly why reusing the refund account was tempting and is wrong. Note the domiciliacion needs an IBAN specifically rather than any account, since the SWIFT-BIC and foreign-bank fields on that page are each labelled Devolucion - and have nowhere to be stated for a charge. Gate. A profile can record a charge account, a U export emits the account page carrying that IBAN and nothing else from the page, a U export with no charge account still refuses, and a refund export is unchanged; `src/cadrumo/domain/deadlines, src/cadrumo/application/user_profile, src/cadrumo/application/modelo`.
- [x] `S19` - Express Nota 3, the rectificativa case the account-page guard structurally cannot see. CAPABILITY gap in the predicate's inputs, NOT a threshold to widen, and it MUST NOT be fixed by adding dispositions to the account-bearing set because the rule is not about the disposition at all. Nota 3 of the bundled diseno states that a rectificativa whose casilla 111 has content must carry bank data even when the payment form is not devolucion, except where the page-3 domiciliacion-cancellation field is marked. The guard reads only the declaration_type header, so it sees neither casilla 111 nor that marker and cannot express the rule in any form. Threading already established, so this does not need discovery. Both production call sites hold a draft. rendered_casilla_ids and assert_export_mirrors_manifest each take draft, and the renderer builds casilla_values from draft.values two lines above its suppression call. What needs widening is boe_representable_casilla_ids, which takes only layout, headers and schema_provider, plus roughly thirteen test call sites. The inputs MUST reach BOTH sides rather than the renderer alone, because the shared predicate exists so the renderer and the parity assertions cannot disagree about what reaches disk, and fixing one side reintroduces exactly that class of defect. Gate. A rectificativa with casilla 111 populated and the cancellation marker unset carries the account page on a non-devolucion payment form, the same filing with the marker set does not, an ordinary non-rectificativa filing is unchanged, and the renderer and the parity derivation agree on all three; `src/cadrumo/application/filing`.
- [x] `S20` - Introduce the canonical positive-result PaymentElection axis, replace the ambiguous CLI disposition option, thread I/U/G choice through export and quickfile with safe receipt/event provenance, keep G capability-refused, and prove public U export reaches the distinct charge-account DID composer; `src/cadrumo/core/, src/cadrumo/application/modelo/, src/cadrumo/application/filing/, src/cadrumo/entrypoints/cli/, src/cadrumo/locales/`.
- [x] `S21` - Model the prior-domiciliation KEEP versus CANCEL_OR_MODIFY filing election with baseline-U provenance, split the M303 2023-2025 and 2026 registry layouts at their official page-3 offsets, and thread the safe semantic election through public filing surfaces so S19 can apply Nota 3 without inference; `src/cadrumo/core/, src/cadrumo/_data/registry/aeat/modelos/303/revisions/, src/cadrumo/application/modelo/, src/cadrumo/application/filing/, src/cadrumo/entrypoints/cli/, src/cadrumo/locales/`.

## Parallelization

`S01` and `S02` both edit the local filing observation module and carry a hard
ordering: `S01` rebinds its casilla constants to the authority and `S02` then
consumes the canonical derivation that names those same constants, so `S01`
lands first. `S03` touches only the domain disposition test and is independent
of both. `S04` is documentation-only and independent.

Each of `S01` and `S02` is one atomic commit. Within `S01` the gate and the
rebinding cannot be split: the gate reds until the twins are rebound, so both
halves must be present in the working tree simultaneously and land together.

## Verification

The plan is complete when every Step is closed and each of the following holds.

The drift gate names no module list and no module count: its subjects are
discovered from the source tree, and adding a tenth twin in a module no one
edited today reds it. The gate's per-module non-vacuity guard survives, so a
module naming nothing cannot pass silently. The documented CPython
short-literal interning limitation stays recorded honestly, because a twin of
the bare-numeric token is the same object and identity cannot discriminate
there.

No production module outside the declaring authority holds its own object for a
compensation casilla token. The nine surviving twins are rebound, and every
cross-package consumer imports through the owning package's public facade
rather than a private module.

The local filing refunded rewrite calls the canonical derivation rather than
re-deriving the rule, and a refunded row carries no formula id and no operand
refs, matching the sede path that refuses a refs-versus-formula disagreement. A
test asserts the local and sede paths agree on the provenance shape for the same
refunded case.

Every gate added here is proven to bite: where the defect is live the assertion
is written first and observed to red against unmodified code, and where a
mutation is required it is delivered as a pytest plugin loaded from outside the
repository with `-n0` passed explicitly, since the project's addopts inject
`-n auto` and a mutation applied in the controlling session never reaches xdist
workers.

The touched modules pass in isolation with owner triage recorded against the
pre-existing unrelated reds on this tree, which are not remediated here.
