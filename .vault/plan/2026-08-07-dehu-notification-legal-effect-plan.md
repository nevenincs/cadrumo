---
tags:
  - '#plan'
  - '#dehu-notification-legal-effect'
date: '2026-08-07'
modified: '2026-08-08'
body_hash: 'sha256:75edd73babf7138c21e72f12af7894f8caec1e7dc434c75457de3af62fb54d13'
tier: L2
related:
  - '[[2026-08-07-dehu-notification-legal-effect-adr]]'
---

# `dehu-notification-legal-effect` plan

## Description

Executes `2026-08-07-dehu-notification-legal-effect-adr`: a new orthogonal
`NotificacionEstadoServicio` core enum, a grounded ten-dias-naturales
constant citing Ley 39/2015 art. 43.2, and a widened post-filing
actionability predicate so a DEHu notification that lapses into rechazo
tacito surfaces to the operator regardless of its procedural
`PostFilingEventKind`. Implementation is authorized end to end; every Step
below is scoped, ordered and closes only against its own verification gate
- no Step is a deferred "investigate" placeholder.

Phase P01 is the human-adjudicated legal-grounding precondition, per
`aeat-calculation-grounding`'s "legal catalogue is a human-reviewed,
filing-grade surface" and the operator's standing instruction that no agent
may self-stamp a legal entry reviewed. Phase P01's fetch (P01.S01) reads
BOE's public consolidated-legislation text, which is NOT an AEAT surface and
carries no authentication; it is not covered by the live-AEAT-probe
restriction below.

The Phase's two halves block different things, and the distinction is the
subject of the amendment recorded in the governing ADR. The **corpus** half
(P01.S01) is a hard precondition for every later Step: nothing may cite art.
43.2 without the committed, anchor-resolving excerpt. The **catalogue
enrollment** half (P01.S03) blocks only the Steps that resolve the entry
**id** - P02.S11's grounding test, P03.S08's `Notice`, P04.S09's terminal
run, and P01.S10's closeout record. It does not block P02.S04, P02.S05,
P03.S06 or P03.S07, whose gates never touch the catalogue.

**What the original formulation still asks for that this split excludes.**
The retired sentence ("a hard blocking dependency for every later Phase")
guaranteed that no line of this feature's code could exist until a human had
personally adjudicated the legal basis - a single ordering rule needing no
per-row judgement. The split trades that for four rows landing on the
strength of the committed corpus alone, and it therefore accepts two things
the original refused: a `Final[int] = 10` shipping in `core/` before any
human signed the provision behind it, and a reviewer arriving after the fact
to a constant already consumed by an enum, a calendar field and an
actionability predicate, so that a review finding the figure wrong now
implies unwinding four rows instead of writing none. The mitigation is
narrow and stated rather than assumed: the figure was cross-checked against
live BOE independently of the bundled corpus, and the constant's doc comment
cites only the provision, never a catalogue entry that does not yet exist.
It is a mitigation, not a substitute for the review.

No Step in this plan requires a live authenticated probe against AEAT's
real servers. If a later Step is ever proposed that would need one (for
example, live-validating the widened `Notice` against a real DEHu buzon),
it must be marked as requiring separate operator sign-off before it is
added to this plan, per the standing instruction that implementation
authorization is not live-traffic authorization.

## Steps

### Phase `P01` - legal grounding precondition (human-adjudicated, blocking)

Fetch and commit the Ley 39/2015 art. 43.2 corpus, then enroll it in the legal catalogue under human sign-off. The corpus half (P01.S01) is a precondition for every later Phase. The catalogue-enrollment half (P01.S03) blocks only the Steps that resolve the entry id.

