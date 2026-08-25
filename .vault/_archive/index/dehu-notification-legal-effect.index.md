---
generated: true
tags:
  - '#index'
  - '#dehu-notification-legal-effect'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:ab84848fad6df48642cf9e754a725f8d7104eb1ac25326eaf0a0cbdd0e2edd32'
related:
  - '[[2026-08-07-dehu-notification-legal-effect-P01-S01]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P01-S02]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P01-S03]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P01-S10]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P02-S04]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P02-S05]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P02-S11]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P03-S06]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P03-S07]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P03-S08]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P04-S09]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P04-summary]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P05-S12]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P05-S13]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P05-S19]]'
  - '[[2026-08-07-dehu-notification-legal-effect-adr]]'
  - '[[2026-08-07-dehu-notification-legal-effect-plan]]'
  - '[[2026-08-07-dehu-notification-legal-effect-reference]]'
  - '[[2026-08-13-dehu-notification-legal-effect-audit]]'
---

# `dehu-notification-legal-effect` feature index

Auto-generated index of all documents tagged with `#dehu-notification-legal-effect`.

## Documents

### adr

- `2026-08-07-dehu-notification-legal-effect-adr` - `dehu-notification-legal-effect` adr: `DEHu notification legal-effect and service state` | (**status:** `accepted`)

### audit

- `2026-08-13-dehu-notification-legal-effect-audit` - `dehu-notification-legal-effect` audit: `P04.S09 verification review`

### exec

