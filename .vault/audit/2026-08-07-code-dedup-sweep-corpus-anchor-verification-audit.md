---
tags:
  - '#audit'
  - '#code-dedup-sweep'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:1858c16c9f8f3b20e4e2441cac46d7565ac2fd43324336fe0d6cab240780e0d1'
related: []
---

# `code-dedup-sweep` audit: `Corpus anchor verification: 91 unchecked cites across 58 files, measured behaviourally`

## Scope

ADR input. A `corpus_ref` in the legal catalogue takes the form `path#anchor`,
and the anchor asserts that the cited text sits in a particular provision. This
note measures how far that assertion is actually checked.

**The sequence matters more than any single figure, because three successive
answers were each a real improvement and each still wrong.** They are recorded
below in order, with what made each one wrong, because the next reader will be
tempted down the same path.

## Findings

### the-answer-took-four-passes | high | Each correction was an improvement and each was still wrong

**Pass one — "decorative tree-wide."** A positive control showed several nonsense
anchors all resolving to the same blob. Generalised to 363 sidecars. It had been
run against exactly one file, which happened to be single-unit; it demonstrated
the single-unit fallback correctly and said nothing about anything else. With
287 of 363 sidecars single-unit, a small sample was always likely to land there.

**Pass two — "63 cites across 31 files."** A structural partition: count units
per sidecar, then split single-unit cites by whether the filename already names
a provision. Better, and wrong twice over. The filename rule read a BOE
identifier (`boe-a-2024-12944-…`) as an article marker and so exempted the
newest entry in the catalogue; a competing rule required a digit after `df` and
so flagged `-df-unica` files whose path plainly isolates. A third variant omitted
`apartado-` and `-modelo-N` stems. The 63-versus-105 gap between two agents was
never a measurement disagreement — it was two guesses at a judgement.

**Pass three — "320 unchecked."** Drop the heuristic, call every single-unit cite
unchecked. Defensible, re-derivable, and still an over-count **by 229**, because
the single-unit branch is GUARDED rather than unconditional. Measured split of
the 320:

* **229** cite a single unit that carries a canonical anchor — **all 229 refuse a
  bogus anchor.** Checked.
* **91** cite a single unit carrying none — **all 91 admit a bogus anchor.**
  Unchecked.

Worked example: `orden-hap-2250-2015-art-1.html#a1` is single-unit and refuses
garbage. Pass three counts it unchecked; behaviourally it is not.

**Pass four — measure behaviour, not structure.** For each cite, resolve its real
anchor, then resolve a deliberately invalid one. Enforced means the real anchor
resolves AND garbage is refused. This accounts for every mechanism automatically,
because it asks the resolver instead of inspecting the sidecar.

### three-resolution-paths-not-one | high | The resolver has three ways to satisfy an anchor, and only one is unchecked

The reason passes one to three kept mis-counting.

1. **Anchor-field match.** Units carrying populated `anchor` values are matched
   against the request; a wrong anchor is refused.
2. **Title match**, in `_title_matches_anchor`. A unit whose `anchor` field is
   EMPTY still resolves by title, and this is not a loose fallback:
   `_canonical_anchor` strips non-alphanumerics, substitutes **Spanish ordinals**
   from a table (`primero` to 1, `segunda` to 2), and collapses article prefixes
   so `a5`, `art-5` and `articulo-5` converge; the matcher then applies distinct
   rules per family — `articulo` an exact numeric match, `anexo` an equality,
   `apartado` a stripped-numeral match. It raises on ambiguity rather than
   choosing, through two separate guards: one for a duplicated anchor, one for an
   ambiguous match.
3. **Single-unit fallback, and it is GUARDED.** Where a sidecar holds exactly one
   unit, that unit is returned only when the unit carries **no** canonical anchor,
   or when its anchor genuinely covers the cited subsection — an article unit
   `#a25` covering a request for `#a25-1-a`. The code says so in its own comment:
   *"A different article remains a missing anchor."* Anything else **falls through
   to the title matcher**, which refuses when nothing matches.

   So the defect is narrower than "single-unit": it is
   **`len(units) == 1` AND the sole unit carries no anchor**. That is the only
   shape where an arbitrary string resolves, and it accounts for exactly the 91.
   Note the exact-anchor check runs FIRST, so a single-unit file whose anchor
   matches never reaches this branch at all.

