---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:c9710da17249b668885e5a3549d2a14927f70f1564968618b7f47a5b47826052'
step_id: 'S24'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference]]"
---

# Measure the carry-advisory volume rather than arguing it

## Scope

- `src/cadrumo/application/calculations`

## Description

- Run both carry resolvers over a real encrypted bucket for every revision that
  declares a carry, as a long-running filer with an empty store, which is the
  upper bound any bucket can produce for that revision.
- Read how the diagnostics reach the operator rather than assuming a cap.
- Test distinguishability on the fields an operator actually receives.
- Report what the measurement contradicts, including in my own earlier records.

## Outcome

The volume is acceptable on eleven of thirteen revisions and unacceptable on one,
and the measurement contradicted two things I had previously asserted.

UPPER-BOUND VOLUME, per single calculate, long-running filer, empty store:

| revision | advisories |
| --- | --- |
| 190/2024-y-siguientes @0A | 10 |
| 200/2024-y-siguientes @0A | 5 |
| 390/2010-y-siguientes @0A | 4 |
| 714/2021-y-siguientes @0A | 4 |
| 100/2025 @0A | 2 |
| 180/2023-y-siguientes @0A | 2 |
| 193/2024-y-siguientes @0A | 2 |
| 131/2025 @1T, 202/2025 @2P, 303/2023 @1T | 1 each |
| 130/2019 @1T, 353/2008 @12, 720/2013 @0A | resolver REFUSED, see below |

Median 2, maximum 10. For eleven of the thirteen the answer to the alert-fatigue
question is that the volume is small, and that closes the question raised on the
reconcile recommendation for this channel.

THE NARROWINGS ARE VISIBLE IN THE NUMBERS. Modelo 100 declares nine
`relation_prefill` carry slots and produces TWO advisories, because the
`taxpayer_files_source` axis excludes the Modelo 111, 123, 190 and 193 retención
carries the payer files. The modelo with the most carries produces nearly the
fewest advisories, which is the narrowing working rather than being argued.

MODELO 190 IS A REAL NOISE CASE, and its shape is redundancy rather than volume.
All ten advisories name the same absent Modelo 111 source. Ten distinct facts are
genuinely missing — trabajo dinerario and especie, actividades, premios,
ganancias, derechos de imagen, retenciones — so nothing is duplicated at the fact
level, but there is ONE root cause and ONE remedy. Per the standing direction the
answer is scoping the presentation, never removing the signal, so this is opened
as `P01.S25` to group by source requirement while keeping the affected ids
machine-readable.

THE ADVISORIES ARE STRUCTURALLY INDISTINGUISHABLE AT THE OPERATOR SURFACE, which
is the finding I did not expect. The calculate CLI projects every source
diagnostic one-to-one onto a notice whose `context` carries only `reason`,
`source_kind` and `resolver_id`. Those three are identical across every carry
advisory. The only distinguishing information is the free-text `message`. An
automated operator is directed to route on the field rather than parse prose, and
on this channel there is no field to route on. There is also no cap and no
de-duplication: N diagnostics become N notices and N terminal lines. Opened as
`P01.S26`.

## Verification

    uv run --no-sync python <scratch>/volume_probe.py <tmp>
    revisions measured with >=1 advisory: 13
    max advisories on one calculate: 10  (at 190/2024-y-siguientes@0A)
    median: 2

Every count comes from constructing the production `PreviousFilingSourceResolver`
and `RelationPrefillSourceResolver` against a real snapshot and a real
encrypted-SQLite bucket through `isolated_runtime_profile`, with a real profile
record declaring `censo.activity_start_date`. No emission site was read and
counted; the resolvers were run.

The per-revision detail enumerates each advisory's subject, so the distinct-subject
count is checked against the raw count rather than assumed equal — they agree
everywhere except where a resolver raised.

The refuse-versus-advise asymmetry was isolated with a second probe over two
buckets identical but for one profile fact:

    uv run --no-sync python <scratch>/raise_probe.py <tmp>
    NO activity start declared:  ADVISED 3 diagnostic(s), unresolved=3
    activity start 2015-01-01:   REFUSED with RegistryValidationError:
        binding 'irpf.previous_year_economic_activity_net_income'
        expected one observed filing '100'/2024/'0A', found 0

Two buckets, one differing fact, opposite behaviours. That is what makes the
asymmetry a property of the code rather than of either bucket.

The operator-surface claims were read from the projection in
`src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py`: one notice per
diagnostic, `context` built from exactly three keys, and text lines rebuilt from
the notices. No production code was changed by this row.

## Notes

THIS MEASUREMENT CORRECTED TWO OF MY OWN ASSERTIONS, and both corrections are
recorded where the original claim lives rather than only here.

The unsatisfied-carry row states that the previous-filing channel now reports. It
reports on the no-declared-activity-start branch only; with a declared start the
pre-existing behaviour is a hard `RegistryValidationError` that propagates, because
the resolver catches only storage-degradation errors. The silence that row closed
was therefore narrower than its Outcome implied. That row now carries the
correction and cites `P01.S27`, which is where the refuse-versus-advise choice
belongs.

And the present-or-zero row answered the alert-fatigue question "by construction".
That was the right thing to flag as weaker evidence and the wrong thing to leave
standing: construction was correct for eleven revisions and wrong for Modelo 190,
where ten lines land for one missing filing. Argument strength was not volume, and
the volume had to be run.

WHAT THIS DOES NOT ESTABLISH. The upper bound is not the realistic case. A filer
who has captured most of their history sees fewer advisories than these numbers,
and I did not build a partially-populated persona per revision to measure the
distribution between zero and the bound. The bound is the decision-relevant figure
for alert fatigue, so it was measured first; the distribution is not measured and
is not claimed.

It also does not measure what an operator sees for a MULTI-modelo session. Each
figure is one calculate of one modelo. A filer working several modelos in sequence
accumulates advisories across calls, and whether any surface aggregates them
across a session was not examined.
