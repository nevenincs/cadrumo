---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:07459d2123ebdc4606664ad4160f37f477d110e3340806d725d0fae171fd5b64'
related: []
---

# `tui-architecture` audit: `A third of legal citations resolve to a whole consolidated law, so required_text proves little`

## Finding

226 of the 702 legal-catalogue entries carrying a `corpus_ref` resolve to a
**whole consolidated law**, the largest being Ley 35/2006 at 1,9 MB, cited by 84
entries. For those, the `required_text` evidence check is satisfied by a phrase
appearing anywhere in the document. Every one of them writes an article anchor —
`#a66` — and the anchor cannot narrow the search.

This is not an oversight, and the codebase says so.

## The mechanism, in the code's own words

`registry/corpus_catalogue.py` declares two corpus tiers and validates the excerpt
tier by filename convention, giving the reason:

> …this model has no anchored dispositive-content reader
> (`SourceReference.corpus_path` carries no `#anchor`), so filename convention is
> the only signal it can verify; rename to the convention or remove the claim

So `full_consolidated` sources are checked for being genuinely full (a size
floor), and `provision_excerpt` sources must carry a provision-suffixed filename
(`-art`, `-apartado`, `-anexo`, `-da`, `-dt`, `-df`, `-se`, `-pr`, `-ar`,
`-redacciones`). The tiering is deliberate and enforced. What it cannot do is
narrow a full-consolidated source to the provision the citation names, because
the anchor lives on `LegalReference.corpus_ref` and never reaches the reader.

| corpus target | entries |
|---|---|
| whole consolidated law (> 200 KB) | 226 |
| per-article excerpt | 476 |

## The consequence, with a worked example

The evidence gate already audits rather than enforces — it compares the declared
phrase against the source and never against the encoded value. Whole-law
resolution weakens the audit further: over a 1,9 MB document, almost any short
phrase is present, and every numeral is present somewhere.

Modelo 100's 2024 savings scale is the demonstration.
`renta-2024-escala-estatal-base-ahorro` cites `ley-35-2006:art-66`, whose
`corpus_ref` is `ley-35-2006.html#a66`. The article's current redaction states the
top tranche as **"En adelante 15"**; the parameter encodes **0.14**, which is the
correct figure for filing year 2024. A numeric sweep asking "does the cited source
state every encoded number" reports this parameter **clean**, because `14` occurs
somewhere in the whole law — an article number, a tranche of another scale, a
date. The contradiction between the cited article and the encoded value is
invisible to any check operating at file granularity.

The contrast is instructive: the superseded redaction has its own excerpt file,
`ley-35-2006-art-66-2023.html`, where the same sweep would be tight. The two tiers
sit side by side on the same article.

## Direction

No liability error arises from this alone. It is an evidence-strength finding:
for roughly a third of citations, "the required text appears in the source"
carries much less information than the same sentence carries for the other
two-thirds, and nothing in the record distinguishes the two when reading a
parameter.

The under-watched direction is that a *weak* check reports the same green as a
strong one. A reviewer auditing a parameter sees `required_text` satisfied and has
no signal that satisfaction was cheap.

## Remediation — owner's decision, not taken here

Three shapes, in increasing cost:

1. **Surface the tier.** Nothing today tells a reader of a parameter whether its
   citation resolves to 1,9 MB or to one article. Exposing `corpus_tier` alongside
   the citation would let a reviewer weight the evidence correctly, and costs no
   new verification.
2. **Prefer excerpts for value-bearing citations.** Where a parameter encodes a
   figure, cite a provision excerpt rather than the consolidated instrument. The
   excerpt convention and its validator already exist; `art-66-2023` shows the
   shape.
3. **Build the anchored reader.** The comment names exactly what is missing. This
   is the general fix and the expensive one, and it would also make the numeric
   sweeps meaningful on the 226.

Option 2 is the one that would have caught the Modelo 100 case, and it needs no new
machinery.

No production code, registry data or test was changed by this audit.

## A partial mitigation for readers: anchor on the citation's own `required_text`

The whole-law problem has no fix for an automated numeric sweep, but it has one
for a person or agent reading a provision. The catalogue entry's `required_text`
is guaranteed present in the file — the evidence gate refuses otherwise — so it is
a reliable landmark into a 1,9 MB document where the article heading is not.

Worked example, from verifying the Ley 12/2023 rental-reduction tiers. Searching
`ley-35-2006.html` for the article heading found two occurrences of `Artículo 23.`
and neither segment contained the tier percentages: one is a table-of-contents
line and the other an unrelated later match. Anchoring instead on
`ley-35-2006:art-23`'s own declared phrase `"el 3 por ciento sobre el mayor"`
landed inside the article body immediately, and the four tiers sit within 1.500
characters of it:

> …se reducirá: a) En un **90 por ciento** cuando se hubiera formalizado por el
> mismo arrendador un nuevo contrato … situada en una zona de mercado residencial
> tensionado, en el que la renta inicial se hubiera rebajado en más de un 5 por
> ciento … b) En un **70 por ciento** cuando no cumpliéndose los requisitos …
> el arrendatario tenga una edad comprendida entre 18 y 35 años …

with the 60 % and 50 % tiers following. That confirmed
`renta-2024-rental-reduccion-rate-tier-{50,60,70,90}` — all four correct, and
cited to the right redaction: `ley-35-2006:art-23` is windowed 2024-01-01 onward,
while `art-23-2021` (2021-07-11 → 2023-12-31) is the excerpt carrying the old flat
`"se reducirá en un 60 por ciento"`. The redaction split is exactly right for a
Ley 12/2023 change effective 2024.

Two things this does not fix, both already recorded above. The citation still
resolves to the whole law, so no sweep can check it. And this entry's
`required_text` pins `"el 3 por ciento sobre el mayor"` — the amortisation rate,
not any tier — so the evidence record says nothing about the four values it is
being used to ground.

**Use the `required_text` as the entry point when reading a whole-law citation.**
Article headings are unreliable landmarks in these files; the declared phrase is
the one string the gate guarantees.
