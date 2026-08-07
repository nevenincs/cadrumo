---
tags:
  - '#audit'
  - '#code-dedup-sweep'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:82f87c4d1e37863d1f400257fa144819c64510818ecc9490400959fbfb49e5ab'
related: []
---

# `code-dedup-sweep` audit: `Corpus anchor verification: three resolution paths, one unchecked, 320 cites`

## Scope

ADR input. A `corpus_ref` in the legal catalogue takes the form `path#anchor`,
and the anchor asserts that the cited text sits in a particular provision. This
note measures how far that assertion is actually checked.

It supersedes two earlier readings, both produced by this campaign and both
wrong. The first held that the anchor was decorative tree-wide. The second put
the unverified set at 63 cites via a filename heuristic. **The mechanism section
below is the finding; the counts follow from it.**

## Findings

### three-resolution-paths-not-one | high | The resolver has three ways to satisfy an anchor, and only one of them is unchecked

Both earlier censuses were built assuming the resolver matches a unit's
`anchor` field and nothing else. It does not.

1. **Anchor-field match.** Where a sidecar's units carry populated `anchor`
   values, the requested anchor is matched against them and a wrong anchor is
   refused.
2. **Title match**, in `_title_matches_anchor`. A unit whose `anchor` field is
   EMPTY can still resolve by its title. This path is not a loose fallback: it
   canonicalises by stripping non-alphanumerics, **expands Spanish ordinals**
   (`primero` to 1, `segunda` to 2) via a substitution table, normalises article
   prefixes so `a5`, `art-5` and `articulo-5` converge, and applies distinct
   rules per prefix family (`articulo`, `anexo`, `apartado`). It **refuses on
   ambiguity** rather than choosing — two separate raises, one for a duplicated
   anchor and one for an ambiguous match.
3. **Single-unit fallback.** Where a sidecar holds exactly ONE unit, that unit is
   returned for any non-empty anchor. Only the empty string is refused. **This is
   the entire defect.**

Measured examples of paths 1 and 2 working: a 222-unit sidecar returns a
277-character unit for a real anchor and refuses an invented one; a 12-unit
sidecar with zero populated anchor fields returns 476 characters for `#a1`; a
9-unit sidecar returns 1802 characters for `#a5`. Article-sized and precise in
every case.

### two-probe-errors-same-class | high | Both censuses tested a real pattern against the wrong instance

Recorded because the next person to probe this corpus faces the same structure,
and the corrected numbers are less useful than the reason they were wrong.

**Error one, the tree-wide claim.** A positive control showed several nonsense
anchors all resolving to one blob, and that was generalised to the whole tree.
The control was run only against a newly bundled file that happened to be
single-unit. It correctly demonstrated path 3 and said nothing about paths 1 or
2. With 287 of 363 sidecars single-unit, a small sample was always likely to
land there.

**Error two, the broken-cite claim.** A 13-unit sidecar with all anchor fields
empty was probed with `#a1`, refused, and reported as evidence that such files
cannot resolve at all. But `#a1` is not that file's cite — its actual cite is
`#primero`, which resolves to 406 characters. The refusal was **correct
behaviour on a fabricated probe**, presented as a defect.

The shared class: a real pattern tested against the wrong instance. A control
that only ever sees one shape cannot establish the shape is universal, and a
probe invented by the auditor tests the auditor's assumption rather than the
system's contract.

### the-honest-denominator-is-320 | medium | Only the single-unit bucket is unverified, and no heuristic is needed to say so

Of **598** anchored `corpus_ref` entries in the legal catalogue:

* **240** cite a multi-unit sidecar with populated anchors — enforced by path 1.
* **35** cite a multi-unit sidecar with empty anchors — enforced by path 2.
* **320** cite a single-unit sidecar — **unchecked**, path 3.
* **3** point at a derived artefact, treated separately below.

So **275 of 598 are genuinely enforced**. The earlier note would have sent an
ADR author to repair something largely working.

### the-path-isolation-question-is-a-judgement-not-a-regex | medium | Two independent filename heuristics failed in opposite directions and their disagreement was never a measurement

Many of the 320 are harmless because the file itself IS the provision: an orden
extracted per article cannot mislead, since the path carries the precision the
anchor merely repeats. Two attempts were made to compute that subset and both
were wrong at the edges.

One pattern treated any `-a<digit>` as an article marker, so it read a BOE
identifier (`boe-a-2024-12944-...`) as an article and exempted the newest
entry in the catalogue — the one a reviewer would most want counted. A tighter
pattern then over-flagged, requiring a digit after `df` and so classing
`-df-unica` files as unverified when their path plainly names the disposición
final única. A third pass omitted `apartado-` and `-modelo-N` stems entirely.

The gap between the resulting figures was never a measurement disagreement; it
was two guesses at a judgement. **No regex should carry this.** The defensible
statement is that 320 single-unit cites are unchecked, and which of them are
additionally path-isolated is a hand review across the roughly 90 distinct files
behind them, where a human can see at a glance what a pattern cannot.

### derived-artefact-citations-are-a-separate-defect | medium | Three cites point at a markdown extraction rather than a source document

Kept out of the count deliberately. Folding them in would let an anchor decision
resolve while leaving a `corpus_ref` aimed at a rendering that regenerates:

* `corpus/manuals/renta/2025/part1/source.pdf.extracted.md#madrid-minimo-descendientes`
* `corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf.extracted.md#madrid-nacimiento-adopcion`
* the same file, `#madrid-nacimiento-adopcion-limites`

Two files, three cites, anchors that are hand-styled slugs rather than document
anchors.

## Recommendations

Make the single-unit fallback refuse an anchor it cannot match by title, rather
than returning the sole unit unconditionally. The title matcher already exists
and is careful; the fallback bypasses it. That converts 320 silent assertions
into checked ones without touching the 275 that already work.

Do not re-extract broadly. The multi-unit files are working through two
mechanisms, and re-extraction risks reddening entries whose `required_text`
currently passes.

Hand-review the roughly 90 files behind the 320 rather than computing a subset.
Record the review's judgement per file; do not encode it as a naming rule.

Treat the derived-artefact cites as their own decision. A citation should name a
source, and if a manual PDF has no anchorable extraction the honest answer may
be that those three cannot carry an anchor at all.
