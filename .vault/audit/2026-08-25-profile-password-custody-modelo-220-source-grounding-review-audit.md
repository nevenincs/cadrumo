---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:cba8a9c2d7608ae9d0c921c68932cf7f04716ab173b737f31d38a179baa160ea'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `modelo 220 source grounding review`

## Scope

Reviewed W06.P12.S259's bounded Modelo 220 revision data, its renamed BOE
source record, every changed source reference, and the focused registry test
against the accepted temporal-coverage decision and the source-grounding
reference. The review checked 2025 period applicability despite 2026
publication, preservation of applicability-only authority, independent
regression witnesses, and absence of new registry projection logic.

## Findings

### authority-grade-witness | medium | The regression test does not independently pin applicability grade

The production diff leaves revision `2025` at `authority_grade =
"applicability"`, which is the correct non-fileable disposition. However,
`test_modelo_220_2025_sources_match_the_revision_window` asks for a snapshot
using `grade=revision.effective_authority_grade`. That expectation is derived
from the same revision under test, so an accidental future promotion of the
revision's authority grade would change both sides together and this test would
still pass. The source identifiers and 2025 dates are independently pinned;
the equally important no-upgrade claim is not.

Resolution: resolved in the S259 change before closure. The focused test now
asserts `revision.authority_grade is
RegistryAuthorityGrade.APPLICABILITY` and requests the real authority snapshot
with the literal `RegistryAuthorityGrade.APPLICABILITY` grade. An accidental
promotion can no longer move the test input and expectation together. Re-review
found no remaining severity findings and approves S259.

## Recommendations

For `authority-grade-witness`, assert the revision's effective grade against
the literal applicability-grade enum and request the snapshot with that
literal grade. Keep the existing exact source identifiers and bounded dates.
