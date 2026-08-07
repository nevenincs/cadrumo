---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:c42ec14ac28b4c18b9ec47e209d727b9562cc9cb4f14c45732b638b5248fc518'
step_id: 'S18'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# add FiledHistoryDiscoveryReport combining the AEAT_REGISTER_OPTIONS combobox signal and the PROFILE_APPLICABILITY expected grid into one provenance-tagged walk set per (modelo, ejercicio) pair, verified by a test asserting a pair present in both signals carries both provenance tags and a pair present in only one carries only that tag

## Scope

- `src/cadrumo/application/live/_filed_data_capture.py`

## Description

- Add `FiledHistoryDiscoveryPair` and `FiledHistoryDiscoveryReport` carrying per-pair provenance.
- Add `filed_history_discovery_report` unioning the two signals additively.
- Promote all three on the `application.live` facade.
- Add the both-tags, single-tag, additivity and asymmetry tests.

## Outcome

The union REMEMBERS which signal nominated each pair instead of discarding that
once the grid is built, because a zero-row outcome means different things per
signal and code that cannot tell them apart cannot report either honestly.

The asymmetry lives on the pair as a predicate, not in the consumers. A caller
asks the pair rather than re-checking tags, so the rule cannot be reimplemented
differently in several places -- which matters because the advisory consumer is a
later Step in another Phase.

The union is additive by construction: a signal set is only ever added to, so the
register's option list can widen the grid and can never remove a pair the profile
expected. An option list offering NOTHING leaves the profile grid intact, which
is the behaviour an unconfirmed signal must have -- an absent option cannot be
distinguished from a list that never lists it.

Being ALSO offered by the register does not downgrade a profile expectation: the
union is additive in coverage, never in standing. The signal tuple is
canonicalised to declaration order and deduplicated so two equal nominations
compare equal, and an empty signal set is refused because a pair nominated by
nothing is not walked.

## Verification

    uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_history_discovery.py -q -n 0
    26 passed in 19.26s

The partition test asserts the profile-expected and register-only sets are both
disjoint AND total against the pair set, so a pair cannot fall out of both
projections unnoticed.

    MUTATION anomaly-predicate-signal-blind: control=True mutated=False -> PASS (test would red)
    MUTATION union-replaced-by-intersection: control=True mutated=False -> PASS (test would red)

## Notes

Landed in the peer sweep `24f8fd9add`; content verified byte-identical and not
re-committed.
