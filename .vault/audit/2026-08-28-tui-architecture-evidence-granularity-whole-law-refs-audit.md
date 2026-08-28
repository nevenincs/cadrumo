---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:caa58fa76f4bd8499b1dabf1fe02b01c7f5e233d8b4cb549aa72c54f427e9553'
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