- [x] `P01.S01` - Reuse the campaign's already-primary-sourced BOE consolidated PDF for Ley 39/2015 at boe.es buscar pdf 2015 BOE-A-2015-10565-consolidado.pdf, art. 43 at page 35, rather than re-deriving it, taking the LAST version if the payload bundles historical redactions, never passing the text through a shell since a truncating heredoc silently loses text, and reading the committed file back before trusting it. The consolidated PDF does not annotate which articles were amended, confirmed by positive control against art. 28, so absence of a marker on art. 43 establishes only that this is todays operative text, and no unamended-since-2015 claim may be made anywhere downstream. Commit the HTML plus its extracted sidecars, verified by resolve_anchored_extracted_unit resolving the target anchor with no CorpusAnchorResolutionError; `src/cadrumo/_data/corpus/normatives/html/`.
- [x] `P01.S02` - Draft the candidate ley-39-2015-notificaciones.toml LegalReference entry (id, kind=ley, corpus_ref, required_text carrying the diez-dias-naturales phrase verbatim) as a proposal recorded only in this Step's execution record, and do NOT commit it to the registry, since LegalReference.review_status is typed Literal reviewed and cannot represent an unreviewed draft on disk; `src/cadrumo/_data/registry/aeat/legal/ley-39-2015-notificaciones.toml (proposed, not written)`.
- [ ] `P01.S03` - HUMAN GATE, owner: operator, no agent may self-stamp review_status. Operator reviews the S02 draft against the committed corpus and personally commits the entry with review_status=reviewed, confirmed by the legal-catalogue verification suite (verify_legal_reference / registry build validation) passing green against the merged entry. This Step blocks every Step that RESOLVES the catalogue entry, namely P02.S11, P03.S08 and P04.S09, plus the P01.S10 closeout that records it. It does NOT block P02.S04, P02.S05, P03.S06 or P03.S07, which depend only on the corpus committed in P01.S01; `src/cadrumo/_data/registry/aeat/legal/ley-39-2015-notificaciones.toml`.
- [ ] `P01.S10` - Scaffold P01.S03's execution record through vaultspec-core vault add exec, citing the operator's review commit sha and the green legal-catalogue verification run, then check the P01.S03 row. Carried as its own row rather than a note, because a row checked with no exec record makes delivered-as-specified and recorded-but-not-implemented wear the same checkbox. Blocked on the operator's commit; `.vault/exec/2026-08-07-dehu-notification-legal-effect/`.

### Phase `P02` - core typed axis

Add the grounded dias-naturales constant and the orthogonal NotificacionEstadoServicio enum plus its pure computation function. The constant and enum rows depend on the committed corpus only; the catalogue-resolution grounding test row is blocked on Phase P01's human review gate.

- [x] `P02.S04` - Add DEHU_RECHAZO_TACITO_DIAS_NATURALES as a Final int equal to 10 to external_constants.py, doc-commented with the Ley 39/2015 art. 43.2 provision citation and its BOE-A-2015-10565 document id in the same style as every sibling leaf constant in that file, and deliberately NOT naming any legal-catalogue entry id, because an entry id cited before the catalogue file exists ships a dangling reference into production source. Verified by the constant importing cleanly and by the external-constants centralisation AST gates staying green; `src/cadrumo/core/external_constants.py`.
- [ ] `P02.S11` - Add the catalogue-resolution grounding test asserting the DEHU_RECHAZO_TACITO_DIAS_NATURALES doc citation resolves against the operator-reviewed ley-39-2015 art-43.2 legal catalogue entry, following the existing test_external_constants_centralisation_part2.py pattern, and extend the constant's doc comment to name that entry id only once the entry exists on disk. This is the half of the original S04 row that genuinely depends on the human review gate, split out so the constant itself is not held behind it. Read the entry id off the COMMITTED registry TOML, never off external_constants.py. The constant's current comment cites only the provision and its BOE document id, so there is no id already present there to check a new one against, and an id copied from the wrong surface would resolve to nothing while reading as grounded. The corrected P01.S02 draft spells it ley-39-2015 colon art-43.2. Blocked on P01.S03; `src/cadrumo/core/external_constants.py, src/cadrumo/core/tests/test_external_constants_centralisation_part2.py`.
- [x] `P02.S05` - Add a new core module declaring the NotificacionEstadoServicio StrEnum, with members NO_ENTREGADA, ACCEDIDA, EN_PLAZO and RECHAZO_TACITO, and a pure function computing it from fecha_notificacion, leida and an explicit as_of date against DEHU_RECHAZO_TACITO_DIAS_NATURALES, then add boundary tests covering day 9 EN_PLAZO, day 10 RECHAZO_TACITO, fecha_notificacion is None NO_ENTREGADA, and leida is True ACCEDIDA regardless of elapsed days, plus a mutation-proof test that flips the day-10 boundary comparison and confirms the boundary test fails; `src/cadrumo/core/_notificacion_estado_servicio.py, src/cadrumo/core/__init__.py, src/cadrumo/core/tests/test_notificacion_estado_servicio.py`.

### Phase `P03` - wiring: calendar, actionability, notice

Surface the computed service state on the typed calendar event, widen post-filing actionability for deemed-served notifications independent of procedural kind, and extend the operator-facing Notice; blocked on Phase P02.

