---
tags:
  - '#exec'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:a391974ec7e7f7b9a711dec799b518d5549588c9aa542aa9c702080715d1addf'
step_id: 'S10'
related:
  - "[[2026-08-04-profile-derived-selectors-plan]]"
---

# Make the remaining injectors compute-always so a stray stored fact cannot win, and invert rather than delete the three tests that bless the defer-to-explicit-fact behaviour being removed, namely the two idempotency tests whose seeded sentinels stay valid as anti-tautology proof in the inverted direction, and the suppression half of the override proof from P01.S01

## Scope

- `src/cadrumo/application/modelo/_profile_binding.py`
- `src/cadrumo/application/modelo/tests/test_minimo_descendientes_engine.py`
- `src/cadrumo/application/modelo/tests/test_anualidades_eligibility_derivation.py`
- `src/cadrumo/application/modelo/tests/test_derived_aggregate_override_real_path.py`

## Description

## Outcome

The injectors compute always. A stored fact at a derived path can no longer displace the law,
and the override channel this campaign was built to close is closed at both ends: refused at
the write door, and inert at the calculation if one survives from before the refusal existed.

The scoping deserves recording because the brief was imprecise and the executor did better
than it. The brief said four guards. Rather than count them, the executor asked the declared
namespace which paths are derived and got exactly four injectors back. That also answered the
question the brief did not pose: what to LEAVE. The marriage facts and the state-attribution
ratio use an identical skip-if-present shape and are NOT declared derived, so they keep it.
Counting to four could have taken one of those and quietly changed a behaviour nobody had
decided to change.

The override is calculation-scoped, not destructive. The injectors mutate an ephemeral
per-calculation index and never persist, so a stale stored fact becomes ignored rather than
overwritten on disk.

Both idempotency tests inverted rather than being adjusted, and the executor flagged an
asymmetry against its own work rather than letting a seed look stronger than it is. One
sentinel is genuinely unreachable by Art. 58 arithmetic. The other is reachable in general --
a shared-custody descendant yields it -- and is unreachable only for that test's profile,
which declares no descendants. That reasoning is now in the docstring, where the next reader
will need it.

## Notes
