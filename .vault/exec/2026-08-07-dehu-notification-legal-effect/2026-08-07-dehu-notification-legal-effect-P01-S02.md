---
tags:
  - '#exec'
  - '#dehu-notification-legal-effect'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:0665d608e85a7174768c85ad5f05eb69c6466f3643035a2dc651502e50d3a2cd'
step_id: 'S02'
related:
  - "[[2026-08-07-dehu-notification-legal-effect-plan]]"
---

# Draft the candidate ley-39-2015-notificaciones.toml LegalReference entry (id, kind=ley, corpus_ref, required_text carrying the diez-dias-naturales phrase verbatim) as a proposal recorded only in this Step's execution record, and do NOT commit it to the registry, since LegalReference.review_status is typed Literal reviewed and cannot represent an unreviewed draft on disk

## Scope

- `src/cadrumo/_data/registry/aeat/legal/ley-39-2015-notificaciones.toml (proposed`
- `not written)`

## Description

- Drafted the candidate `LegalReference` entry for Ley 39/2015 art. 43.2 in
  this Step's execution record only. It is a proposal for the operator to
  review and personally commit; it was NOT written to any file under the
  registry legal catalogue tree.
- Sourced `published_at` (2015-10-02, BOE núm. 236) and `effective_from`
  (2016-10-02, one year after publication per the law's own "Disposición
  final séptima. Entrada en vigor" — art. 43 is not among the provisions
  the same disposición defers to 2021-04-02) directly from the fetched BOE
  act page, the same source `P01.S01` bundled the article text from.
- Chose `required_text` phrases that are distinctive to this provision alone
  (the diez-días-naturales clause and its preceding sentence) rather than a
  phrase authored to match itself.

## Outcome

**Proposed content for
`src/cadrumo/_data/registry/aeat/legal/ley-39-2015-notificaciones.toml`
(not written to disk):**

```toml
# Ley 39/2015, de 1 de octubre, del Procedimiento Administrativo Comun de
# las Administraciones Publicas - general non-modelo-scoped administrative
# procedure grounding, following the lgt-autoliquidacion.toml / censo.toml
# topic-file precedent.
#
# - art-43.2: regimen de notificaciones por medios electronicos. Grounds
#   the diez-dias-naturales rechazo tacito window for a notification put
#   at the taxpayer's disposal (DEHu) but not accessed.

[legal."ley-39-2015:art-43.2"]
evidence_tier = "legal_authority"
authority = "boe"
kind = "ley"
corpus_ref = "corpus/normatives/html/ley-39-2015-art-43.html#a43"
document_id = "BOE-A-2015-10565"
article = "43.2"
permalink = "https://www.boe.es/buscar/act.php?id=BOE-A-2015-10565#a43"
published_at = 2015-10-02
effective_from = 2016-10-02
review_status = "reviewed"
reviewed_at = 2026-08-07
reviewed_by = "operator"
notes = "Ley 39/2015 art. 43.2: regimen de notificaciones por medios electronicos. Una notificacion electronica se entiende practicada en el momento del acceso a su contenido; cuando es de caracter obligatorio o elegida por el interesado, se entiende rechazada -legalmente servida pese a no haberse accedido- transcurridos diez dias naturales desde la puesta a disposicion sin acceso. El plazo corre desde la puesta a disposicion (fecha_notificacion), no desde el acceso (leida). No se ha comprobado de forma exhaustiva la existencia de un plazo de notificacion mas especifico para un procedimiento AEAT concreto que desplace este regimen general; solo se descartaron RD 1363/2010 (remite al regimen general) y LGT art. 112 (notificacion por comparecencia, supuesto distinto)."
required_text = [
    "se entenderá practicadas en el momento en que se produzca el acceso a su contenido",
    "se entenderá rechazada cuando hayan transcurrido diez días naturales desde la puesta a disposición de la notificación sin que se acceda a su contenido",
]
```

`reviewed_at`/`reviewed_by` above are placeholders inside the DRAFT text
showing the shape the operator's own review stamp would take — they are not
an agent self-stamping the entry; nothing carrying these values has been
written to disk. The operator sets the real `reviewed_at`/`reviewed_by` at
the moment they personally review and commit `P01.S03`.

## Verification

Not applicable to this Step: `LegalReference.review_status` is typed
`Literal["reviewed"]`
(`src/cadrumo/domain/calculations/registry/_schema_references.py:132`), so no
unreviewed draft can be constructed or validated against the pydantic model
without asserting a review that has not happened. The catalogue verification
suite named in the plan's `P01.S03` gate runs against the operator-committed
entry, not against this draft.

Confirmed instead that nothing was written under the registry legal tree:

    git status --porcelain -- src/cadrumo/_data/registry/aeat/legal/

produced no output — the directory is unchanged by this Step.

## Notes

`P01.S03` (the human review-and-commit gate) is deliberately left untouched.
No file was created, staged, or modified under
`src/cadrumo/_data/registry/aeat/legal/`, and no `review_status = "reviewed"`
value was written to disk by this Step.
