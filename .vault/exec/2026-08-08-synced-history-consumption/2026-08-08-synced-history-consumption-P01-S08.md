---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:944e6c160f9bdcca69ca1e9e9146921489bf0adc3ade16c8fb57f7075c1d8116'
step_id: 'S08'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference]]"
---
# Establish what a Sociedades filer's unpullable carries do on the consumption side

## Scope

- `src/cadrumo/application/calculations`
- `src/cadrumo/application/modelo`

## Description

- Check whether the behaviour is already characterised before writing anything,
  since an unchecked row is not evidence the work is undone.
- Run the existing Modelo 200 live-path tests to confirm the current behaviour by
  execution rather than by reading the resolver.
- Determine what distinguishes the slots that go silent from the slots that
  advise.
- Establish whether any operator-facing surface separates a filer with no prior
  filings from one whose prior filings exist at AEAT and cannot be fetched.

## Outcome

BOTH, and the nine slots split — which is a finer answer than the row's
either-or framing anticipated, and the dividing line is not the one the earlier
rows suggested.

THREE SLOTS PRODUCE A PLAUSIBLE FIGURE, SILENTLY. The Modelo 200 self-carries —
bases imponibles negativas pendientes at opening, and both dotaciones-por-
deterioro opening stocks — resolve to ZERO with no prior filing in the store, and
the live calculate emits NO diagnostic whatsoever. The existing test asserts
`result.source_diagnostics == ()` on that path, and it passes. A zero opening BIN
stock means no loss carryforward is applied, which raises the base imponible. So
this is the over-payment direction, arriving as a clean number with an empty
diagnostics channel.

TWO SLOTS ADVISE. The Modelo 200 carries fed by Modelo 202 pagos fraccionados
leave the dependent cuota-diferencial formula UNRESOLVED and emit one
`source_issue` relation-prefill diagnostic naming modelo 202, the filing year and
each missing period. Nothing is silently zeroed there.

THE DIVIDING LINE IS FORMULA OPERAND VERSUS BOUND CASILLA, not source kind. All
five Modelo 200 slots declare `source = "relation_prefill"`. The two that advise
are formula operands; the three that go silent bind a casilla directly and take
the present-or-zero semantics. This refines the split recorded in the
over-payment row: the silence is not only a previous-filing-versus-relation-prefill
divide. Within one source kind, a directly-bound carry is silent because it
resolves to a zero, and a formula-operand carry is loud because it resolves to
nothing. Any fix that keys on the source kind alone would leave these three
untouched.

NO SURFACE DISTINGUISHES THE TWO POPULATIONS. The zero is byte-identical whether
the taxpayer is a genuine first-ejercicio company with no prior stock or a company
whose prior Modelo 200 exists at AEAT and cannot be fetched, and no diagnostic
accompanies either. Nothing on the resolution path consults pull-reachability, so
there is no fact available to distinguish them with.

The one surface that speaks to the absence of AEAT history makes it worse for this
population specifically. The no-AEAT-history notice fires when not one persisted
observation carries an official AEAT source kind, and its suggestion is
`aeat app live filed pull-all`. For a Sociedades-only filer that remedy cannot
ever succeed: the capture planner diverts modelo 200 and modelo 202 into typed
unsupported failure rows because neither declares the filed-declarations read
surface. So the notice points at a verb that structurally cannot fetch what it is
telling the operator to fetch. And for a mixed filer, one successfully pulled
Modelo 303 row satisfies the notice's predicate and silences it, while the
Sociedades history has still never arrived.

## Verification

    uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_modelo_200_fold_in_live.py -n0 -q
    3 passed in 17.29s

That run is the real-run evidence the gate asks for. The three tests are the
prior-filing carry, the no-prior-filing carry, and the missing-M202 relation, so
one invocation exercises both poles of the split plus the populated control.

The behaviour was NOT re-derived by reading resolvers: the zero and the empty
diagnostics tuple are the existing test's own assertions, and they pass against
HEAD today.

    uv run --no-sync python -c "<probe over the loaded authority>"
    M200 bindings by source: {'relation_prefill': 5, 'profile': 6}

That is what establishes the dividing line is not source kind: all five carry
slots share one `source`, and they behave two different ways.

No production file was changed and no new test was written. The row is an
investigation, and the fix it argues for belongs to the row that owns the
diagnostic gap.

## Notes

