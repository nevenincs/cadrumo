---
tags:
  - '#audit'
  - '#code-dedup-sweep'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:ad9953458f5facbd484aa26c30973a312563d39fdfc95c3fd56975355b4a554a'
related: []
---

# `code-dedup-sweep` audit: `Corpus anchor verification: the unverified set is 63 cites across 31 files, not tree-wide`

## Scope

ADR input. A `corpus_ref` in the legal catalogue takes the form `path#anchor`, and
the anchor asserts that the cited text sits in a particular provision. This note
measures how far that assertion is actually checked.

It supersedes an earlier reading that the anchor was decorative tree-wide. That
reading came from a positive control run against a single file which happened to
be single-unit: the control correctly demonstrated the single-unit fallback and
was then generalised to the whole tree. A control that only ever sees one shape
cannot establish that the shape is universal.

## Findings

### anchors-are-enforced-on-multi-unit-files | low | The resolver checks anchors precisely wherever a sidecar carries more than one unit

Full census of all 363 sidecars under `corpus/normatives/html`: **1690 units, of
which 1280 carry a populated anchor.** Not zero.

Measured against a 222-unit sidecar, the resolver returns a **277-character**
unit for a real anchor and REFUSES an invented one. That is an article-sized
extract, not a document. Where a file has several units the citation is precise
and a wrong anchor fails loudly.

### single-unit-fallback-is-the-actual-mechanism | medium | With exactly one unit the resolver returns it regardless of anchor, so any non-empty string resolves

287 of 363 sidecars hold exactly one unit. For those, every non-empty anchor
resolves to the same blob and only the empty string is refused. That is the
whole of the defect, and it is a property of the fallback rather than of anchors
in general.

### the-actionable-set-is-63-cites-across-31-files | medium | Most single-unit cites are harmless because the PATH already isolates the provision

Of 598 anchored `corpus_ref` entries in the legal catalogue:

* **277** cite a multi-unit file, where the anchor is enforced.
* **256** cite a single-unit file whose filename already names the provision, for
  example an orden extracted per article. The file IS the article, so the path
  carries the precision and the anchor is redundant rather than false. Nobody can
  be misled by `...-art-1.html#a1`.
* **63** cite a single-unit file that is a WHOLE DOCUMENT, where the anchor is the
  only thing claiming to isolate the provision and nothing checks it. This is the
  actionable set.

Per-file, the 63 across 31 files: `trlirnr-rdleg-5-2004.html` (8: a2, a10, a13,
a13-1-h, a24, a25-1-a, a25-1-b, a25-1-f); `orden-hfp-105-2017.html` (4);
`orden-eha-1881-2011`, `orden-eha-3021-2007`, `orden-eha-3290-2008`,
`orden-eha-3514-2009`, `orden-hac-1197-2025`, `orden-hac-1400-2018`,
`orden-hac-177-2020`, `orden-hac-342-2021`, `orden-hac-3580-2003`,
`orden-hac-510-2021`, `orden-hac-539-2003`, `orden-hac-590-2021`,
`orden-hac-612-2021`, `orden-hac-66-2002`, `orden-hac-72-2024`,
`orden-hac-85-2003`, `orden-hap-2368-2013`, `orden-hap-2455-2013`,
`orden-hap-2486-2014`, `orden-hfp-1314-2022`, `orden-min-2000-12-15-m341` (2
each); `orden-eha-3851-2007`, `orden-eha-586-2011`, `orden-eha-2887-2008`,
`orden-hac-1023-2021-modelo-714`, `orden-hac-657-2025` (1 each); and
`boe-a-2024-12944-rdl-4-2024-iva-alimentos.html#a1`.

### my-own-classifier-had-false-negatives-in-both-directions | low | The filename heuristic is not sound and the union needs a hand review

The loose pattern treated any `-a<digit>` as an article marker, so it exempted
`boe-a-2024-12944-...` — a BOE identifier, not an article. That wrongly excluded
the newest and most recently authored entry from the risky set, which is exactly
the entry a reviewer would most want counted.

A tighter pattern then over-flagged in the other direction: two `-df-unica`
files carry no digit after `df`, so a rule requiring one calls them risky when
their path genuinely isolates the disposición final única.

Both patterns are wrong at the edges. At 31 files the union is small enough to
review by hand, and the ADR should not rest on either regex.

### derived-artefact-citations-are-a-separate-defect | medium | Three cites point at a markdown EXTRACTION rather than a source document

Kept out of the 63 deliberately. Folding them in would let an anchor decision
resolve while leaving a `corpus_ref` aimed at a derived artefact nobody would
think to re-check:

* `corpus/manuals/renta/2025/part1/source.pdf.extracted.md#madrid-minimo-descendientes`
* `corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf.extracted.md#madrid-nacimiento-adopcion`
* the same file, `#madrid-nacimiento-adopcion-limites`

Two files, three cites. The anchors are hand-styled slugs rather than document
anchors, so these assert precision against a rendering that regenerates.

## Recommendations

Make the single-unit fallback refuse an anchor it cannot match, rather than
returning the sole unit unconditionally. That converts 63 silent assertions into
loud ones without touching the 277 that already work or the 256 that are
redundant-but-harmless.

Re-extract only the whole-document files behind those 63 so their units carry
real anchors. Re-extracting the wider set risks reddening entries whose
`required_text` currently passes on a whole-document read, for no gain.

Treat the derived-artefact cites as their own decision. A citation should name a
source, and if a manual PDF has no anchorable extraction the honest answer may be
that those three entries cannot carry an anchor at all.
