---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:510a5ee9005f87d1e3571135100249c9f499071e26e8626988b3f3144a05e754'
step_id: 'S32'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

# SCOPE CLAIM FALSIFIED AT HEAD - re-derive the CLUSTER verdict, carry the ratified pairwise one, and fix the comparator from the registry rather than from a constant. The row was written on the premise that the tree holds TWO per-casilla money comparisons and reasoned from a six-axis ruling over that pair to the conclusion that the cluster needs no merge remedy. There are FOUR members - detect_casilla_divergences at application/modelo/_reconcile_casilla.py:93, compare_calculation_to_filed_observation at domain/calculations/registry/_filed_state.py:95, casillas_a_recapture_would_change at application/live/_filed_data_capture.py:1249, and the revision-versus-revision delta at application/modelo/_projection.py:835. What died is the SCOPE inference, not the pairwise verdict, because a pairwise verdict does not depend on the size of the population around it. The ratified ruling held by lead-handover on the first two, constraint-shape-divergent on six axes with substitutability failing in BOTH directions, is CARRIED BY REFERENCE and MUST NOT be re-run. Four pairwise questions remain open and not five. MEASURED EVIDENCE from lead-live-sync, who landed the sibling half at f907b137f4 - tolerance is NOT a constant to choose but a regulatory value the registry publishes per verification expectation and folds min-strictest on RegistrySnapshot.verification_policy. Bundled values re-verified after 4395a2db04 - modelo 303 publishes BOTH 0.00 and 0.01 on every revision so it folds to EXACT equality, 720 and 184 and 190 fold to 0.00, and 131 and 117 and 123 and 187 and 188 and 714 fold to 0.01. No single constant can be correct across that set. The fix is therefore cheaper than it reads - _filed_state.py:137 compares with a bare inequality and the function takes no tolerance parameter, but the caller already holds the authority, since application/registry/__init__.py reads snapshot.revision.casillas at 415 through 417 two lines above the call at 418, so snapshot.verification_policy().tolerance is already in scope and this is ONE argument rather than threading a snapshot through three layers. ERROR DIRECTION, which must be argued explicitly because the wrong reading looks conservative - the sibling comparator UNDER-reported by hardcoding 0.01 and absorbing real divergence on 303, whereas this one OVER-reports by comparing exactly on the six modelos that publish 0.01, so a legitimate cent of rounding surfaces as filed-state drift on the shipped aeat registry verify-filed-state verb. That is false-positive noise, and noise is what trains an operator to stop reading a channel, so comparing exactly is NOT the safe default it appears to be. CAVEAT that is easy to miss - verification_policy RAISES RegistryValidationError when a revision declares no verification expectations, which is not a rare shape. lead-live-sync chose to fall back to exact equality there and documented why, that no published contract means no authority to widen, and that guessing strict yields a visible finding while guessing loose yields a silent omission. Decide that fallback explicitly on this path rather than inheriting it. Note - recapture_divergences is already a live CONSUMER of the unruled casillas_a_recapture_would_change, landed at 86a9002581. Gate - the four open pairs each carry a recorded substitutability verdict, the ratified pair is cited rather than re-run, the comparator reads its tolerance from the registry authority rather than any literal, the no-expectations fallback is decided explicitly, and a test pins the contract across at least modelo 303 and one 0.01 modelo precisely because they disagree so no constant can pass, following test_reconcile_tolerance_is_registry_published.py

## Scope

- `src/cadrumo/domain/calculations/registry/_filed_state.py`
- `src/cadrumo/application/registry`
- `src/cadrumo/application/modelo`
- `src/cadrumo/application/live`

## Description

Originally recorded PART-DELIVERED with the plan checkbox deliberately left
unchecked, because the row's gate had a clause this change did not itself
satisfy. See the RECONCILED note below: that clause is now confirmed
satisfied by evidence outside this record, and the checkbox is closed
accordingly.

Delivered, exactly as the row specifies:

- `compare_calculation_to_filed_observation` takes a `tolerance: Decimal = Decimal("0")` parameter, comparing `abs(local - filed) > tolerance` instead of a
  bare inequality — matching `detect_casilla_divergences`'s existing shape and
  rationale.
- The one caller, `application/registry/verify_filed_state`, resolves
  `snapshot.verification_policy().tolerance` through a new
  `_registry_verification_tolerance` helper and passes it — the ONE argument
  the row predicted, since the snapshot was already in scope two lines above
  the call site.
- The no-verification-expectations fallback is decided EXPLICITLY on this
  path (`except RegistryValidationError: return Decimal("0")`), mirroring
  `application/modelo/_pulled_filing_reconcile._registry_reconcile_tolerance`'s
  same decision and rationale rather than inheriting it silently.
- Three new tests in `domain/calculations/registry/tests/test_filed_state.py`
  pin the contract against two REAL bundled modelos that disagree — 303
  folds to `0.00`, 130 folds to `0.01` — so a hardcoded constant could not
  pass either the default-is-exact test or the explicit-tolerance-absorbs-it
  test.

RECONCILED IN A LATER SESSION — the row's OTHER clause, "the four open pairs
each carry a recorded substitutability verdict," is now confirmed satisfied,
closing the gap this record originally left open. At the time this half was
written the substitutability question was believed unresolved for the two
pairs not yet adjudicated. It was not: an already-committed change, dated
BEFORE this row's own text was authored, had already run the
substitutability pre-filter across all six pairs of the four-member cluster
and recorded a "not substitutable with X because Y" verdict beside each of
the four sites, keyed on the ABSENCE CONTRACT (three-way: reported,
ignored-as-wider-extraction, or treated-as-zero) rather than the tolerance
everyone had assumed was the discriminator. The ratified pair is cited
rather than re-run, exactly as this row's remedy already required. This
record did not find that prior commit when it was written; it surfaced only
while adjudicating `P02.S33`'s own two comparators, which is why the
correction lands here rather than in a fresh row.

`P02.S33` has since separately adjudicated and proven the TOLERANCE question
for the two comparators this record left open — a distinct axis from the
substitutability verdict clause this note reconciles — closing the last
open question this row's own gate named.

## Outcome

COMPLETE. Every clause of the row's gate is now satisfied: the four open
pairs (in fact all six pairs of the cluster) carry a recorded
substitutability verdict; the ratified pair is cited, not re-run; the
comparator reads its tolerance from the registry authority rather than a
literal; the no-expectations fallback is decided explicitly; and a test pins
the contract across two real, disagreeing bundled modelos.

Code: `domain/calculations/registry/_filed_state.py`,
`application/registry/__init__.py`. Tests:
`domain/calculations/registry/tests/test_filed_state.py` (+3). `ruff check`,
`ruff format --check`, `ty check`, `basedpyright` all clean on the touched
files; `pytest` on the touched test file green (14/14, the 11 pre-existing
plus the 3 new).

## Notes

The row's own text already carried nearly the whole implementation —
exact file, exact line, exact one-argument fix, exact fallback decision —
which is why this half landed cleanly in one pass with no design detour, in
contrast to `P01.S13` in the same session.

The substitutability-verdict correction above is a reminder that a partial
record's own "not delivered" framing is only as good as the search that
produced it — checking whether a clause was reworked IN THIS SESSION is not
the same question as whether it is already true of the tree, and the two
were conflated here originally.
