---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:c525ff3fdf8efb6c0c53f29863f32abae0b3bd362e99520e586e5b769aa3694d'
related: []
---

# `tui-architecture` audit: `M360's 400/50 refund minimums cite the plazo article and appear nowhere in the cited Orden`

## Finding

`modelo-360-quarterly-refund-threshold-eur` (400,00 EUR) and
`modelo-360-annual-refund-threshold-eur` (50,00 EUR) both declare
`legal_refs = ["orden-eha-789-2010:art-4"]`. That article establishes neither
figure. Neither figure appears anywhere in the cited Orden, in digits or in
words. The `required_text` cross-check passes without pinning a number, so the
evidence gate cannot catch it.

This is a **citation** defect, not a claim that the values are wrong. 400 and 50
are the amounts EU law fixes for this refund; what is missing is a provision in
the catalogue that says so.

## Evidence

The parameter file
(`_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/parameters/0001-refund-thresholds.toml`)
states in its own comment:

> IVA refund eligibility thresholds per Orden EHA/789/2010 art. 4: refund
> requests below €400 per quarter (€50 per annual final-period filing) are not
> accepted by the AEAT processing surface.

The cited article resolves. `orden-eha-789-2010:art-4` is catalogued in
`legal/iva.toml` with `corpus_ref =
"corpus/normatives/html/orden-eha-789-2010-art-4.html#a4"`, and that file exists.
Its complete text is 504 bytes:

> Artículo 4. Plazo de presentación del formulario 360 de solicitud de devolución
> del Impuesto sobre el Valor Añadido soportado por empresarios o profesionales
> establecidos en el territorio de aplicación del Impuesto. El plazo para la
> presentación de la solicitud de devolución se iniciará el día siguiente al final
> del período de devolución y concluirá el 30 de septiembre siguiente al año
> natural en el que se hayan soportado las cuotas a que se refiera.

It is the **plazo** article. It fixes a deadline — 30 September — and says
nothing about any monetary threshold. The only numbers in it are `30`, `360` and
the article number.

Nor is this a case of citing the wrong article of the right norm. Parsed over the
full bundled Orden (43.170 characters of extracted text), neither `400` nor
`cuatrocientos` occurs at all. The apparent `50 euros` matches are substrings of
`250 euros`, and both that and the `1.000 euros` beside it govern **when invoice
copies must accompany a request** — a documentation rule, not a refund minimum.

### The cross-check is vacuous

Both parameters declare:

```toml
required_text = ["devolución del Impuesto sobre el Valor Añadido"]
```

That phrase appears in art. 4's own title, so the evidence gate is satisfied by a
provision that establishes neither value. This is a concrete instance of the
recorded class of parameters whose `required_text` pins no number: the gate
confirms a document was read, not that it states the figure encoded.

## Direction

**Over-payment.** These thresholds gate refund eligibility. A threshold that is
wrong, or that drifts because nothing authoritative anchors it, suppresses a
legitimate refund claim: the taxpayer has borne the IVA and does not recover it.
Nothing in the verification apparatus watches that direction — it is built against
under-declaration, and a suppressed refund produces a valid return, no refusal and
no signal.

The exposure is bounded today by the values being, as far as this audit can tell,
the correct ones. The defect is that their correctness rests on nothing the
registry can check.

## Where the figures actually come from — and why this is blocked

The minimum refund amounts for non-established claimants are set by Directive
2008/9/EC art. 17 and carried into Spanish law through LIVA art. 119: 400 EUR
where the refund period is less than a calendar year but at least three months,
and 50 EUR where the period is a calendar year or the remainder of one. That
matches the quarterly/annual split the two parameters encode.

**Neither text is bundled.** The corpus ships LIVA per article, and the sequence
runs `... 117-bis, 122 ...` — there is no `ley-37-1992-art-119.html`. No
Directive 2008/9/EC text is bundled either.

So the correct citation cannot be authored from what is in the tree, and authoring
a corpus excerpt from a secondary source is forbidden precisely because the
`required_text` gate would then be self-certifying — which is the failure mode
this parameter already exhibits.

## Remediation — owner's decision, not taken here

1. Bundle LIVA art. 119 from the consolidated BOE text, taking the **last**
   version rather than the first, and asserting the amending norm's identifier.
2. Re-point both parameters' `legal_refs` at the provision that states the amount,
   keeping `orden-eha-789-2010:art-4` only if a plazo reference is independently
   wanted.
3. Replace the `required_text` with a phrase that pins the digits, so the
   cross-check can fail.

Step 3 is worth doing regardless of steps 1 and 2: a `required_text` that cannot
discriminate is the mechanism by which this went unnoticed.

No production code, registry data or test was changed by this audit. The values
were not altered — per the standing rule, the oracle follows the fix, and here
there is no fix to the numbers, only to what vouches for them.
