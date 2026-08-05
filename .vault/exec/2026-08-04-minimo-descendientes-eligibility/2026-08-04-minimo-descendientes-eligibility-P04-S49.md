---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:b7edb8287b8f7a8868583f914957d3eb021c4c6bd3d0759763e803533c1ee8b7'
step_id: 'S49'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

## Outcome

Remedy detail moved off the diagnostic message onto a structured carrier, the ten
advisories rewritten to state the problem only, and a headroom gate added that proves
they clear the cap. Verified green after a session crash: 40 gate tests, 658 passing
across the gate plus the aggregation suite.

The measured claim now holds. Before the rewrite, eight of ten advisories lacked the
required headroom and **two were truncating in production** -- `dependencia_suppressed`
at 521 and `prorrata_inferred` at 516 against a 512 cap, reachable at **four children**
rather than any implausible household. After it, all ten clear at the late-qualifying
worst case.

## The measurement inverted the plan's own ranking

The Step was scoped from a static-floor table that ranked `count_desync` (floor 406)
as the top risk and `dependencia_suppressed` (floor 333) as the safest. Measured
against the real factories, that was exactly backwards: `count_desync` does not use the
fact-path renderer at all and is the safest growable advisory in the module, while
`dependencia_suppressed` was already over the cap.

A static floor is a lower bound on a message, not a ranking of risk. Sorting by it
substitutes the part that cannot grow for the part that can. The corrected table is in
the headroom census research document.

## Two rejected alternatives, both on measurement

**Raising the 512 cap** was reached and rejected: any cap can be crossed by data-scaled
content, so it moves the threshold and buys one clause. The instinct that something was
wrong with the copy was right, and it pointed at remedy detail belonging on the carrier
rather than in prose -- which is this Step.

**Factoring the repeated `renta_family.descendiente.` prefix** in the fact-path renderer
would have recovered a flat 50 characters -- more than the remedy move -- because 78 of
its 96 rendered characters are that one constant repeated three times. It was rejected
after measurement: six tests assert the verbatim path *deliberately*, because an
operator lifting a fact path out of an advisory and using it is the feature. Losing that
distinction to make room is worse than a thin message. The 78-character figure is
recorded so a future campaign can spend that budget as a deliberate format decision with
the tests updated, rather than as a side effect.

## The gate

`test_minimo_descendientes_advisory_headroom.py` uses the **late-qualifying** worst case
(`_WORST_FIRST_INDEX = 100_000` over a 900,000 qualifying run), not the all-qualifying
million the sibling suite had used. The renderer emits enumerate positions, so length
grows with index digits as well as remainder; all-qualifying yields 101 characters where
late-qualifying yields 116. The weaker convention understated headroom by ~15-22
characters -- a gate erring in the safe-looking direction, inside the instrument built
to measure headroom. The reason is written into the test prose so the convention is not
simplified back.

`_WORST_COUNT` stays at a flat million for `count_desync` alone, because that advisory
interpolates two integers rather than descendant paths and household size is not its
axis.

The gate reads the elision marker off the **live type** -- feeding one unbroken word and
stripping the filler -- rather than importing a constant. That survives the concurrent
refactor which retired `DIAGNOSTIC_MESSAGE_ELISION` in favour of
`core.prose_elision.PROSE_ELISION_MARKER`.

## Provenance and process notes

The implementation landed inside a broad `Git WIP snapshot` checkpoint commit rather
than a commit of its own, so it carries no descriptive message or attribution in
history. That checkpoint pattern is the same one that swept an unmeasured experiment
into an unrelated guardería commit earlier in this campaign.

The division of labour intended for this Step did not hold: the gate was written by the
same agent that wrote the copy it checks, which is the arrangement the campaign had
explicitly argued against -- an instrument should not measure its author's own homework.
The gate passes on inspection and on execution, so it was kept rather than rewritten for
provenance alone, but the principle stands unmet here.

The measurements this Step rests on -- the ten-advisory table, the two production
truncations, the four-children trigger, the 78-character prefix finding, and the
late-qualifying convention -- were produced by a reviewing agent that twice refused a
coordinator instruction on evidence and was right both times.
