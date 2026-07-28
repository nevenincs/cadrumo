---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S25'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace declaracion-real-render-verification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S25 and 2026-07-26-declaracion-real-render-verification-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Make every synthetic fixture generator set the canonical producer signature, since only one of three does and the provenance gate's discriminator rests on that invariant holding and ## Scope

- `src/cadrumo/tests/fixtures` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Make every synthetic fixture generator set the canonical producer signature, since only one of three does and the provenance gate's discriminator rests on that invariant holding

## Scope

- `src/cadrumo/tests/fixtures`

## Description

- Establish which generators set the canonical producer signature and which do not.
- Give the signature a single owner instead of a literal repeated per generator.
- Route all three generators through it and regenerate the affected corpora.

## Outcome

One of three generators set the signature. The other two did not, and both failed in the direction that makes synthetic bytes read as real.

The borrador writer set no producer at all, so reportlab stamped its own default. The n26 writer set the bare string naming the rendering library. The discriminator treats an unsignatured producer as evidence of real, externally-authored origin, so those six files would have been read as genuine documents by any gate that asked, the n26 ones as real bank statements.

The signature now has one owner in the fixtures package root and all three generators read it from there. That is the substantive change rather than a tidying one: the invariant the discriminator rests on was previously asserted by twenty-four independent literals across three modules, and the two modules that disagreed with the other twenty-three are precisely the defect. A constant cannot drift from itself.

The borrador and n26 corpora were regenerated so the committed bytes carry the signature, and both were verified to read back correctly. The justificante corpus was not regenerated and must not be: that directory holds real sanitised specimens alongside synthetic ones, and its generator would overwrite them.

## Notes

The justificante sidecar writer emits byte-identical output to what is committed. An earlier version of this change also recorded the producer inside the sidecar, which would have made the generator write something different from every committed sidecar without regenerating any of them. That was removed, on its own merits as well.

The corpora's consumers were run rather than assumed unaffected, the n26 provider tests and the full borrador adapter suite, because regeneration changes bytes and neither corpus pins its hashes anywhere that would have caught a difference.

Not addressed, and worth naming. The discriminator still cannot distinguish a real PDF carrying no producer from a synthetic one whose generator omitted the signature. This change makes the project invariant true again, but the invariant is still what the discrimination rests on, and a fourth generator added later would silently disarm it for its own output. Nothing currently detects that.