A TEST BLESSES THE SILENT ZERO, and a fix has to dispose of that rather than trip
over it. `test_m200_self_carries_resolve_zero_with_no_prior_filing_on_live_calculate`
states in its own docstring that it "documents the status quo and fails loudly if
it drifts", and its rationale is that a first-ejercicio filer has no prior stock,
so the zero is "a correct zero, not a silent under-declaration of a declared
prior".

That reasoning is correct for the population it names and silent about the other
one. The test is not wrong and should not be called a defect: it is scoped to a
first-ejercicio filer and never claims to cover an unreachable prior. But it WILL
fail the moment anyone turns that zero into an advisory or a refusal, so whoever
implements the diagnostic must amend this test in the same change rather than
discover it as a surprise red.

CORRECTION TO MY OWN EARLIER RECORD. The over-payment row framed the silent
channel as the previous-filing channel, on the ground that its resolver emits no
diagnostics. That remains true and is unchanged. What that framing missed is these
three `relation_prefill` slots, which are silent for a DIFFERENT reason —
present-or-zero binding semantics rather than an absent diagnostics channel. The
silent set is therefore larger than that row implied, and the diagnostic row's gate
should be read as covering both mechanisms.

WHAT I COULD NOT MEASURE. Whether the no-AEAT-history notice is in fact rendered
to a Sociedades-only filer on any live operator surface. I read its predicate and
its suggestion string and reasoned about the population; I did not run a projection
to observe it. A data-driven surface is invisible to reading, so that reasoning is
weaker than the M200 run above and is marked as such rather than presented
alongside it.

## Second run: the Modelo 202 half, and an independent confirmation of the Modelo 200 half

Added by a second executor working the same Step after the first went offline.
The first run's findings are confirmed, not restated, because the method differs:
that run exercised the existing Modelo 200 live-path tests, this one built a
fresh live operator calculate over a real isolated encrypted profile seeded as a
Sociedades legal entity with an EMPTY observation store, supplying a zero for
every binding on the revision EXCEPT the carry slots under test. Independence of
agent is not independence of method, so a second run reading the same tests would
have added nothing.

MODELO 202 REFUSES, and it is the half the first run did not cover. Four of the
seven unreachable factual-evidence slots sit on modelo 202, and the live calculate
for 2025 period 1P raises `ModeloRequiredBindingsMissingError` naming
`modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior`, with an instructive
remedy pointing at the bindings-list verb. So the answer to the row splits by
modelo as well as by mechanism: modelo 200 goes silent, modelo 202 refuses loudly.

The refusal is caused by exactly that carry and nothing else. Supplying the carry
bindings a value turns the same run into a returned result, which is the control
that rules out an unrelated missing input as the cause.

MODELO 200 CONFIRMED, with a discriminating control the first run did not need but
which rules out a fixed constant. With the three carries absent the calculate
returns a complete result of 3250 casilla values and NO diagnostics, and casillas
00670, 01494 and 01495 each read `Decimal('0')`. Supplying those same three
bindings a value of 12345 returns 12345 in all three casillas. The zero therefore
tracks the absent carry rather than being a constant the formula would emit
regardless, which is what makes "silent zero" a measurement instead of an
inference.

THE DIRECTION, from the casilla's own official label rather than from its id.
Casilla 00670 is "Detalle compensacion bases imponibles negativas - TOTAL -
Pendiente aplicacion a principio del periodo", grounded in `ley-27-2014:art-41`,
`art-29`, `art-30` and `art-39`. A zero opening stock discards the loss
carryforward, which raises the base imponible and the tax. This is the
OVER-declaration direction, and it arrives as a clean number with an empty
diagnostics channel. All three silent casillas are declared `required = false`
with `input_kind = bound`, which is the present-or-zero semantics the first run
identified, confirmed here from the compiled schema.

THE NOTICE PREDICATE IS CONFIRMED against the code, closing half of what the first
run marked as unmeasured. `no_aeat_history_notice` returns `None` on the FIRST
observation whose source kind satisfies the official-AEAT predicate, so a single
pulled row silences it. The other half stays open and is still not measured: nobody
has run a projection to observe whether the notice is rendered to a Sociedades-only
filer on a live operator surface, and reading a predicate is not running the
surface.

The row's own gate required that a missing distinguishing surface open its own row
rather than remain a note. It is `P01.S14`. It is deliberately not folded into
`P01.S10`, which owns giving the previous-filing RESOLVER a diagnostic channel: the
three silent modelo 200 casillas are `relation_prefill` bound casillas, a different
mechanism on different files, and the first run's suggestion that the diagnostic
row's gate simply "be read as" covering both mechanisms is the shape where a
ruling recorded in prose acquires no owner.
