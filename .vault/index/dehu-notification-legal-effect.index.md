---
generated: true
tags:
  - '#index'
  - '#dehu-notification-legal-effect'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:5996920d49de03e55524d40616581370a7113253969f0b5feb7bde68614f0fee'
related:
  - '[[2026-08-07-dehu-notification-legal-effect-P01-S01]]'
  - '[[2026-08-07-dehu-notification-legal-effect-P01-S02]]'
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

### plan

- `2026-08-07-dehu-notification-legal-effect-plan` - `dehu-notification-legal-effect` plan

### reference

- `2026-08-07-dehu-notification-legal-effect-reference` - `dehu-notification-legal-effect` reference: `DEHu notification legal-effect grounding`
