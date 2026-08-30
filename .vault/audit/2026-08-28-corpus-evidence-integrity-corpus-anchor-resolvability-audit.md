---
tags:
  - '#audit'
  - '#corpus-evidence-integrity'
date: '2026-08-28'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:6cac0888df78a4c08cb56e21f8eb68cce4529dfea6f5c76288da96dcbe2de949'
related:
  - "[[2026-08-28-registry-legal-grounding-windows-m200-pyme-rate-citation-omission-audit]]"
---

# `corpus-evidence-integrity` audit: `Corpus anchors: 332 resolve, 315 are cosmetic, 55 are false precision`

## Scope

## Findings

## Recommendations

## What this refines

An earlier audit recorded that 226 catalogue entries resolve to a whole
consolidated law, that every one writes an article anchor, and that
`corpus_catalogue.py` says the model "has no anchored dispositive-content reader".
The remediation options ended with "build the anchored reader ... the general fix
and the expensive one".

That framing assumed the anchors would work once a reader existed. They largely
would not, and the number that matters is far smaller than 226.

## Every entry is anchored; less than half resolve

All **702** catalogue entries carrying a `corpus_ref` write an anchor. Checking
each against its bundled file for a matching `id=` or `name=`:

| | count |
|---|---|
| anchor resolves in the bundled document | **332** |
| does not resolve, but the file **is** the provision (excerpt tier) | **315** |
| does not resolve, on a whole document — **false precision** | **55** |

The 315 are cosmetic. `orden-hap-2250-2015:art-1` points at
`orden-hap-2250-2015-art-1.html#a1`: the anchor is redundant because the whole
file is article 1, and a reader that ignored the fragment would still read exactly
the right text. Nothing needs doing to them.

The 55 are the real set, spread over **16 documents**:

| bytes | document | example |
|---|---|---|
| 3.486.623 | `source.pdf.extracted.md` | `madrid-dl-1-2010:art-2 #madrid-minimo-descendientes` |
| 1.921.157 | `ley-35-2006.html` | `ley-35-2006:dt-38` |
| 1.760.893 | `ley-37-1992.html` | `ley-37-1992:art-9-bis` |
| 1.470.202 | `ley-27-2014.html` | `ley-27-2014:da-18` |
| ~470–514 K | six módulos/annual ordenes | `orden-hac-1347-2024:instruccion-2-3-b-3` |

## Why the anchors do not resolve

The bundled BOE captures carry no structural ids. `orden-hac-1347-2024.html` has
25 `id=` attributes and every one is page furniture — `header`, `contenido`,
`activar-menu`, `logo-movil-boe-container`. The document's articles, anexos and
instrucciones are unmarked, so `#anexo-ii-instruccion-2-3-b-3` addresses nothing.

So building the anchored reader would not, on its own, narrow any of these 55. The
corpus would have to be re-captured with structural anchors, or provisions
extracted to excerpt files (the option already recorded as needing no new
machinery), or anchors resolved by heading text rather than id.

## Direction

No liability error. This is evidence strength, and specifically the hazard already
recorded as "a weak check reports the same green as a strong one" — now with a
mechanism. A reviewer reading `ley-35-2006:dt-38 #dt-trigesima-octava-...` sees
what looks like a disposición-scoped citation; the verifiable scope is 1,9 MB.
The anchor's precision is asserted, not delivered, and nothing in the record
distinguishes the two.

## It strengthens an existing finding

The largest offender is the renta-2022 Madrid mínimos entry, already open in this
campaign for pointing one `corpus_ref` at a manual serving six years. It also
carries a non-resolving anchor over a 3,5 MB extracted PDF. Two independent
characterisations of the same row, reached by different routes.

## Not gated

The cosmetic/false-precision split depends on the size floor that separates the
tiers, and a re-captured corpus would move entries between bands legitimately. A
gate on "every anchor resolves" would red the 315 cosmetic entries for no benefit.
The 55-entry list is the deliverable.

No production code, registry data or test was changed by this audit.