### the-measurement | medium | 91 unchecked cites across 58 files, and nothing is broken

| | catalogue entries | distinct `path#anchor` |
|---|---|---|
| enforced | 504 | 499 |
| **unchecked** | **91** | **90** |
| derived-artefact | 3 | 3 |
| real anchor refused | **0** | **0** |
| total | 598 | 592 |

Two independent runs. The columns differ only because one counts catalogue
entries and the other distinct assertions — six anchors are cited by more than
one entry. **Both runs agree on 58 files**, which is the actionable unit for
re-extraction, and on the worst offenders: `trlirnr-rdleg-5-2004.html` at 8 cites
and `orden-hfp-105-2017.html` at 4.

**Zero real anchors refuse.** Nothing in the catalogue is broken; the defect is
under-checking, not breakage.

### the-probe | medium | The instrument, so the figure can be re-derived after it goes stale

The number will drift as the corpus grows. This is how it was obtained — no
filename rule, no unit-count proxy, just *does the resolver refuse garbage for
this cite*:

```python
BOGUS = "zzz-no-such-provision-9999"
for path, anchor in every_anchored_corpus_ref():
    if path.endswith((".extracted.md", ".extracted.json")):
        derived += 1; continue
    side = DATA / (path + ".extracted.json")
    def resolves(a: str) -> bool:
        try:
            resolve_anchored_extracted_unit(side, anchor=a); return True
        except Exception:
            return False
    if not resolves(anchor):      real_refused += 1
    elif resolves(BOGUS):         unchecked += 1
    else:                         enforced += 1
```

### two-probe-errors-same-class | high | Both early passes tested a real pattern against the wrong instance

Pass one generalised a control from a single file to the tree. And a later probe
reported a 13-unit sidecar as unresolvable after testing it with a **fabricated**
`#a1` — its real cite is `#primero`, which resolves to 406 characters. The
refusal was correct behaviour on a wrong probe, presented as a defect.

The shared class: **a real pattern tested against the wrong instance.** A control
that only ever sees one shape cannot establish the shape is universal, and an
anchor invented by the auditor tests the auditor's assumption rather than the
system's contract. The behavioural probe avoids both because it uses each cite's
own real anchor as the positive case.

### derived-artefact-citations-are-a-separate-defect | medium | Three cites point at a markdown extraction rather than a source document

Kept out of the count deliberately; an anchor decision would resolve past them
while leaving a `corpus_ref` aimed at a rendering that regenerates:

* `corpus/manuals/renta/2025/part1/source.pdf.extracted.md#madrid-minimo-descendientes`
* `corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf.extracted.md#madrid-nacimiento-adopcion`
* the same file, `#madrid-nacimiento-adopcion-limites`

## Recommendations

Tighten one condition on one branch. The single-unit branch already falls through
to the title matcher when the sole unit carries an anchor that does not cover the
request; it returns unconditionally only when the unit carries **no** anchor. That
one arm — `not _canonical_anchor(unit_anchor)` — is what admits the 91. Making it
fall through as the guarded arm already does converts 91 silent assertions into
checked ones and touches neither the 504 that work nor the extraction pipeline.

Re-extract the 58 files behind those 91 so their units carry real anchors. Do not
re-extract more broadly: the enforced cites are working through two mechanisms
and re-extraction risks reddening entries whose `required_text` currently passes.

Treat the derived-artefact cites as their own decision. A citation should name a
source, and if a manual PDF has no anchorable extraction the honest answer may be
that those three cannot carry an anchor at all.

Prefer the behavioural probe over any structural proxy when this is re-measured.
Three structural partitions disagreed on totals while agreeing on the top of the
list; the behavioural one needs no judgement to trust.