- `2026-08-07-dehu-notification-legal-effect-P01-S01` - Reuse the campaign's already-primary-sourced BOE consolidated PDF for Ley 39/2015 at boe.es buscar pdf 2015 BOE-A-2015-10565-consolidado.pdf, art. 43 at page 35, rather than re-deriving it, taking the LAST version if the payload bundles historical redactions, never passing the text through a shell since a truncating heredoc silently loses text, and reading the committed file back before trusting it. The consolidated PDF does not annotate which articles were amended, confirmed by positive control against art. 28, so absence of a marker on art. 43 establishes only that this is todays operative text, and no unamended-since-2015 claim may be made anywhere downstream. Commit the HTML plus its extracted sidecars, verified by resolve_anchored_extracted_unit resolving the target anchor with no CorpusAnchorResolutionError
- `2026-08-07-dehu-notification-legal-effect-P01-S02` - Draft the candidate ley-39-2015-notificaciones.toml LegalReference entry (id, kind=ley, corpus_ref, required_text carrying the diez-dias-naturales phrase verbatim) as a proposal recorded only in this Step's execution record, and do NOT commit it to the registry, since LegalReference.review_status is typed Literal reviewed and cannot represent an unreviewed draft on disk
- `2026-08-07-dehu-notification-legal-effect-P02-S04` - Add DEHU_RECHAZO_TACITO_DIAS_NATURALES as a Final int equal to 10 to external_constants.py, doc-commented with the Ley 39/2015 art. 43.2 provision citation and its BOE-A-2015-10565 document id in the same style as every sibling leaf constant in that file, and deliberately NOT naming any legal-catalogue entry id, because an entry id cited before the catalogue file exists ships a dangling reference into production source. Verified by the constant importing cleanly and by the external-constants centralisation AST gates staying green
- `2026-08-07-dehu-notification-legal-effect-P02-S05` - Add a new core module declaring the NotificacionEstadoServicio StrEnum, with members NO_ENTREGADA, ACCEDIDA, EN_PLAZO and RECHAZO_TACITO, and a pure function computing it from fecha_notificacion, leida and an explicit as_of date against DEHU_RECHAZO_TACITO_DIAS_NATURALES, then add boundary tests covering day 9 EN_PLAZO, day 10 RECHAZO_TACITO, fecha_notificacion is None NO_ENTREGADA, and leida is True ACCEDIDA regardless of elapsed days, plus a mutation-proof test that flips the day-10 boundary comparison and confirms the boundary test fails
- `2026-08-07-dehu-notification-legal-effect-P03-S06` - Add a typed notificacion_estado_servicio field, typed NotificacionEstadoServicio or None, to OverviewCalendarEvent, and compute it per row in calendar_events_from_notification_snapshots from fecha_notificacion and leida against an explicit as_of parameter threaded from the caller, never an inline date.today call, then add a projection test proving a synthetic ten-day-lapsed row computes RECHAZO_TACITO
- `2026-08-07-dehu-notification-legal-effect-P03-S07` - Widen the actionability predicate behind actionable_post_filing_events so an event is actionable when its post_filing_kind is in ACTIONABLE_POST_FILING_EVENT_KINDS or its notificacion_estado_servicio is RECHAZO_TACITO, then add a mutation-proof test proving a plain NOTIFICACION event carrying RECHAZO_TACITO state appears in actionable_post_filing_events and that reverting the widening back to a bare frozenset membership check fails the test
- `2026-08-07-dehu-notification-legal-effect-P01-S03` - HUMAN GATE, owner: operator, no agent may self-stamp review_status. Operator reviews the S02 draft against the committed corpus and personally commits the entry with review_status=reviewed, confirmed by the legal-catalogue verification suite (verify_legal_reference / registry build validation) passing green against the merged entry. This Step blocks every Step that RESOLVES the catalogue entry, namely P02.S11, P03.S08 and P04.S09, plus the P01.S10 closeout that records it. It does NOT block P02.S04, P02.S05, P03.S06 or P03.S07, which depend only on the corpus committed in P01.S01
- `2026-08-07-dehu-notification-legal-effect-P01-S10` - Scaffold P01.S03's execution record through vaultspec-core vault add exec, citing the operator's review commit sha and the green legal-catalogue verification run, then check the P01.S03 row. Carried as its own row rather than a note, because a row checked with no exec record makes delivered-as-specified and recorded-but-not-implemented wear the same checkbox. Blocked on the operator's commit
- `2026-08-07-dehu-notification-legal-effect-P02-S11` - Add the catalogue-resolution grounding test asserting the DEHU_RECHAZO_TACITO_DIAS_NATURALES doc citation resolves against the operator-reviewed ley-39-2015 art-43.2 legal catalogue entry, following the existing test_external_constants_centralisation_part2.py pattern, and extend the constant's doc comment to name that entry id only once the entry exists on disk. This is the half of the original S04 row that genuinely depends on the human review gate, split out so the constant itself is not held behind it. Read the entry id off the COMMITTED registry TOML, never off external_constants.py. The constant's current comment cites only the provision and its BOE document id, so there is no id already present there to check a new one against, and an id copied from the wrong surface would resolve to nothing while reading as grounded. The corrected P01.S02 draft spells it ley-39-2015 colon art-43.2. Blocked on P01.S03
- `2026-08-07-dehu-notification-legal-effect-P03-S08` - Extend the overview CLI Notice composer to include deemed-served notifications in a warning-severity Notice carrying the P01.S03 legal catalogue entry id and the affected certificado ids on Notice.context, add the new locale keys through python -m dev.locales set with real es, en, ca and hu strings for every key, and run the locale scaffold check
- `2026-08-07-dehu-notification-legal-effect-P04-S09` - Run the targeted suites sequentially, core tests, the registry legal and catalogue tests, application overview tests and entrypoints cli tests, plus vaultspec-core vault check all and the locales scaffold --check gate, capture full output to a log file per aeat-local-execution, and triage any red signature as owner-surface or unrelated peer churn before closing this Step
- `2026-08-07-dehu-notification-legal-effect-P04-summary` - `dehu-notification-legal-effect` `P04` summary
- `2026-08-07-dehu-notification-legal-effect-P05-S12` - Prove the canonical DEHu route and remote-operation guard permit only authenticated read-only notification fetches and refuse acknowledge, mark-read, comparecer, submit, present, and every other AEAT mutation before transport.
- `2026-08-07-dehu-notification-legal-effect-P05-S13` - Verify active-profile and authenticated-session preconditions with sanctioned read-only diagnostics, record only presence and readiness facts, and stop for the operator if login, certificate, or Cl@ve interaction is required.
- `2026-08-07-dehu-notification-legal-effect-P05-S19` - Reproduce the production custody regression through a real isolated create setup-interruption process-restart and login lifecycle using the file backend and original passphrase, then identify the first commit and invariant that permits encrypted bucket state to outlive its only master-key route.

### plan

- `2026-08-07-dehu-notification-legal-effect-plan` - `dehu-notification-legal-effect` plan

### reference

- `2026-08-07-dehu-notification-legal-effect-reference` - `dehu-notification-legal-effect` reference: `DEHu notification legal-effect grounding`
