---
generated: true
tags:
  - '#index'
  - '#dehu-notification-legal-effect'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:6ee7675bafbd9e791323aecc65f74f4999ab0681b2ccd64e6badefd48dc3da3f'
related:
  - '[[2026-08-07-dehu-notification-legal-effect-P01-S01]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P01-S02]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P02-S04]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P02-S05]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P03-S06]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P03-S07]]'
  - '[[2026-08-07-dehu-notification-legal-effect-adr]]'
  - '[[2026-08-07-dehu-notification-legal-effect-plan]]'
  - '[[2026-08-07-dehu-notification-legal-effect-reference]]'
---

# `dehu-notification-legal-effect` feature index

Auto-generated index of all documents tagged with `#dehu-notification-legal-effect`.

## Documents

### adr

- `2026-08-07-dehu-notification-legal-effect-adr` - `dehu-notification-legal-effect` adr: `DEHu notification legal-effect and service state` | (**status:** `accepted`)

### exec

- `2026-08-07-dehu-notification-legal-effect-P01-S01` - Reuse the campaign's already-primary-sourced BOE consolidated PDF for Ley 39/2015 at boe.es buscar pdf 2015 BOE-A-2015-10565-consolidado.pdf, art. 43 at page 35, rather than re-deriving it, taking the LAST version if the payload bundles historical redactions, never passing the text through a shell since a truncating heredoc silently loses text, and reading the committed file back before trusting it. The consolidated PDF does not annotate which articles were amended, confirmed by positive control against art. 28, so absence of a marker on art. 43 establishes only that this is todays operative text, and no unamended-since-2015 claim may be made anywhere downstream. Commit the HTML plus its extracted sidecars, verified by resolve_anchored_extracted_unit resolving the target anchor with no CorpusAnchorResolutionError
- `2026-08-07-dehu-notification-legal-effect-P01-S02` - Draft the candidate ley-39-2015-notificaciones.toml LegalReference entry (id, kind=ley, corpus_ref, required_text carrying the diez-dias-naturales phrase verbatim) as a proposal recorded only in this Step's execution record, and do NOT commit it to the registry, since LegalReference.review_status is typed Literal reviewed and cannot represent an unreviewed draft on disk
- `2026-08-07-dehu-notification-legal-effect-P02-S04` - Add DEHU_RECHAZO_TACITO_DIAS_NATURALES as a Final int equal to 10 to external_constants.py, doc-commented with the Ley 39/2015 art. 43.2 provision citation and its BOE-A-2015-10565 document id in the same style as every sibling leaf constant in that file, and deliberately NOT naming any legal-catalogue entry id, because an entry id cited before the catalogue file exists ships a dangling reference into production source. Verified by the constant importing cleanly and by the external-constants centralisation AST gates staying green
- `2026-08-07-dehu-notification-legal-effect-P02-S05` - Add a new core module declaring the NotificacionEstadoServicio StrEnum, with members NO_ENTREGADA, ACCEDIDA, EN_PLAZO and RECHAZO_TACITO, and a pure function computing it from fecha_notificacion, leida and an explicit as_of date against DEHU_RECHAZO_TACITO_DIAS_NATURALES, then add boundary tests covering day 9 EN_PLAZO, day 10 RECHAZO_TACITO, fecha_notificacion is None NO_ENTREGADA, and leida is True ACCEDIDA regardless of elapsed days, plus a mutation-proof test that flips the day-10 boundary comparison and confirms the boundary test fails
- `2026-08-07-dehu-notification-legal-effect-P03-S06` - Add a typed notificacion_estado_servicio field, typed NotificacionEstadoServicio or None, to OverviewCalendarEvent, and compute it per row in calendar_events_from_notification_snapshots from fecha_notificacion and leida against an explicit as_of parameter threaded from the caller, never an inline date.today call, then add a projection test proving a synthetic ten-day-lapsed row computes RECHAZO_TACITO
- `2026-08-07-dehu-notification-legal-effect-P03-S07` - Widen the actionability predicate behind actionable_post_filing_events so an event is actionable when its post_filing_kind is in ACTIONABLE_POST_FILING_EVENT_KINDS or its notificacion_estado_servicio is RECHAZO_TACITO, then add a mutation-proof test proving a plain NOTIFICACION event carrying RECHAZO_TACITO state appears in actionable_post_filing_events and that reverting the widening back to a bare frozenset membership check fails the test

### plan

- `2026-08-07-dehu-notification-legal-effect-plan` - `dehu-notification-legal-effect` plan

### reference

- `2026-08-07-dehu-notification-legal-effect-reference` - `dehu-notification-legal-effect` reference: `DEHu notification legal-effect grounding`
