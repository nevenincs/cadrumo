---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:554fa6cc82e2f39a870cce74ebfc5beba6de05099dc34f8d4779170c1722a642'
step_id: 'S40'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Bundle RD 1619/2012 articles 6 and 11 from BOE consolidated text, since only article 2 ships today and article 6 is the authority the schema field set derives from

## Scope

- `src/cadrumo/_data/corpus/normatives/html`

## Description

- Fetch articles 6 and 11 verbatim from the BOE consolidated text of RD 1619/2012 and bundle them beside the existing article 2, following the same document shape and `data-source-url` anchor convention.
- Record in the research document the three provisions that settle findings previously argued from inference, and the two further requirements nothing tracks yet.

## Outcome

Two corpus documents added: `rd-1619-2012-art-6.html` (8404 bytes, 1151 words) and `rd-1619-2012-art-11.html` (1765 bytes, 219 words). Article 2 was the only bundled article before this.

Article 6 is the authority the canonical schema's field set derives from, which is why this Step precedes the schema work rather than following it. Reading it settled three questions that had been argued from inference:

- **6.1.i** requires the operation date, or the pago anticipado date, whenever it differs from the issue date. Broader than the finding it settles: the same provision covers both, so ONE field serves the article 75.Uno devengo and the article 75.Dos prepayment carve-out, with a discriminator for which role it carries. Two separate date fields would contradict how the regulation treats the datum.
- **6.1.d** makes the destinatario's NIF obligatory in exactly three enumerated cases, not universally. The record's unconditional requirement is therefore stricter than the regulation, and the fix is a conditional keyed to those cases, never a global relaxation.
- **6.1.a** requires a serie with numbering correlative within it, and a specific serie for rectificativas. So serie is a first-class identity component rather than a prefix convention inside the number, and because a rectificativa is identifiable by its serie, serie and invoice class are coupled and cannot be modelled independently.

## Verification

```
rg -c "se haya recibido el pago anticipado" rd-1619-2012-art-6.html     -> 1
rg -c "Numero de Identificacion Fiscal del destinatario ..." art-6.html -> 1
rg -c "antes del dia 16 del mes siguiente" rd-1619-2012-art-11.html     -> 3
```

Both documents parse as HTML and yield the expected word counts. The three load-bearing phrases the downstream Steps cite are present verbatim.

## Notes

**A shell heredoc corrupted the text and the corruption was caught before it landed.** Article 6 apartado 3 cites `articulo 2.3.b).b').a'')`, whose doubled apostrophes terminated the bash heredoc early. The first attempt silently simplified that cross-reference to make the write succeed. Bundled legal text is the authority other documents are validated against, so a convenience edit to it is a fabrication however small; the reference was restored verbatim through a writer that does not interpret quoting. Worth stating because the failure mode is invisible -- the file would have looked complete and read plausibly.

**Two requirements found here have no Step yet.** Article 6.1.f requires any descuento or rebaja not included in the unit price to be stated, and a search for descuento and rappel returns zero files. Article 6.1.j requires an exempt operation to cite the provision exempting it, and the record stores a category but no citation. Both are recorded on the rollout tracker rather than left in prose, because prose-only findings are what produced the two dormant-capacity defects this campaign already carries.

**Article 6.5 is deliberately out of scope.** The VERI*FACTU QR and AEAT verification phrase are obligations on the invoicing SYSTEM, not fields of the invoice record, and belong to their own decision.
