---
tags:
  - '#exec'
  - '#dehu-notification-legal-effect'
date: '2026-08-07'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:4a866f72dabccf4b533e518e3aed0df1c5d890b8dcbf63c3d9a8399c67f183d6'
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
    "se entenderán practicadas en el momento en que se produzca el acceso a su contenido",
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

**Correction applied after the draft was first recorded.** The first
`required_text` phrase originally read `se entenderá practicadas`; the
provision reads `se entenderán practicadas` (plural, agreeing with
"las notificaciones"). `verify_legal_reference` checks every
`required_text` phrase for presence in the resolved corpus unit, so the
draft as first recorded would have refused the `P01.S03` gate with
"corpus text missing required text". Confirmed by running
`verify_legal_reference` against the committed sidecar with a positive
control: the original phrasing refuses, the corrected phrasing passes. The
TOML above now carries the corrected phrase; nothing was written under
`src/cadrumo/_data/registry/aeat/legal/`.

**Independent live-BOE cross-check of the figure.** The BOE consolidated act
page for `BOE-A-2015-10565` was re-fetched and all six bundled art. 43
paragraphs matched the committed excerpt verbatim after whitespace and
entity normalisation. The window is "diez días naturales"; the article
contains no "días hábiles" and no "quince días" wording. The page carries
seven per-block amendment annotations, none of them on art. 43, but
per-block annotation is demonstrably incomplete (the Ley Orgánica 3/2018
reference appears on the page while art. 28 carries no per-block note), so
the excerpt header's refusal to claim art. 43 is unamended since 2015
stands and is independently reproduced.

Both corrected `required_text` phrases sit at offsets 603 and 816 of the
1366-character normalised excerpt, outside the 220-character heading window
and above the 1200-character unchecked-body floor, so the entry does not
join the heading-only population the required-text ratchet gate caps.
