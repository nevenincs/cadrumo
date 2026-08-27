---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:c7b4193b7fac6adf4e531a74e242575911492ba29db45e06da6588f1ce8025c7'
related: []
---

# `tui-architecture` audit: verification power across the registry

## Why this, and not a list of bad tests

The tautology hunt asks of any calculation test: "would this fail if the registry
formula were wrong against AEAT?" Reading the suite for individually bad tests
found none worth reporting. What it found instead is that the question mostly
cannot be answered in the affirmative, because for most of the registry there is
no AEAT authority in the tree to fail against.

`test_external_oracle_grounding_enrolled.py` already holds the oracle RELATION at
zero in both directions: no bundled oracle value is stranded, and no declared
grounding claim lacks evidence. That gate is sound and this audit does not
disturb it. Its own docstring names what it does not measure: "Enrollment ... is
a ceiling; verification POWER is the count of casillas whose engine value is
reconciled against an AEAT-authoritative expected value."

Nothing reports that number. This audit reports it.

## The measurement

Taken with the repository's own fold, `audit_bundled_external_grounding()`, not a
reimplementation.

- 26 bundled external oracle evidence entries.
- 128 registry revisions audited.
- **12 revisions have at least one independently checked casilla. 116 have none.**

Coverage within the 12, as `independent_check_coverage`:

| modelo | checked casillas | coverage |
|---|---|---|
| 322 | 3 | 100 % |
| 353 | 3 | 100 % |
| 390 | 3 | 75 % |
| 303 | 10 | 38 % |
| 200 | 3 | 30 % |
| 100 | 29 | 15.5 % |
| 202 | 1 | 7.7 % |
| 100 | 8 | 5.1 % |
| 100 | 8 | 4.7 % |
| 303 | 1 | 3.6 % |
| 100 | 5 | 3.3 % |
| 100 | 4 | 1.9 % |

The two modelos at 100 % reach it with three casillas each. Modelo 100, the
IRPF flagship, peaks at 15.5 % and has a revision at 1.9 %.

The 116 uncovered revisions span 58 modelos, including every revision of 184,
763, 714, 131, 165, 308, 309, 490 and 194, and single revisions of 111, 115,
130, 190, 193, 210, 216, 296, 347, 360 and 720.

## What follows from it

For those 116 revisions every numeric assertion in the suite rests on arithmetic
someone authored. That is not the same as saying those tests are wrong -- most
are continuity and wiring assertions that legitimately test structure rather than
an AEAT figure, and they are honest about it. It does mean that a systematic
engine error in those revisions would be reproduced by the tests rather than
caught, which is precisely the failure mode `no-silent-under-declaration`
describes: "A value reconciled only against the app's own engine cannot catch a
systematic engine error the filing matches."

## A gate weakness worth an owner's ruling

The existing gate's coverage assertions are `assert audit.inventory.evidence`,
`assert audit.rows` and `assert audit.checked_revision_count` -- all non-emptiness
checks. Deleting 25 of the 26 bundled oracle payloads would leave every assertion
green, provided no revision still DECLARES a grounding claim for the deleted
evidence. Verification power can therefore fall silently.

The obvious remedy is a floor, and `aeat-quality-gates` forbids exactly that:
"Never hardcode an exact count as a pass condition... Gate on the property, not
the tally." A raw count floor would trade one defect for a rule violation, so the
shape of the ratchet is a genuine design decision and is left to an owner rather
than guessed at here.

## Checked and found SOUND

`test_modelo_202_cuota_base_ejercicio_anterior_continuity.py` is the reference
shape for a non-tautological registry assertion and should be copied. It derives
the wiring assertion from the live snapshot parameter, and separately pins the
statutory 18 % (LIS art. 40.2) as a literal whose only job is to catch registry
drift. Its comments reason about the tautology risk explicitly.

The 130 assertions whose expected side reads the system under test were reviewed
and are, on inspection, overwhelmingly carry-forward and wiring invariants over
test-authored inputs -- structural claims, not AEAT numeric claims.

## Probe limitation, stated

The provenance classifier (`tautology_scan.py`) sorts by keyword and cannot
recognise an oracle test that binds its expected value to a plain `expected`
variable; it reported zero oracle-derived assertions, which is false. Its buckets
are not trustworthy as counts and were used only to select candidates for reading.
The coverage figures above come from the repository's own fold, not from it.
