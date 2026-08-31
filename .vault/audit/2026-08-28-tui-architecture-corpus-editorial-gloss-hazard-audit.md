---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:baeb372d67ef8bc470a4322534c5faa22ee667e9a745c09897bfb039bdf1bb45'
related: []
---

# `tui-architecture` audit: `Five corpus files mix BOE text with an editorial gloss; no citation currently relies on it`

## Finding

Five of the 476 bundled normative corpus files carry an **appended editorial
gloss** — authored commentary sitting in the same file as the BOE text, closing
with a `Fuente:` attribution. The `required_text` evidence gate cannot distinguish
the two, so a phrase drawn from the commentary would validate as if it were the
law.

**No current citation relies on the gloss.** All 18 `required_text` phrases across
those five entries resolve to BOE text. The hazard is latent, and this audit
records it before it is load-bearing rather than after.

## The files, and what the gloss adds

`ley-19-1991-art-30`, `-art-31`, `-art-4-9`, `ley-35-2006-art-49`, `-art-93`.

`ley-19-1991-art-31.html` is the clearest case. Paragraphs 0–4 are the verbatim
BOE text of art. 31 Uno and letters a) to c), ending:

> c) En el supuesto de que la suma de ambas cuotas supere el límite anterior, se
> reducirá la cuota del Impuesto sobre el Patrimonio hasta alcanzar el límite
> indicado, sin que la reducción pueda exceder del **80 por 100**.

Paragraph 5 is commentary restating the same rule, and paragraph 6 the
attribution:

> El límite conjunto fija que la suma de la cuota íntegra del Impuesto sobre el
> Patrimonio y de las cuotas del IRPF no exceda del 60 por **ciento** … la
> reducción no puede exceder del 80 por **ciento** de la cuota íntegra del IP — es
> decir, el sujeto pasivo satisface, como mínimo, el **20 por ciento** de la cuota
> íntegra del Patrimonio (**suelo del 20 por ciento**).

The gloss is not wrong — it is a correct reading of art. 31. That is what makes it
hazardous. Three phrasings appear **only** there: "80 por ciento" (the BOE writes
"80 por 100"), "20 por ciento", and "suelo del 20 por ciento". An author reaching
for the modern spelling, or for the floor the law states only by implication,
would write a `required_text` that the gate happily validates against commentary
authored in this repository.

That is the failure mode `aeat-calculation-grounding` names — an excerpt authored
from a secondary source, with a self-certifying `required_text` — reached by a
different route: not a fabricated file, but a real file with authored text
appended.

## What the current entries do, correctly

`ley-19-1991:art-31` declares `required_text = ['60 por 100', 'bases imponibles',
'más de un año', 'no sean susceptibles de producir los rendimientos', '80 por
100']`. Every phrase is BOE text, and it deliberately uses the BOE's **"por 100"**
rather than the gloss's "por ciento". It also pins the number. This is the right
shape and the reason the hazard is not live.

Classified with the repository's own `normalise_corpus_text` — the same fold the
gate uses — over the full file text with the gloss paragraphs subtracted: 18 of 18
phrases BOE, none gloss-only.

## Direction

None today; the values are correct and the citations sound. The exposure is to
future authorship, and it is asymmetric in an unhelpful way: a gloss-derived
`required_text` would *pass*, so nothing would ever surface it. Unlike a missing
phrase, which the gate refuses loudly, a phrase matching commentary is
indistinguishable from a phrase matching law.

## Remediation — owner's decision, not taken here

The cheap option is to mark the gloss so it can be excluded — a wrapper element,
or moving the commentary into the legal entry's `notes` where it belongs and
leaving the corpus file as pure BOE text. The latter is more faithful: a file
under `corpus/normatives/` should contain the normative text and nothing else, and
the commentary is genuinely useful where a reader of the catalogue entry will find
it.

Either way the gate could then assert that every `required_text` resolves against
normative text only. Note that five files is small enough to fix by hand and large
enough that the next one will be added without noticing.

## Method note: ABSENT is a free correctness oracle

This classification took three attempts, and each wrong version was caught by a
contradiction rather than by review.

The first used a fixed 900-character window before `Fuente:` and flagged art. 31's
`'80 por 100'` as gloss-only — a phrase already read in the BOE letter c). The
second split on `<p>` only and reported phrases `ABSENT` from the file entirely.

**`ABSENT` is impossible for a registry that loads.** The evidence gate refuses a
`required_text` that is not present in its source, so any corpus-membership probe
reporting a phrase absent has proved a defect in itself, not in the registry. That
is a free oracle: it costs nothing, and it caught two successive probe bugs here.
Use it on any future corpus sweep.

No production code, registry data or test was changed by this audit.
