---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S12'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Register the fully-exposed profiles as D3 evidence gaps naming the English-render specimen class that would unblock each

## Scope

- `.vault/exec`

## Description

Under D3 an untestable profile is an evidence gap, never a pass. The language
route needs the same treatment: a profile whose patterns are Spanish-only has not
been shown to work in another language, and it has not been shown to fail either.
It is undecided, and the specimen that would decide it does not exist.

The register below is the exposure measurement read as a work list. Every entry
is blocked on the same specimen class, so the unblocking condition is stated once
rather than nineteen times: **a real AEAT justificante of that modelo, filed
through the sede with a non-Spanish language selected, sanitised to the existing
`real_corpus` standard.** One such render exists in the whole corpus, for Modelo
390, which is why exactly one profile could be widened.

## Outcome

Nineteen profiles are registered as blocked. Every one of their `named_label`
targets depends on Spanish prose, so each would extract nothing at all from a
render in another language, and each is recorded as undecided rather than
verified.

Ordered by how much is at stake, counting targets that would be lost:

- Modelo 100, five revisions, 21 targets each, 105 in total. The largest exposure
  in the estate and the only modelo where every revision is affected.
- Modelo 303, two revisions, 12 and 4. The worked example: this profile was
  certified against four Spanish facsimiles during this campaign and would read
  nothing from an English render of the same form.
- Modelo 349, 4 targets. Modelo 180, 190, 193 and Modelo 232 on both revisions,
  3 each. Modelo 369, 2. Modelo 840, 2. Modelo 036, 184, 347 and 720, 1 each.
  Modelo 115, 5.

Eight profiles need no specimen and are not registered, because they are immune
by construction: Modelo 111 at 29 targets, Modelo 130 at 19, Modelo 131 on three
revisions at 15 each, Modelo 123 on two at 14 and 8, and Modelo 202 at 4. They
anchor on printed box numbers, which AEAT does not translate.

Modelo 390 is partially decided and is the only profile in that state: four
targets evidenced and widened, one blocked on a page the render omits, five
immune.

## Notes

Two things about this register that a later reader should not have to rediscover.

The gaps are not equally cheap to close. A single English render of one modelo
decides that modelo only, so nineteen specimens would be needed to close the
register outright. That is the argument for treating the structural alternative
as the real remedy rather than specimen acquisition, which is assessed separately.

The register is also not the whole hazard, and the part it omits is inference
rather than measurement. It counts renders in another language because that is
the failure this campaign observed and can evidence. AEAT's sede serves the
co-official languages as well, and a Catalan or Galician render would defeat a
Spanish-and-English alternation exactly as an English one defeats a Spanish-only
pattern -- but **nothing in this repository evidences that**. No sidecar carries a
language field and no bundled document mentions either language, so the claim
rests on how the sede is known to work.

Stated as a bound rather than an estimate: the register is a lower bound on the
exposure. Anyone claiming the render-language route closed should say which
languages that claim covers, because closing it for English is what the evidence
can support.

The semantic code index was truncated throughout, roughly 1027 chunks against
roughly 4546 files, while reporting itself healthy. No semantic result was relied
on; the register derives from loading every revision through the registry
authority.