- [x] `P03.S06` - Add a typed notificacion_estado_servicio field, typed NotificacionEstadoServicio or None, to OverviewCalendarEvent, and compute it per row in calendar_events_from_notification_snapshots from fecha_notificacion and leida against an explicit as_of parameter threaded from the caller, never an inline date.today call, then add a projection test proving a synthetic ten-day-lapsed row computes RECHAZO_TACITO; `src/cadrumo/application/overview/_calendar.py, src/cadrumo/application/overview/tests/`.
- [x] `P03.S07` - Widen the actionability predicate behind actionable_post_filing_events so an event is actionable when its post_filing_kind is in ACTIONABLE_POST_FILING_EVENT_KINDS or its notificacion_estado_servicio is RECHAZO_TACITO, then add a mutation-proof test proving a plain NOTIFICACION event carrying RECHAZO_TACITO state appears in actionable_post_filing_events and that reverting the widening back to a bare frozenset membership check fails the test; `src/cadrumo/application/overview/_calendar.py, src/cadrumo/application/overview/tests/`.
- [ ] `P03.S08` - Extend the overview CLI Notice composer to include deemed-served notifications in a warning-severity Notice carrying the P01.S03 legal catalogue entry id and the affected certificado ids on Notice.context, add the new locale keys through python -m dev.locales set with real es, en, ca and hu strings for every key, and run the locale scaffold check; `src/cadrumo/entrypoints/cli/_overview_rendering.py, src/cadrumo/locales/es.yml, src/cadrumo/locales/en.yml, src/cadrumo/locales/ca.yml, src/cadrumo/locales/hu.yml, src/cadrumo/entrypoints/cli/tests/`.

### Phase `P04` - full-tree verification

Run every targeted suite plus the tree-wide vault and locale gates and triage any red signature; blocked on every Step in Phases P01 through P03 being closed, including the human review gate.

- [ ] `P04.S09` - Run the targeted suites sequentially, core tests, the registry legal and catalogue tests, application overview tests and entrypoints cli tests, plus vaultspec-core vault check all and the locales scaffold --check gate, capture full output to a log file per aeat-local-execution, and triage any red signature as owner-surface or unrelated peer churn before closing this Step; `no production files, verification only`.

## Parallelization

Phase P01 is strictly serial: P01.S01 must land before P01.S02 (the draft
cites the committed corpus), P01.S03 (the human gate) cannot close before
P01.S02 exists, and P01.S10 cannot close before the operator's P01.S03
commit exists to cite.

P01.S01 hard-blocks every later Step. P01.S03 hard-blocks only the
entry-id-resolving set - P01.S10, P02.S11, P03.S08 and P04.S09 - and none
of P02.S04, P02.S05, P03.S06 or P03.S07.

Within P02, P02.S04 must land before P02.S05, since the pure function in
P02.S05 imports `DEHU_RECHAZO_TACITO_DIAS_NATURALES` from P02.S04. P02.S11
may land at any point after both P02.S04 and P01.S03 are closed, and is the
only P02 row waiting on the human gate.

Within P03, P03.S06 must land before P03.S07 (the actionability widening
reads the field P03.S06 adds) and before P03.S08 (the Notice composer
reads the same field); P03.S07 and P03.S08 touch disjoint files
(`_calendar.py` versus `_overview_rendering.py` and the locale catalogues)
and may run in parallel with each other once P03.S06 is closed.

P04.S09 runs strictly last, after every Step in P01 through P03 is closed.

## Verification

The plan is complete when every Step is closed (`- [x]`) and P04.S09's
full-tree run is green with no untriaged owner-surface failure. Per-Step
gates (restated from Steps above, not re-argued):

- P01.S01: `resolve_anchored_extracted_unit` resolves the committed anchor
  with no `CorpusAnchorResolutionError`.
- P01.S03: the legal-catalogue verification suite passes green against the
  operator-committed, reviewed entry. The commit is the human sign-off
  record, but it is NOT this row's closing artefact - P01.S10 supplies that.
- P01.S10: the Step Record for P01.S03 exists, cites the operator's commit
  sha, and the P01.S03 checkbox is closed through
  `vaultspec-core vault plan step check`.
- P02.S04: the constant imports cleanly, its doc comment cites Ley 39/2015
  art. 43.2 and `BOE-A-2015-10565` and names no catalogue entry id, and the
  external-constants centralisation AST gates stay green.
- P02.S11: the grounding test asserting the constant's citation resolves
  against the reviewed catalogue entry passes.
- P02.S05: the boundary tests (day 9, day 10, `None`, `leida is True`) and
  the mutation-proof test pass; the mutation-proof test fails when the
  boundary comparison is deliberately flipped, proving the test is not
  tautological.
- P03.S06: the projection test proving a ten-day-lapsed row computes
  `RECHAZO_TACITO` passes.
- P03.S07: the mutation-proof test proving a deemed-served plain
  `NOTIFICACION` reaches `actionable_post_filing_events` passes, and fails
  when the widening is reverted.
- P03.S08: the CLI envelope/schema conformance tests pass, and
  `python -m dev.locales scaffold --check` is clean across all four
  catalogues with no scaffold placeholder.
- P04.S09: `vaultspec-core vault check all` and every targeted suite are
  green, or every red signature is triaged and attributed to unrelated peer
  churn per `aeat-worktree-safety`.
