---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:d31fd428ea4366f0e786d9442e40e4d35627e8898b9274a7d918e08ba22e1349'
step_id: 'S20'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# add classify_register_scoping_signal comparing the AEAT_REGISTER_OPTIONS modelo set against the profile's confidently_excluded set from build_obligation_coverage, returning LIKELY_UNIVERSAL, LIKELY_NIF_SCOPED or INCONCLUSIVE, verified by three synthetic-fixture tests, one per classification, none asserting a resolved boolean

## Scope

- `src/cadrumo/application/live/_filed_data_capture.py`

## Description

- Add the closed `RegisterScopingSignal` StrEnum to `src/cadrumo/core/_register_scoping_signal.py` and promote it on the core facade.
- Add `classify_register_scoping_signal` comparing the offered modelo set against the profile's confidently-excluded set.
- Promote it on the `application.live` facade.
- Add one test per classification plus a representability test and an advisory-only test.
- Regenerate the API stub for the new core module.

## Outcome

The scoping question cannot be settled without an authorised live probe, and
the design never depended on it resolving. What it did have was a free, offline,
taxpayer-specific discriminator nobody was reading: if the register offers a
modelo the taxpayer's own declared facts positively EXCLUDE, it is offering
something this filer cannot have filed, which is what a catalogue rendered
regardless of taxpayer looks like.

The enum has NO `UNIVERSAL` and NO `NIF_SCOPED` member, and the absent pair is
the design. A resolved member could be stored, exported and later cited as though
a probe had confirmed it, so a resolved value is not representable at all rather
than merely discouraged. Every member is a hedge.

The evidence is asymmetric and the confidence follows it. `LIKELY_UNIVERSAL`
rests on a POSITIVE observation -- an excluded modelo was offered. Its
counterpart is only ever the ABSENCE of that observation, which a universal
catalogue also produces for a taxpayer whose profile excludes nothing the
register happens to list, so it stays `LIKELY_NIF_SCOPED` and never becomes
confirmation.

`INCONCLUSIVE` is returned when either side of the comparison is empty, and it is
not a weak version of either reading: the available evidence says nothing either
way, and collapsing that into "probably scoped" would manufacture confidence out
of an absent measurement.

The reading is advisory and gates nothing. The offered set is unioned into the
walk grid additively regardless, so a classification can neither widen nor narrow
what is queried -- an advisory that quietly gated coverage would be the worst of
both, an unconfirmed signal deciding what gets walked.

## Verification

    uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_history_discovery.py -q -n 0
    31 passed in 27.93s

Six tests, not three. The plan row asks for one per classification and that none
assert a resolved boolean; two further tests make that structural rather than a
convention. One pins that the enum cannot express a resolved value at all, so a
future consumer cannot store a heuristic and later render it as confirmed. One
pins that both readings produce an identical walk grid, so the advisory cannot
start gating coverage.

Each classification test carries an anchor assertion on its own fixture -- that
the profile excludes something, or that the offered modelo is not excluded --
because either arm would otherwise pass for the wrong reason if the underlying
applicability partition changed shape.

## Notes

The classification is deliberately NOT persisted and NOT surfaced on the
discover verb's payload in this Step: the row scopes the classifier, and adding
an operator-facing field would need its own locale keys against catalogues that
are under heavy concurrent write.

No live AEAT access, no probe, and no authorisation required or sought.
