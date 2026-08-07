---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:36d56834d0975862e93e31cc434135aff571ba82843573620d92daad6d7c41e1'
step_id: 'S05'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# add a parity test capturing the same synthetic declaracion fixture once through capture_filed_data and once through the discovery-driven grid, asserting both persisted observations carry ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE and are otherwise field-equal apart from capture timestamps, verified by the test going red if either path is made to stamp a different kind

## Scope

- `src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`

## Description

- Add the provenance parity test comparing the single-pair and bulk finalizer policies over one declaración.
- Add the no-signal-token-in-provenance test.
- Add the official-source-kind membership test proving no sixth kind was introduced.

## Outcome

The claim this Step settles is that a discovery-driven historical capture needs
no new observation source kind, because an imported filing IS an AEAT-sourced
filed declaración. That is only safe if the discovery signal cannot reach the
stamp, so the same declaración is pushed through the single-pair policy and
through the bulk policy a discovery sweep uses, into two real encrypted
repositories with a real key provider, and the two persisted rows are compared
WHOLE after each provenance field is asserted individually.

Nothing is excluded from the comparison. The captured-at instant derives from the
filing's own presented-at, so it is genuinely equal on both paths and is asserted
equal rather than waved through as a permitted difference.

Built on Modelo 130 rather than 303, and that is a correctness choice rather than
a convenience. The provenance stamp is modelo-agnostic, while a 303 observation
additionally drives the IVA compensation wallet on the way to persistence -- a
side effect with nothing to do with provenance, and one whose failure would be
indistinguishable here from a real provenance divergence.

The second test closes the side a two-run comparison cannot: both runs could be
wrong in the same way, so it also asserts no discovery signal token reaches the
persisted metadata. The third gates membership of the official set rather than a
total enum count, so an unrelated non-official kind does not force an edit while
a discovery-specific official kind fails.

## Verification

    uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py -q -n 0 -k "discovery or official_source_kind_set"
    3 passed, 34 deselected in 41.62s

The plan row requires the test to go red if either path stamps a different kind.
Proved with a mutation harness loaded from OUTSIDE the repo, patching the single
stamping site so the bulk arm stamps the live-capture kind instead:

    MUTATION INSTALLED: BEST_EFFORT arm will stamp AEAT_SEDE_LIVE_CAPTURE
    MUTATION FIRED for modelo 130: stamping aeat_sede_live_capture
    E   AssertionError: assert <ObservationSourceKind.AEAT_SEDE_LIVE_CAPTURE: 'aeat_sede_live_capture'> is <ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE: 'aeat_sede_justificante'>
    1 failed, 36 deselected in 37.29s
    MUTATION FIRE COUNT: 1 ['130']

The first mutation harness reported itself INSTALLED and the test still passed,
which read as an insensitive test. It was the instrument: the policy check
compared a string enum against an uppercase member name, so it never fired. The
harness now reports its own fire count, because a mutation that never fired
proves nothing and looks identical to a mutation that fired harmlessly.

## Notes

A peer sweep landed an in-progress 303-based draft of these tests into HEAD
before they were corrected, and that draft is RED at HEAD: every Modelo 303
filed-observation persist raises there, because the IVA compensation history
consumer reads a `generated` attribute while the available-compensation
derivation dataclass declares `available`, `basis`, `operand_refs` and
`operand_values` and no `generated`. That mismatch is present in HEAD in both
files, neither of which this Step touched, and it fails 21 tests across the sede
and live suites independently of this work. It is reported to the team rather
than patched here: guessing the intended semantics of the renamed field would
risk the IVA compensation carry, which is money.

The correction to Modelo 130 was landed own-only against HEAD in commit
`48b511acfd`, so a peer's concurrent refactor of an unrelated test in the same
file was neither taken nor disturbed.
