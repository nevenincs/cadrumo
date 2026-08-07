---
tags:
  - '#plan'
  - '#dehu-notification-legal-effect'
date: '2026-08-07'
modified: '2026-08-07'
body_hash: 'sha256:c8e89ce3bf2bb1e4f297e696751894b5a90851faad2a11fda8c8879e5f2621be'
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

Phase P01 is the human-adjudicated legal-grounding precondition and is a
hard blocking dependency for every later Phase, per
`aeat-calculation-grounding`'s "legal catalogue is a human-reviewed,
filing-grade surface" and the operator's standing instruction that no agent
may self-stamp a legal entry reviewed. Phase P01's fetch (P01.S01) reads
BOE's public consolidated-legislation text, which is NOT an AEAT surface and
carries no authentication; it is not covered by the live-AEAT-probe
restriction below.

No Step in this plan requires a live authenticated probe against AEAT's
real servers. If a later Step is ever proposed that would need one (for
example, live-validating the widened `Notice` against a real DEHu buzon),
it must be marked as requiring separate operator sign-off before it is
added to this plan, per the standing instruction that implementation
authorization is not live-traffic authorization.

## Steps

### Phase `P01` - legal grounding precondition (human-adjudicated, blocking)

Fetch and commit the Ley 39/2015 art. 43.2 corpus and enroll it in the legal catalogue under human sign-off; every downstream Phase is blocked on this Phase's closing Step.

- [ ] `P01.S01` - Fetch BOE's live consolidated text for Ley 39/2015 art. 43.2, taking the LAST version if the payload bundles historical redactions and confirming no shell-heredoc truncation by reading the saved file back, then commit the HTML plus its extracted sidecars, verified by resolve_anchored_extracted_unit resolving the target anchor with no CorpusAnchorResolutionError; `src/cadrumo/_data/corpus/normatives/html/`.
- [ ] `P01.S02` - Draft the candidate ley-39-2015-notificaciones.toml LegalReference entry (id, kind=ley, corpus_ref, required_text carrying the diez-dias-naturales phrase verbatim) as a proposal recorded only in this Step's execution record, and do NOT commit it to the registry, since LegalReference.review_status is typed Literal reviewed and cannot represent an unreviewed draft on disk; `src/cadrumo/_data/registry/aeat/legal/ley-39-2015-notificaciones.toml (proposed, not written)`.
- [ ] `P01.S03` - HUMAN GATE, owner: operator, no agent may self-stamp review_status. Operator reviews the S02 draft against the committed corpus and personally commits the entry with review_status=reviewed, confirmed by the legal-catalogue verification suite (verify_legal_reference / registry build validation) passing green against the merged entry. This Step blocks every Step in Phases P02 through P04; `src/cadrumo/_data/registry/aeat/legal/ley-39-2015-notificaciones.toml`.

### Phase `P02` - core typed axis

Add the grounded dias-naturales constant and the orthogonal NotificacionEstadoServicio enum plus its pure computation function; blocked on Phase P01's human review gate.

- [ ] `P02.S04` - Add DEHU_RECHAZO_TACITO_DIAS_NATURALES as a Final int equal to 10 to external_constants.py, doc-commented with the art. 43.2 citation naming the P01.S03 catalogue entry id, and add a grounding test asserting the docstring citation resolves against the reviewed legal catalogue entry, following the existing test_external_constants_centralisation_part2.py pattern; `src/cadrumo/core/external_constants.py, src/cadrumo/core/tests/test_external_constants_centralisation_part2.py`.
- [ ] `P02.S05` - Add a new core module declaring the NotificacionEstadoServicio StrEnum, with members NO_ENTREGADA, ACCEDIDA, EN_PLAZO and RECHAZO_TACITO, and a pure function computing it from fecha_notificacion, leida and an explicit as_of date against DEHU_RECHAZO_TACITO_DIAS_NATURALES, then add boundary tests covering day 9 EN_PLAZO, day 10 RECHAZO_TACITO, fecha_notificacion is None NO_ENTREGADA, and leida is True ACCEDIDA regardless of elapsed days, plus a mutation-proof test that flips the day-10 boundary comparison and confirms the boundary test fails; `src/cadrumo/core/_notificacion_estado_servicio.py, src/cadrumo/core/__init__.py, src/cadrumo/core/tests/test_notificacion_estado_servicio.py`.

### Phase `P03` - wiring: calendar, actionability, notice

Surface the computed service state on the typed calendar event, widen post-filing actionability for deemed-served notifications independent of procedural kind, and extend the operator-facing Notice; blocked on Phase P02.

- [ ] `P03.S06` - Add a typed notificacion_estado_servicio field, typed NotificacionEstadoServicio or None, to OverviewCalendarEvent, and compute it per row in calendar_events_from_notification_snapshots from fecha_notificacion and leida against an explicit as_of parameter threaded from the caller, never an inline date.today call, then add a projection test proving a synthetic ten-day-lapsed row computes RECHAZO_TACITO; `src/cadrumo/application/overview/_calendar.py, src/cadrumo/application/overview/tests/`.
- [ ] `P03.S07` - Widen the actionability predicate behind actionable_post_filing_events so an event is actionable when its post_filing_kind is in ACTIONABLE_POST_FILING_EVENT_KINDS or its notificacion_estado_servicio is RECHAZO_TACITO, then add a mutation-proof test proving a plain NOTIFICACION event carrying RECHAZO_TACITO state appears in actionable_post_filing_events and that reverting the widening back to a bare frozenset membership check fails the test; `src/cadrumo/application/overview/_calendar.py, src/cadrumo/application/overview/tests/`.
- [ ] `P03.S08` - Extend the overview CLI Notice composer to include deemed-served notifications in a warning-severity Notice carrying the P01.S03 legal catalogue entry id and the affected certificado ids on Notice.context, add the new locale keys through python -m dev.locales set with real es, en, ca and hu strings for every key, and run the locale scaffold check; `src/cadrumo/entrypoints/cli/_overview_rendering.py, src/cadrumo/locales/es.yml, src/cadrumo/locales/en.yml, src/cadrumo/locales/ca.yml, src/cadrumo/locales/hu.yml, src/cadrumo/entrypoints/cli/tests/`.

### Phase `P04` - full-tree verification

Run every targeted suite plus the tree-wide vault and locale gates and triage any red signature; blocked on Phases P01-P03 all closed.

- [ ] `P04.S09` - Run the targeted suites sequentially, core tests, the registry legal and catalogue tests, application overview tests and entrypoints cli tests, plus vaultspec-core vault check all and the locales scaffold --check gate, capture full output to a log file per aeat-local-execution, and triage any red signature as owner-surface or unrelated peer churn before closing this Step; `no production files, verification only`.

## Parallelization

Phase P01 is strictly serial: P01.S01 must land before P01.S02 (the draft
cites the committed corpus), and P01.S03 (the human gate) cannot close
before P01.S02 exists. P01.S03 hard-blocks every Step in P02, P03 and P04 -
no later Step may start before it is checked closed.

Within P02, P02.S04 must land before P02.S05, since the pure function in
P02.S05 imports `DEHU_RECHAZO_TACITO_DIAS_NATURALES` from P02.S04.

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
  operator-committed, reviewed entry; the commit itself is the human
  sign-off record.
- P02.S04: the grounding test asserting the constant's citation resolves
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
