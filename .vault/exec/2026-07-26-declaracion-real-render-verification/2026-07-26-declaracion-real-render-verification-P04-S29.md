---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:cdeb5914f38ea0a517b4e35fe37ac8e82035929f8bffdd4751e69f6a7135125a'
step_id: 'S29'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Register the Modelo 100 coverage floor as an evidence gap under D2, since three specimens from one filer with every box populated cannot ground one

## Scope

- `.vault/exec`
- `src/cadrumo/_data/registry/aeat/modelos/100`

## Description

The word-level parser fix takes Modelo 100 from fabricating every value to
recovering 21 of 21 on all three real specimens, which means the profile now
passes at its declared `min_coverage` of 1. That is exactly the shape a green
suite can be mistaken for evidence, so it is registered rather than left implied.

The floor is inherited, not evidenced. It was set before any real render had been
read, and nothing has since been measured that would ground it.

## Outcome

The floor stays at 1 and is recorded as an evidence gap under D2.

Two independent reasons the specimens cannot ground it, either of which is
sufficient:

**One filer.** All three renders are the same taxpayer's annual declarations for
2021, 2022 and 2023. D2 forbids setting a floor from one filer's specimens
precisely because it encodes that filer's shape, and this is the case the
governing decision was written about.

**Every box populated.** All 21 targets carry a value on all three. The specimens
therefore demonstrate what a fully-completed Modelo 100 yields and say nothing at
all about what the form yields when a filer legitimately leaves an optional box
blank -- which is the only question a floor answers. A floor of 1 refuses any
such filing.

The practical exposure is that Modelo 100 is the largest profile in the estate at
21 targets across five revisions, and the two revisions with the most filings
ahead of them, 2024 and 2025, have no specimen at all. A single blank optional
box on a real 2024 filing would be refused with `fail_hard`.

What would close this: a real render from a **second filer**, ideally one whose
declaration leaves at least one profile target blank. That is the same specimen
class the render-language register names, so one acquisition could serve both.

No registry change was made. Lowering the floor on the evidence available would
repeat the error in the opposite direction -- guessing a number from three
documents rather than inheriting one from none.

## Notes

This Step exists because the fix succeeding is what makes the gap invisible. When
Modelo 100 was excluded from the real-render gate the floor was obviously
unevidenced; now that it passes, the same unevidenced floor reads as confirmed by
a green suite. The enrolment point in the gate's module docstring says so
explicitly, so a reader arriving from the code rather than the vault meets the
caveat too.

Worth pairing with the anti-vacuity guard when either is next touched. Modelo 100
supplies the first bundled specimens that score full coverage, so that guard now
rests entirely on Modelo 390 and Modelo 111 falling short of 1.0. Acquiring a
sparser Modelo 100 render would strengthen both this floor question and that
guard at once.

The semantic code index was truncated throughout, roughly 1027 chunks against
roughly 4546 files, while reporting itself healthy. No semantic result was relied
on.
