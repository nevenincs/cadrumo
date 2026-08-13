---
tags:
  - '#plan'
  - '#aeat-liabilities-sanciones'
date: '2026-08-07'
modified: '2026-08-13'
body_hash: 'sha256:e58722dcf96334447f8ffa2591aa8873441b071c385bee393cfe9a01c4e7f105'
tier: L2
related:
  - '[[2026-08-07-aeat-liabilities-sanciones-adr]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-research]]'
  - '[[2026-08-13-aeat-liabilities-sanciones-notification-documents-adr]]'
  - '[[2026-08-12-aeat-liabilities-sanciones-p05-p06-closeout-honesty-audit]]'
---

# `aeat-liabilities-sanciones` plan

## Description

This plan executes a cluster of two decisions against one standing goal - an
operator can see, inside the application, what AEAT reports as owed - reached
through two different AEAT registers.

`2026-08-07-aeat-liabilities-sanciones-adr` governs Phases **P01 through
P07**: a read-and-display `Deuda` register mirroring `ExpedientesService`
structurally, never a calculation input, gated by a fail-closed read-landing
guard given its adjacency to AEAT's payment flow. Grounded throughout by
`2026-08-07-aeat-liabilities-sanciones-research`.

`2026-08-13-aeat-liabilities-sanciones-notification-documents-adr` governs
Phases **P08 through P12**: fetching, encrypting, parsing and displaying the
notification documents in which this taxpayer's liabilities actually sit.
Grounded by `2026-08-12-aeat-liabilities-sanciones-p05-p06-closeout-honesty-audit`,
which established with a same-session positive control that the recaudación
register the first decision reads is genuinely empty while the liabilities
themselves are real and served one procedural stage earlier.

Phases P01-P04 and P07 are **closed**, each with a matching execution
record: the domain type and its closed enums, the snapshot service, the
guard skeleton shipped refusing by construction, the list/view/latest CLI
read surface, and real es/en/ca/hu values for its help and label keys. None
of them touched AEAT, none needed a specimen, and none needed new legal
grounding, because they display AEAT's own reported figures without
interpreting them. The P07 blocker - in-flight `en.yml`/`hu.yml` peer WIP -
was discharged when that WIP landed; the row closed with the rest of the
CLI unit, as its own text records.

**What the closed set still owes against this plan's standing goal.** The
goal is that an operator can see, inside the application, what AEAT
currently reports as owed. What P01-P04 deliver is the shape of that
register, not its contents: `_DEUDAS_READ_PATH_PREFIXES` is the empty tuple,
no `walk_deudas_consulta` exists, no `pull` verb exists, and `app live deudas
pull` appears in neither `PROFILE_BOUND_WRITE_VERB_PATHS` nor the
operator-orientation harness document. An operator today gets three verbs
over zero rows. That is the honest interim state the governing ADR named
("the feature ships visibly incomplete until a specimen exists"), and
closing thirteen rows does not move the goal - it leaves the goal entirely
behind Phase P05.

Phase P05 is blocked end-to-end on an operator-authorised live specimen
capture of "Consultar deudas" and is not startable before then; it carries
the DOM parse function, the guard's real allowed prefixes, the `pull` verb,
its write-guard enrollment, and the harness sweep together because each
depends on the same capture. Until that capture exists the guard's empty
prefix tuple is the correct posture, not a gap: it refuses every landing,
and a specimen-dependent row can only narrow the refused surface, never
widen it by omission.

Phase P06 is blocked on named human legal reviewers per
`aeat-calculation-grounding`'s human-reviewed mandate; an agent must never
author these entries. That block is deeper than reviewer assignment alone:
none of LGT arts. 28, 65, 82, 163, 167-173 or 178-212 is bundled under
`src/cadrumo/_data/corpus/normatives/html/`, so the corpus must be fetched
and live-cross-checked against BOE before a human review is even possible.

Divergence reconciliation against filed declarations (the ADR's rejected
option 2) is out of scope for this plan and requires its own ADR once P05
ships and a real specimen exists to validate a comparison against.

**Correction (2026-08-10): the deeper half of the P06 block is discharged.**
The paragraph above states that none of LGT arts. 28, 65, 82, 163, 167-173 or
178-212 is bundled, so the corpus must be fetched before a human review is even
possible. That was accurate and is now out of date: the consolidated Ley 58/2003
is bundled, acquired from BOE through the sanctioned maintainer acquirer rather
than by hand, with its extracted sidecar. All 46 of those articles are present
and verified against the written file and the sidecar independently of the
acquirer's own check. Eleven per-article Ley 58/2003 excerpts were already
bundled and none of them covered the range these rows need, which is why the
absence was real rather than a search failure.

What that changes, stated narrowly. P06 is no longer blocked on two things. It
is blocked on ONE: a named human legal reviewer. The corpus dependency in each
row's scope clause is satisfied, and a `corpus_ref` now has a bundled
consolidated target to resolve against instead of a file that had to be created
first.

What it does NOT change. An agent still may not author or stamp these entries,
and `review_status` still may not be self-stamped. The live cross-check on any
numeric amount or rate is still owed and is part of the review rather than of
the acquisition: the payload was fetched from BOE and its served version is
asserted per bloque, but the standing grounding rule distrusts any bundled text
on a number, and the reviewer's reading is what discharges that. Retiring the
per-article excerpts in favour of the consolidated file is a separate question
this correction deliberately does not settle.

