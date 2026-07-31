---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:2455d5edb8c61061b37efc594c1fd1efccb376ba6f4592660fc4a0a3c3602df2'
step_id: 'S25'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

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
