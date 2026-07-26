---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S05'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Fold every verified specimen into the shared real-render gate and prove the gate bites for each

## Scope

- `src/cadrumo/adapters/inbound/declaracion/tests`

## Description

Six real specimens were folded into the shared real-render gate alongside the
five AEAT-published facsimiles it already carried: the Modelo 390 annual, the
four Modelo 111 quarters, and the Modelo 190 annual. Modelo 100 is deliberately
excluded, for the reason recorded under Notes.

Three structural changes were needed before the fold.

The gate selected profiles on `artefact_kind == "declaracion"`. That field is a
free-form `str` on the profile schema, and the registry splits it between
`"declaracion"` and `"declaration_pdf"` across the tree, so the filter would have
matched nothing for Modelo 100 and Modelo 190 and read as "this modelo has no
declaration profile" rather than as an error. The selector now mirrors the
production one, keying on the closed `surface` enum together with the accepted
artefact kinds, and asserts exactly one match rather than taking the first.

The two specimen families prove different things, so they are modelled
separately. The facsimiles carry AEAT's own worked-example figures and therefore
support arithmetic checks against the form's printed totals. The real-corpus
specimens carry AEAT's layout, printed labels and blank boxes, but their
sanitiser overwrote every monetary amount with a single constant, so no printed
arithmetic survives on them. Treating the two as one family would have meant
either inventing arithmetic that does not hold or dropping the value check
entirely.

The replacement value check is grounded outside the profile. Each specimen's
redaction manifest declares what the sanitiser wrote; the gate parses those
declared constants and asserts every extracted amount is one of them. Count
targets are exempt and named per specimen, read off the printed column header.

## Outcome

The module went from 16 to 42 cases and all pass. The full declaracion suite
passes (`227 passed`), `ruff` and `ty` are clean over the package, and
`pytest --collect-only -q` collected 14708 tests with exit 0 immediately before
the commit.

Every gate was proven to bite by breaking what it guards and observing the
failure, then restoring from a copy taken beforehand and confirming the restored
file's digest matched. No gate is claimed to be a gate on the strength of having
passed.

Reverting one English label alternate fails the extracted-set assertion for
`390/2021-0A`, naming `iva.anual.cuota-deducible-total` as unexpectedly absent,
with 41 other cases still green. Raising the Modelo 390 floor from 0 to 0.5 fails
five cases across the accept, set, manifest-constant, blank-box and anti-vacuity
assertions. Pointing a real-corpus row at a synthetic fixture fails the
provenance premise with the declared provenance quoted back.

The manifest-constant check was proven against the defect it exists to catch.
Driven at Modelo 100 using the gate's own helpers, it refuses all 21 targets on
each of the three real specimens, 63 refusals in total, reporting values such as
`0545 = Decimal('10010000.50405')` against a declared constant of `1000.00`. The
casilla set and the coverage ratio both pass on those same specimens, so this is
the only assertion in the module that catches them.

The blank-box guard was proven with production code and no patching. Calling
`_classify_target` on Modelo 390 box 662, which is printed blank on the real
render, returns missing while the guard is armed and `Decimal('662')` when the
guard is given no printed number to compare against.

## Notes

Modelo 100 is not enrolled and this is a deliberate refusal rather than an
omission. Its three real renders print the box number in a six-point font whose
x-range overlaps the nine-point amount, word assembly merges the two into one
token, and all 21 targets on all three specimens yield a value that is neither
the printed amount nor a parse failure, while coverage scores 1.0 against a floor
of 1. Enrolling it would have required weakening the manifest-constant assertion
to accommodate it, which reproduces exactly the green-suite-over-a-broken-profile
pathology this module exists to end. Step S03 stays open and the defect is
reported to the coordinator; the fix belongs in word assembly, which is outside
this phase's file grant.

Two type diagnostics in this module and one in the fixture-naming gate were
resolved while here. All three pre-existed at HEAD, confirmed by running the type
checker against the committed version of the file, so they are not regressions
from this work; they were closed because both files fall within this step's grant
and they were reddening the package type gate.

One registry test is red and is not this step's: the production source-ref
literal gate fails naming `cadrumo/application/modelo/_reconcile.py:283`, a
pydantic field default in a file this step never touched and which carries no
uncommitted changes. Attribution was confirmed rather than assumed by reverting
this step's registry change to the committed version and re-running the test,
which still failed. The registry suite otherwise passes, 3029 tests, run
sequentially to avoid the loader-cache race.

The semantic code index was truncated throughout, roughly 1027 chunks against
roughly 4546 files, while reporting itself healthy with an empty
degraded-reasons list. No semantic result was relied on anywhere in this phase.