**Correction (2026-08-12): the P05 specimen block is discharged in part, and
what replaced it is a different blocker.** The paragraph above states that P05
is blocked end-to-end on an operator-authorised live specimen capture and is not
startable before then. An authenticated Cl@ve Móvil discovery session has now
run against the live sede, so that sentence is out of date - but only for the
rows the capture actually grounds.

What the capture established, and S15 consumed: the consulta path (now a
declared sede path rather than a feature-module literal); that *pagar todas mis
deudas* is served from the SAME AEAT application as the consulta, which is why
the allow-list names the endpoint and never the shared prefix; that the consulta
is a two-step surface whose listing exists only behind a POST query, admitted
through the same scoped mechanism the IVA wallet reader uses; the three further
payment and aplazamiento launchers beside it; that the surface is served as
ISO-8859-15; and that a retrieval failure surfaces as an error line naming the
NIF.

What the capture could NOT establish, and why the block moved rather than
lifted: this taxpayer has **no outstanding deudas**. That is an observation, not
an assumption - an invalid NIF drew AEAT's retrieval error while the valid query
re-rendered the form byte-identically apart from the clock, which proves the
form processes and the empty result is real. So the zero-state is now observed
and the populated listing is not: no row DOM, no `situacion` label vocabulary,
no importe or periodo formatting.

**S13, S14, S16, S17 and S18 therefore stay open, and the reason has changed
from absent ACCESS to absent DATA.** They are unblocked the moment a listing
with rows can be observed - either because a deuda arises, or under a
representation the operator holds for a taxpayer who has one. Neither is
something this campaign can schedule.

**What the standing goal still asks for that this excludes.** The goal is that
an operator can see, inside the application, what AEAT currently reports as
owed. S15 hardens the wall around that read; it does not perform it. There is
still no `walk_deudas_consulta`, no `pull` verb, no write-guard enrollment and
no harness entry, so an operator today still gets three verbs over zero rows.
Closing S15 moves the guard from refusing everything to refusing everything
except one endpoint nothing yet navigates to. That is real progress on safety
and none on the goal, and the two must not be confused at closeout.

**Correction (2026-08-12, second): the "no outstanding deudas" reading is
withdrawn.** The correction above concluded that the remaining P05 rows are
blocked because this taxpayer has no outstanding deudas, and called that
established rather than assumed. It is withdrawn.

The negative control it rested on - an invalid NIF drawing AEAT's retrieval
error while the valid query re-rendered the form - proves the form PROCESSES a
submission. It does not separate "no debts" from "the listing did not render for
another reason". Both the consulta form and its result carry an AEAT banner
instructing the user to access pending notifications *before continuing*, which
was dismissed as page furniture; and the operator has since stated there are
many late filings with debts and penalties set out in the messages.

The rows stay open, but the recorded reason changes from "blocked on data that
does not exist" to "blocked on a listing not yet reached, for reasons not yet
established" - unfinished investigation rather than unschedulable work.

The next step is NOT for an agent to act on alone. Accessing an electronic
notification is the moment it is deemed served and starts the appeal and payment
clocks, which for a taxpayer with late filings and pending penalties is an
irreversible act on their legal position. The notifications LIST surface carries
no such effect and is the only side that may be read without an explicit
operator decision.

**Reopened 2026-08-13 at the operator's explicit ask, with a second governing
decision and five new Phases.** The plan closed at 23/23 with five of those
checkboxes recorded as deferred carry-forward rather than deliveries. Nothing
about that record changes: `P05.S13`, `S14`, `S16`, `S17` and `S18` stay closed
as deferred, the recaudación register stays empty, and no row below claims
otherwise. What changes is that the goal turns out to be reachable without them.

The constraint the paragraph above states - that an agent must never access an
unread electronic notification - is not relaxed by the new Phases. It is
promoted into a binding invariant by the second governing decision and expressed
in code as a predicate that admits only rows AEAT already reports as read. Every
Phase from P08 onward operates strictly inside it, and refusing a notification
that is already SERVED but still unread is deliberate: service and reading are
different events, and only the second licenses the fetch.

**What P08 through P12 do NOT deliver against the standing goal.** They surface
what AEAT has *served* on notifications the taxpayer has already opened. They do
not surface the recaudación register, they cannot see an unread notification,
and they state no total and no payable balance. So an operator finishing this
plan still cannot answer "what do I owe in total, right now" from inside the
application - they can answer "what has AEAT told me, in documents I have
already opened". That is a genuine advance on zero and it is not the whole goal;
the five deferred P05 rows remain the backlog for the rest.

## Steps

### Phase `P01` - Deuda domain type and closed enums

Land the Deuda adapter schema model and its closed ObjetoTributario and Direccion StrEnums in core, buildable and testable with no AEAT specimen and no new legal grounding. situacion ships a bounded str from birth, following the Declaracion.estado precedent, not a StrEnum, because it mirrors an AEAT free-text listing label the app does not control rather than an axis the app defines.

- [x] `P01.S01` - Add the closed ObjetoTributario StrEnum (interes de demora, recargo de apremio, sancion, liquidacion, other) to core, never reused or widened from PostFilingEventKind, verified by a new unit test asserting the closed member set; `src/cadrumo/core`.
- [x] `P01.S02` - Add the closed Direccion StrEnum (owed, refundable) to core as its own typed axis rather than a sign, mirroring the ledger contract amount-is-magnitude convention, verified by a unit test; `src/cadrumo/core`.
- [x] `P01.S03` - Add the Deuda adapter schema model in a new _deudas.py module mirroring Expediente placement and STRICT_FROZEN_CONFIG, with clave_liquidacion, objeto_tributario, importe_pendiente as a non-negative Decimal, direccion, periodo, situacion as a bounded str following the Declaracion.estado precedent (never a StrEnum), and mode Literal read, verified by a model validation unit test; `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`.

### Phase `P02` - DeudasService snapshot family

Mirror ExpedientesService/PersistedExpedientesSnapshot/ExpedientesCapture exactly for deudas, with a bucket-scoped namespace and content-addressed snapshot ids, roundtrip-tested against a synthetic capture fixture.

- [x] `P02.S04` - Add the LIVE_DEUDAS_SNAPSHOT_NAMESPACE bucket-scoped namespace constant beside LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE; `src/cadrumo/adapters/persistence/storage`.
- [x] `P02.S05` - Add DeudasCapture, PersistedDeudasSnapshot, deudas_snapshot_object_key and _derive_snapshot_id mirroring the ExpedientesCapture/PersistedExpedientesSnapshot pattern exactly; `src/cadrumo/application/live/_deudas.py`.
- [x] `P02.S06` - Add DeudasService extending StatelessSnapshotService with capture, list_snapshots, show and latest verbs, structurally read-only by construction with no method that mutates AEAT state; `src/cadrumo/application/live/_deudas.py`.
- [x] `P02.S07` - Write the strict roundtrip test against a real SecureObjectRepository, real key provider and real SQLite engine, populate every defaultable field non-default, assert strict pydantic equality, then the anti-tautology proof deleting a persisted field on disk and asserting reload refusal; `src/cadrumo/application/live/tests/test_deudas_service.py`.

### Phase `P03` - Fail-closed read-landing guard skeleton

Land the guard function modelled on the censal reader's _assert_read_landing, shipped with an empty/refusing allowed_path_prefixes tuple so it fails closed by construction before any adapter fetch function exists.

- [x] `P03.S08` - Add the deudas read-landing guard modelled on the censal reader _assert_read_landing, shipped with an empty refusing _DEUDAS_READ_PATH_PREFIXES tuple so it fails closed by construction before any fetch function exists; `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`.
- [x] `P03.S09` - Write the guard unit test proving refusal on every synthetic landing URL including a payment-shaped and an aplazamiento-shaped URL against the empty prefix set, then a mutation proof populating one real-looking prefix and confirming it permits only that prefix; `src/cadrumo/adapters/outbound/aeat/sede/tests/test_deudas_read_landing_guard.py`.

### Phase `P04` - CLI read surface: list, view, latest

Expose aeat app live deudas list/view/latest over persisted snapshots, matching the expedientes verb shape exactly; needs no specimen since it reads only what has already been captured.

- [x] `P04.S10` - Add the deudas CLI entrypoint and its list, view and latest payload models as new OutputSchema subclasses in the existing _app_live_payloads module, mirroring the expedientes payload shapes. Introduces tr help keys, so this row and S11 and S12 land as ONE unit with P07.S23 rather than independently: the codebase-to-locale parity gate is tree-wide and immediate, so the moment a tr key exists in source it must exist in all four catalogues; `src/cadrumo/entrypoints/cli/_app_live_deudas_cli.py, src/cadrumo/entrypoints/cli/_app_live_payloads.py`.
- [x] `P04.S11` - Wire aeat app live deudas list, view and latest into the app live command group, matching the expedientes latest, list, view verb shape exactly; `src/cadrumo/entrypoints/cli`.
- [x] `P04.S12` - Add the three new leaves to the reviewed-non-mutating roster as pure reads over persisted snapshots, verified by test_every_app_leaf_is_accounted_for_by_name_independent_census and a new CLI integration test asserting the three verb shapes; `src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py`.

### Phase `P05` - Specimen-blocked: adapter parse, pull, write-guard enrollment

Wire the live AEAT fetch once an operator authorises a specimen capture: the DOM-to-Deuda parse function, the guard real allowed_path_prefixes, the pull CLI verb, its PROFILE_BOUND_WRITE_VERB_PATHS entry, and the operator-orientation harness sweep. Every row here is blocked until the specimen exists and is not startable before then.

- [x] `P05.S13` - BLOCKED on an operator-authorised live specimen capture of Consultar deudas: observe the real situacion label vocabulary and confirm the str Field length bound is adequate, per the Declaracion.estado precedent, with no type change since situacion stays str; `no type change, situacion stays str; `src/cadrumo/core, src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`.
- [x] `P05.S14` - BLOCKED on the same specimen: write walk_deudas_consulta mapping the real DOM to Deuda rows, verified by a parse test against the captured fixture with sensitive fields never committed to the repo; `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`.
- [x] `P05.S15` - BLOCKED on the same specimen: populate the guard real allowed_path_prefixes from the captured consulta path, verified by the guard test refusing every known payment and aplazamiento path observed in the specimen; `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`.
- [x] `P05.S16` - BLOCKED on the same specimen: wire aeat app live deudas pull calling the walker and DeudasService capture, named pull never capture or refresh or fetch or sync per the CLI contract; `src/cadrumo/entrypoints/cli/_app_live_deudas_cli.py`.
- [x] `P05.S17` - Enroll app live deudas pull in PROFILE_BOUND_WRITE_VERB_PATHS with a comment stating it persists a captured snapshot to bucket storage, verified by test_root_fallback_guard_predicate_covers_profile_bound_mutations extended with the new entry; `src/cadrumo/application/storage_write_policy.py`.
- [x] `P05.S18` - Add deudas pull to the operator-orientation agent-harness document alongside expedientes pull and notifications pull in the same commit as the verb, verified by test_documented_command_conformance; `src/cadrumo/_data/agent/rules/cadrumo-operator-orientation-routing.md`.

### Phase `P06` - Human-grounding-blocked: LGT legal-catalogue rows

Author legal-catalogue entries for the four ungrounded LGT provisions, each with a named human reviewer and a live-cross-checked BOE corpus_ref, needed only before the register interprets a legal category rather than displaying AEAT's own reported figures.

- [x] `P06.S19` - BLOCKED on a named human legal reviewer, never an agent stamp. The corpus half of this row's blocker is discharged as of 2026-08-10: the consolidated Ley 58/2003 is bundled with its extracted sidecar, so art. 28 is present and a corpus_ref has a target. Author the legal-catalogue entry for LGT art. 28, recargo del periodo ejecutivo and recargo de apremio, pointing corpus_ref at the bundled consolidated file at anchor a28 rather than hand-authoring a duplicate excerpt. The reviewer cross-checks every percentage against live BOE before stamping, because the standing grounding rule distrusts bundled text on a number; `src/cadrumo/_data/registry/aeat/legal/`.
- [x] `P06.S20` - BLOCKED on a named human legal reviewer, never an agent stamp. The corpus half is discharged as of 2026-08-10: arts. 178 through 212 are all present in the bundled consolidated Ley 58/2003 and in its sidecar. Author the legal-catalogue entry for the regimen sancionador focused on the arts. 191-197 pecuniaria proporcional bands, pointing corpus_ref at the bundled consolidated file. Every band percentage is cross-checked against live BOE by the reviewer before stamping; `src/cadrumo/_data/registry/aeat/legal/`.
- [x] `P06.S21` - BLOCKED on a named human legal reviewer, never an agent stamp. The corpus half is discharged as of 2026-08-10: arts. 65 and 82 are present in the bundled consolidated Ley 58/2003. Author the legal-catalogue entry for aplazamiento y fraccionamiento del pago and its garantias, pointing corpus_ref at the bundled consolidated file. Any interest rate the entry carries is cross-checked against live BOE by the reviewer before stamping; `src/cadrumo/_data/registry/aeat/legal/`.
- [x] `P06.S22` - BLOCKED on a named human legal reviewer, never an agent stamp. The corpus half is discharged as of 2026-08-10: arts. 163 and 167 through 173 are all present in the bundled consolidated Ley 58/2003. Author the legal-catalogue entry for the procedimiento de apremio, providencia and embargo, pointing corpus_ref at the bundled consolidated file, verified by the legal-entry evidence gate; `src/cadrumo/_data/registry/aeat/legal/`.

### Phase `P07` - Peer-WIP-blocked: locale rows

Author real es/en/ca/hu values for the new deudas CLI help and labels once the in-flight en.yml/hu.yml peer WIP lands and scaffold --check is clean.

- [x] `P07.S23` - Author real es, en, ca and hu values for the new deudas CLI help and label keys via python -m dev.locales set, then scaffold and scaffold --check clean. Lands as ONE unit with P04.S10 through S12 because the codebase-to-locale parity gate is tree-wide and immediate, so no ordering exists in which the CLI rows are green before these values exist in all four catalogues. The original en.yml and hu.yml peer-WIP blocker is discharged; `src/cadrumo/locales`.

### Phase `P08` - Notification document custody: encrypted storage service

Persist a fetched notification PDF through the encrypted content-addressed AttachmentStore, keyed on the certificado id and content-addressed so a re-fetch is a no-op. Bytes never touch a filesystem path, per the sensitive-financial-data rule. Nothing here is blocked: the adapter fetch function and its comparecencia guard are already committed and live-verified.

- [x] `P08.S24` - Add the LIVE_NOTIFICATION_DOCUMENT_NAMESPACE bucket-scoped namespace constant for the document manifest beside LIVE_DEUDAS_SNAPSHOT_NAMESPACE, verified by the existing namespace-uniqueness gate over the storage namespace constants; `src/cadrumo/adapters/persistence/storage`.
- [x] `P08.S25` - Add the frozen PersistedNotificationDocument model carrying certificado_id, the AttachmentStore attachment id, pdf_sha256, source_url and fetched_at under STRICT config, exposing NO filesystem path field of any kind, verified by a model validation unit test asserting the field set and that no field name or value carries a path; `src/cadrumo/application/live/_notification_documents.py`.
- [x] `P08.S26` - Add NotificationDocumentService storing the fetched bytes through the encrypted content-addressed AttachmentStore resolved the way application/ledger/_actions_common.py resolves it, delegating to that single-writer primitive rather than re-implementing its write path, verified by a unit test asserting the store receives the bytes and the service opens no second write path; `src/cadrumo/application/live/_notification_documents.py`.
- [x] `P08.S27` - Make a re-store of an already-persisted certificado id a content-addressed no-op returning the existing record with no second attachment write and no re-stamped fetched_at, and refuse with an instructive localised conflict when the same certificado id arrives with a different pdf_sha256, verified by an idempotency test covering the no-op, the field-complete match and the divergent-digest refusal; `src/cadrumo/application/live/_notification_documents.py`.
- [x] `P08.S28` - Write the strict roundtrip test against a real SecureObjectRepository, real key provider, real SQLite engine and real AttachmentStore, populating every defaultable field non-default and asserting strict pydantic equality, then the anti-tautology proof deleting a persisted field on disk and asserting reload refusal; `src/cadrumo/application/live/tests/test_notification_documents_service.py`.
- [x] `P08.S29` - Write the custody gate proving a full fetch-and-store cycle writes the PDF bytes to no filesystem path: run the service against a temporary profile root, assert every file created is an encrypted store artefact and that the plaintext PDF magic bytes appear nowhere on disk, then the mutation proof writing the bytes to a temp file and confirming the gate reds; `src/cadrumo/application/live/tests/test_notification_document_custody.py`.

### Phase `P09` - Deterministic sancion and liquidacion parser

Extract the printed figures from a fetched document with a label-anchored regex composed on the EXISTING canonical PDF primitives, never a second amount regex and never a model. An unmatched document reports unparsed and refuses to persist a zeroed record.

- [x] `P09.S30` - Add the frozen sancion/liquidacion parse record with Spanish-stemmed fields mirroring the printed labels (clave_liquidacion, referencia, nif, base_sancion, porcentaje_minimo, sancion_resultante, reduccion_conformidad, reduccion_pronto_pago, diferencia), each distinguishing an absent label from a matched zero, verified by a model unit test asserting a matched-zero and an unmatched field are not equal. DELIVERED as SancionLiquidacion rather than the row's original SancionDocumentoParse name, and the absent-versus-zero distinction is carried by Decimal | None on the optional fields rather than a per-field matched flag: a required field cannot express absence at all and refuses instead, so the flag would have been dead weight on every field that has one. Coverage is equivalent, not narrower - the regression pins that the arithmetic cannot recover the distinction, so only the record carries it; `src/cadrumo/adapters/inbound/notificacion/_sancion.py`.
- [x] `P09.S31` - Reconcile the sancion amount pattern against the tree's two existing amount authorities rather than adding a third: _STRICT_AEAT_MONEY_RE is byte-identical in the IVA compensation wallet parser and the sancion parser with no shared home, which is true duplication, while SPANISH_AMOUNT_GROUP is constraint-shape-divergent (unanchored capture group, NBSP-tolerant) and is NOT substitutable for the anchored house pattern. Give the house pattern one canonical home consumed by both callers, verified by a duplication gate asserting the literal appears exactly once in the tree; `src/cadrumo/adapters/inbound/notificacion/_sancion.py`.
- [x] `P09.S32` - Write parse_sancion_documento running the label dispatch over text lifted by the existing extract_pages_text_from_bytes and converting captured amounts with the existing parse_spanish_decimal, adding no second PDF text extractor and no second decimal parser, verified by a parse unit test over a synthetic specimen reproducing the observed label set; `src/cadrumo/adapters/inbound/notificacion/_sancion.py`.
- [x] `P09.S33` - Establish whether the AEAT text layer emits the UNE 82100 NBSP or narrow-NBSP thousands separator and admit them in the anchored house pattern. RESOLVED on the empirical finding the tree already carried at adapters/inbound/pdf/_label_regex.py, which records NBSP and narrow-NBSP grouping as observed AEAT rendering and ASCII space as never emitted. Both forms were refused by the sancion reader, so a genuine AEAT document would have been refused outright. The separator taxonomy now has one source consumed by all three grammars, ASCII space stays refused, and _strip_leaders no longer destroys the separator ahead of the check. Verified by a regression pinning the accepted and refused separator forms with a mutation proof, landed in the tree's existing tests/test_sancion_parser.py rather than the row's originally-named test_sancion_parse.py, which would have been a near-duplicate file; `src/cadrumo/adapters/inbound/notificacion/tests/test_sancion_parser.py`.
- [x] `P09.S34` - Make a document in which no label matches report explicitly unparsed and refuse to return a record of zeroes or a clean empty result, verified by a regression feeding an unrelated PDF and asserting the refusal, paired with the standing lesson that this reader has twice returned a silent zero against populated data; `src/cadrumo/adapters/inbound/notificacion/_sancion.py`.
- [x] `P09.S35` - Confirm the notificacion package facade exports the sancion parse entry point and its typed record for the application layer, and that the PDF-bytes-to-text step reuses the canonical extract_pages_text_from_bytes rather than introducing a second extractor, verified by the import hygiene gate and a check that no second pdfplumber call site is added; `src/cadrumo/adapters/inbound/notificacion/__init__.py`.

### Phase `P10` - CLI leaves, write-guard enrollment, harness and locales

Expose the fetch and read-back leaves on the existing app live notifications group under the CLI contract: pull stem for the AEAT fetch, positional certificado id, diagnostics on the typed Notice channel only. The fetch leaf persists to bucket storage so it is enrolled in the profile-bound write policy and swept into the operator harness in the same change.

- [ ] `P10.S36` - Add the document pull and document view payload models as new OutputSchema subclasses in the existing _app_live_payloads module, carrying no bespoke advisory, next or suggestion field, verified by test_json_schema_conformance; `src/cadrumo/entrypoints/cli/_app_live_payloads.py`.
- [ ] `P10.S37` - Register the document subgroup under app live notifications and wire aeat app live notifications document pull taking the certificado id as a positional Argument, resolving the row from the persisted notification snapshot and calling the guarded adapter fetch and the storage service. The subgroup carries the literal pull stem the CLI contract requires, never capture or fetch or refresh or sync; `src/cadrumo/entrypoints/cli/_app_live_notifications_cli.py`.
- [ ] `P10.S38` - Wire aeat app live notifications document view taking the certificado id as a positional Argument and reading only the persisted record and its parse, making no AEAT contact at all, verified by a CLI integration test asserting the verb completes with no session factory available; `src/cadrumo/entrypoints/cli/_app_live_notifications_cli.py`.
- [ ] `P10.S39` - Project the comparecencia refusal, the unparsed-document report and the re-fetch no-op through the typed Notice channel on the shared envelope spine, rebuilding each text line from the same notice so JSON and text cannot drift, verified by test_rule_surface_conformance; `src/cadrumo/entrypoints/cli/_app_live_notifications_cli.py`.
- [ ] `P10.S40` - Enroll app live notifications document pull in PROFILE_BOUND_WRITE_VERB_PATHS beside the existing app live notifications pull entry with a comment stating it persists fetched document bytes to bucket storage, verified by test_root_fallback_guard_predicate_covers_profile_bound_mutations extended with the new entry; `src/cadrumo/application/storage_write_policy.py`.
- [ ] `P10.S41` - Classify the document read-back leaf on the reviewed-non-mutating roster as a pure read over persisted records, verified by test_every_app_leaf_is_accounted_for_by_name_independent_census staying green with both new leaves accounted for; `src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py`.
- [ ] `P10.S42` - Add document pull to the operator-orientation agent-harness document alongside notifications pull in the same commit as the verb, stating that it refuses any notification AEAT does not report as read, verified by test_documented_command_conformance; `src/cadrumo/_data/agent/rules/cadrumo-operator-orientation-routing.md`.
- [ ] `P10.S43` - Author real es, en, ca and hu values for every new tr key on the two leaves and their notices via python -m dev.locales set, obtaining the ca and hu strings before running set rather than leaving either catalogue to a later sweep, then scaffold and scaffold --check clean with no self-referencing placeholder and no allowlist entry; `src/cadrumo/locales`.

### Phase `P11` - Penalty history: bounded display-as-reported view

List the parsed documents the profile holds with each document's own reported figures. Computes no total and asserts no payable balance, because whether a sancion is paid, appealed, reduced or superseded is not stated on the document and therefore not stated by the application.

- [ ] `P11.S44` - Wire aeat app live notifications document history listing every parsed document the profile holds with each document's own reported figures, certificado id and date, computing no total and asserting no payable balance, verified by a CLI integration test over two persisted parses asserting the payload carries no summed field; `src/cadrumo/entrypoints/cli/_app_live_notifications_cli.py`.
- [ ] `P11.S45` - Attach a standing info Notice to the history payload stating it records what AEAT served and is neither a payable balance nor the recaudacion register the deudas verbs read, because payment, appeal, reduction and supersession are not stated on the document, verified by a test asserting the notice is present on every history emit; `src/cadrumo/entrypoints/cli/_app_live_notifications_cli.py`.
- [ ] `P11.S46` - Add the no-total invariant gate asserting the history payload schema declares no field summing amounts across documents, keyed by field name and by the schema shape rather than by a count, then the mutation proof adding a total field and confirming the gate reds; `src/cadrumo/entrypoints/cli/tests/test_notification_document_history_no_total.py`.
- [ ] `P11.S47` - Author real es, en, ca and hu values for the history verb help and its standing notice via python -m dev.locales set, then scaffold --check clean; `src/cadrumo/locales`.

### Phase `P12` - User documentation for notification documents

Document the fetch, the read-back and the history view in singular imperative steps, and state the comparecencia constraint in operator language so the refusal on an unread notification reads as designed behaviour rather than a fault. DRAFTED AND DELIBERATELY HELD on 2026-08-13: the section and its cli-sequence contract were written and then withdrawn unlanded, because test_documented_command_conformance resolves every cited verb against the live operator-surface manifest and the verbs do not exist in code yet. Landing them would red a required gate for every peer. The naming question that also blocked it is now SETTLED by operator ruling - the surface is aeat app live notifications document pull, document view and document history - so the only remaining blocker is the verbs existing. The wording to restore is in this Phase's rows.

- [ ] `P12.S48` - Add the cli-sequence contract file for the notification-document reads declaring the document pull, document view and document history steps in singular imperative sentences, each blocked live-aeat where it reads the operator's authenticated session; `docs/_sequences/contracts/how-to/check-aeat-notifications/check-notifications-documents.seq`.
- [ ] `P12.S49` - Add the notification-documents section to the AEAT notifications how-to in singular imperative steps, stating plainly that the tool reads only notifications already opened in the sede and that an unread notification must be opened by the taxpayer personally because opening it is the moment it becomes legally served; `docs/how-to/check-aeat-notifications.md`.
- [ ] `P12.S50` - Enroll any new user-facing term the section introduces in the Terminology Handbook as a concept fragment referenced with the term role, never redeclared in prose, verified by the terminology scaffold check; `src/cadrumo/_data/terminology/concepts`.
- [ ] `P12.S51` - Verify the documentation with pytest dev/docs/tests/test_docs_build.py and the documented-command conformance integration gate, resolving every link and every cited verb against the live operator-surface manifest; `docs/how-to/check-aeat-notifications.md`.

## Parallelization

P01 must land before P02 and P03 (both consume `Deuda`, its enums, and the
module `_deudas.py` lives in). P02, P03 and P04 have no interdependency
among themselves once P01 is closed and may run in parallel: the snapshot
service, the guard skeleton, and the CLI read surface touch disjoint files.
Within P04, S10 must land before S11, and S11 before S12. Within P02, S04
through S06 are sequential (each is a precondition for the next); S07 depends
on S04-S06 all being closed.

P05 is hard-blocked behind P01-P04 (it extends the same module and CLI
surface) and, independently, behind an operator authorising a live specimen
capture. Its own Steps are sequential: S13 (enum finalisation) before S14
(parse function, which needs the finalised `Situacion` type), S14 before S15
(prefixes come from the same capture but the parse function is the
consumer that proves the prefix is right), S15 before S16 (the `pull` verb
wires the guarded walker), S16 before S17 (enrollment names a verb that must
already exist), S17 before S18 (the harness doc must describe a live verb).

P06's four Steps are mutually independent (four separate LGT provisions) and
may run in parallel once a human reviewer is assigned to each; none of them
blocks P01-P05, since the base register displays AEAT's reported figures
without needing any of these citations. P07 is independent of every other
Phase except that it cannot start until the peer `en.yml`/`hu.yml` write
lands in the shared worktree.

**P08 through P12** are independent of P01-P07 entirely: they read a different
AEAT surface, persist through a different storage primitive, and share no
module with the deudas register. None of them is blocked by the P05 deferral,
and none of them unblocks it.

P08 and P09 have no interdependency and may run in parallel - the custody
service and the parser touch disjoint packages and neither imports the other.
Within P08, S24 through S27 are sequential (the namespace before the model, the
model before the service, the service before its idempotency behaviour); S28
and S29 both depend on S24-S27 being closed and may then run in parallel.
Within P09, S30 and S31 may run in parallel, S32 depends on both, S33 and S34
depend on S32, and S35 depends on S32 and S30.

P10 is hard-blocked behind BOTH P08 and P09, because the fetch leaf calls the
custody service and the read-back leaf renders the parse. Its own Steps are
sequential in the CLI-contract order: S36 (payloads) before S37 and S38 (the
leaves), S37 before S40 (enrollment names a verb that must already exist), S40
before S42 (the harness must describe a live verb). S39 depends on S37 and S38.
**S43 lands as ONE unit with S36 through S39**, exactly as P07.S23 did with
P04: the codebase-to-locale parity gate is tree-wide and immediate, so no
ordering exists in which a `tr` key is green in source before it exists in all
four catalogues.

P11 is blocked behind P10 (it extends the same command group and needs a
persisted parse to list). Its S47 lands as one unit with S44 and S45 for the
same locale-parity reason. P12 is blocked behind P10 and P11 together, because
the documented-command conformance gate resolves every cited verb against the
live operator-surface manifest and will red on a verb that does not yet exist.

## Verification

The plan is complete when every Step is closed (`- [x]`) or the closeout
audit records why a Step is a deferred carry-forward, per
`aeat-agent-orchestration`'s campaign-close mandate. Per-phase criteria:

- **P01**: new unit tests for `ObjetoTributario`, `Direccion` and the `Deuda`
  model pass; `uv run --no-sync pytest --collect-only -q` collects cleanly
  with no import cycle introduced.
- **P02**: `test_deudas_service.py`'s roundtrip passes with real adapters
  (real key provider, real SQLite, real `SecureObjectRepository`) and its
  anti-tautology proof fails the load when a persisted field is deleted from
  the on-disk payload.
- **P03**: `test_deudas_read_landing_guard.py` proves the guard refuses every
  synthetic URL against the empty prefix set, then proves a populated
  single-entry prefix permits only that entry (the mutation-proof pairing:
  break it, confirm red, restore).
- **P04**: `test_every_app_leaf_is_accounted_for_by_name_independent_census`
  stays green with the three new leaves classified, and a new CLI
  integration test exercises `list`/`view`/`latest` against a persisted
  snapshot fixture.
- **P05**: each Step's own named gate
  (`test_root_fallback_guard_predicate_covers_profile_bound_mutations`,
  `test_documented_command_conformance`, the parse fixture test) passes, and
  no Step in this Phase is started before an operator has authorised and
  delivered a specimen capture.
- **P06**: each legal-catalogue entry passes the legal-entry evidence gate
  (corpus cross-check, `required_text` phrase distinctiveness) and carries a
  named human reviewer's sign-off, never an agent stamp.
- **P07**: `python -m dev.locales scaffold` then `scaffold --check` run
  clean with no self-referencing placeholder and no missing `ca`/`hu` entry.
- **P08**: `test_notification_documents_service.py`'s strict roundtrip passes
  against real adapters (real key provider, real SQLite, real
  `SecureObjectRepository`, real `AttachmentStore`) and its anti-tautology
  proof fails the load when a persisted field is deleted from the on-disk
  payload; `test_notification_document_custody.py` finds the plaintext PDF
  magic bytes nowhere on disk after a full store cycle, and reds when the
  mutation writes them to a temp file.
- **P09**: the parse tests pass over a synthetic specimen carrying the
  observed label set; the `3.687,12euros` and NBSP-separator regressions
  assert exact `Decimal` values and red when the amount group is narrowed;
  the unrelated-PDF case reports unparsed rather than returning zeroes; the
  duplication gate finds no second amount regex and no second text extractor
  in this feature's modules; the import-hygiene gate finds no cross-package
  private import of the sancion modules.
- **P10**: `test_json_schema_conformance`, `test_rule_surface_conformance`,
  `test_root_fallback_guard_predicate_covers_profile_bound_mutations`,
  `test_every_app_leaf_is_accounted_for_by_name_independent_census` and
  `test_documented_command_conformance` all pass with both new leaves
  present, and `scaffold --check` is clean in the same unit.
- **P11**: the history integration test asserts the payload carries no summed
  field and that the standing notice is present on every emit;
  `test_notification_document_history_no_total.py` reds when a total field is
  added.
- **P12**: `pytest dev/docs/tests/test_docs_build.py` passes under the
  nitpicky Sphinx gate with every link resolving, and
  `pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -m integration`
  resolves every verb the new section cites against the live manifest.

Cross-cutting: at no point in P01-P05 does a persisted `Deuda` value reach a
`BindingAggregation`, relation, or casilla resolution - grep
`BindingSourceKind` after P05 lands and confirm no new member references a
post-filing enforcement concept, the same structural check the research used
to establish the current gap. The same check binds a persisted
`SancionDocumentoParse`: a figure AEAT served on a notification is a
consequence of a filing, never an input to one.

**Cross-cutting and binding for P08-P12: the comparecencia predicate may only
narrow.** After every Step in these Phases, `assert_notification_content_readable`
still admits exactly and only `leida is True`. No Step may add a force flag, an
override parameter, an already-served branch, a batch walk over unread rows, or
any other path by which the application drives AEAT's `vernotif` control on a
notification the taxpayer has not personally opened. A Step that would require
one is not a Step to reformulate; it is out of scope by decision. Verify by
reading the predicate at the close of each Phase, not only at plan close - it is
the one invariant here whose violation is legally irreversible for the operator
rather than merely a defect in the tree.

**Closed 2026-08-12 at 23/23, and five of those checkboxes are NOT deliveries.**

This plan's completion clause admits either every Step closed or a closeout
audit recording why a Step is a deferred carry-forward. Both now hold, and the
campaign-close mandate's condition is met: no Step is checked without a matching
execution record.

`P05.S13`, `S14`, `S16`, `S17` and `S18` are closed as **deferred
carry-forward**. Each carries an execution record whose Outcome opens by saying
so and states what was not built. Read as a set:

- no `walk_deudas_consulta` exists,
- no `deudas pull` verb exists,
- no write-policy enrollment exists,
- the operator harness names no deudas verb,
- and `situacion`'s bound is retained UNCONFIRMED rather than confirmed.

The blocker is that AEAT's recaudación register holds no rows for this taxpayer,
established with a same-session positive control rather than asserted: the
notifications summary rendered three populated tables while the deudas consulta,
queried immediately after, rendered none. The taxpayer's liabilities are real
and sit at notification stage, in a different register at a different procedural
stage from the one this surface reads.

**What the standing goal still asks for that this close excludes.** The goal is
that an operator can see, inside the application, what AEAT currently reports as
owed. They cannot. What shipped is the register's shape, its guard and its legal
grounding - P05.S15 moved the guard from refusing every landing to refusing every
landing except one endpoint nothing navigates to, and P06 grounded provisions
nothing yet consumes. A future campaign that reopens this work should treat the
five rows above as its backlog, not as prior art.

**Reopened 2026-08-13 at 23 of 51.** The close above stands unamended: those
five rows are still deferred carry-forward and this reopening does not schedule
them. What it adds is a second route to the same standing goal, governed by
`2026-08-13-aeat-liabilities-sanciones-notification-documents-adr` and carried
by P08 through P12, 28 new Steps. The plan is therefore no longer closed and
must not be reported as such until those Steps are closed or a fresh closeout
audit records why any of them is a deferred carry-forward.

The condition for closing this plan a second time is unchanged and applies to
the new Phases in full: no Step marked complete without a matching execution
record, and a fresh-context honesty review against the closure summary before
any claim of structural completeness. The specific claim that review must test
is the one this feature has already got wrong once - that a green checkbox count
is not evidence the operator can see anything.
