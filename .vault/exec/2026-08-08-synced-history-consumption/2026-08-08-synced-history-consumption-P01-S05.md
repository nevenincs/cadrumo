---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:153dd4937859b19f011fb47aa017c662629877e136dea282eedf8fb5c2d92467'
step_id: 'S05'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference]]"
---

# Investigate whether a ledger-derived casilla on a pulled work unit should be back-derived, left empty with an advisory, or refused

## Scope

- investigation only, no production files

## Description

- Search by meaning for an existing home for the comparison before proposing one,
  rather than treating a third option as something to build.
- Read what the reconciliation surface actually accepts as input, and which
  modelos it is enrolled for.
- Establish which of the three options the tree takes today.
- Recommend, preserving the rejected alternatives with their failure modes and the
  paragraph that undercuts the recommendation.

## Outcome

RECOMMENDATION: reconcile. Neither back-derive nor refuse. And the comparison is
not a new thing to build — the primitive, its registry-declared scope and its
typed divergence taxonomy already ship; the pulled observation is the input they
are not wired to.

`detect_casilla_divergences` in
`src/cadrumo/application/modelo/_reconcile_casilla.py` is a pure comparison over
two casilla-value mappings, classifying every disagreement into three closed
kinds: `value_mismatch`, `missing_in_filed`, `extra_in_filed`. Its compared set is
scoped by the registry's own `verification_policy`, so it is declared registry data
rather than an ad hoc casilla list. That is exactly the shape a pulled-versus-ledger
comparison needs, and it exists.

WHAT THE TREE DOES TODAY, measured rather than assumed. Casilla-level
filed-declaration reconciliation is reachable only through
`reconcile file --file <declaración PDF>`, and only for the six modelos enrolled
in `_DECLARATION_CASILLA_RECONCILE_MODELOS`: 100, 111, 130, 190, 303, 390. A
modelo outside that set is refused rather than degraded to header-only
comparison, which is the right refusal.

`reconcile pull` does NOT reach it. It captures a justificante snapshot and
reconciles against the receipt — header fields plus the printed total where the
revision declares `reconciliation_total_casilla_ids`. A receipt is not a
casilla-level document.

So the pulled filed observation, which already carries per-casilla values off the
register for every pullable modelo, is never fed to the comparison primitive. The
values needed on both sides of the divergence check are both persisted, in the
same bucket, and nothing joins them. The recommendation is therefore a wiring
change against an existing authority, not a new mechanism, and it needs no new
taxonomy row because reconciliation is not an aggregation channel: it produces a
diagnostic, never a casilla value.

REJECTED: BACK-DERIVE the ledger-derived casilla from the pulled declared value.
Its failure mode is that it invents transactions that never existed. A ledger
binding's value is an aggregation over rows, and the evidence bundle a revision
must carry is the contributing-transaction projection; synthesising a row set that
sums to a declared total fabricates the very evidence the bundle exists to
preserve, and the fabrication is indistinguishable from real rows at every
downstream surface. This option is additionally closed by the decision record's
own constraint, which forbids it outright, so it is not open for the ruling to
reconsider.

REJECTED: REFUSE the calculation when a ledger-derived casilla is empty on a
pulled work unit. Its failure mode is that it blocks an onboarding flow the
taxpayer needs. A genuinely inactive filer is obliged to present a declaration
with no activity, and an empty ledger is the correct state for them; refusing
would make the legal filing impossible through the application. It also fails
closed against the wrong population, because the taxpayer least able to diagnose
the refusal is the one who just onboarded.

REJECTED AS SUFFICIENT: LEAVE EMPTY WITH AN ADVISORY. Not wrong, and it is
roughly what happens today, but it is not enough on its own. Its failure mode is
that the legally valid zero reads as settled. The advisory says a value is absent;
it does not say that AEAT holds a figure for that same casilla which disagrees.
Those are different claims, and only the second is actionable. Keeping the
advisory is right; treating it as the answer is what leaves the taxpayer where the
campaign found them.

## THE PARAGRAPH THAT UNDERCUTS THE RECOMMENDATION

Reconciliation only helps a taxpayer who has something worth comparing. A
freshly-onboarded profile has an empty ledger, so its computed values are zero
across the board, and comparing zero against every pulled declared figure yields a
`value_mismatch` on essentially every reconciled casilla. That is not a signal, it
is a wall of divergences — precisely the alert-fatigue failure the
unconsumed-IVA advisory rule was written against, where a channel that fires on
the whole population trains the operator to dismiss it, and then it is worthless
on the day one divergence matters.

The recommendation therefore depends on a scoping condition that does not exist
today: some declared notion of when the ledger is populated enough for a
divergence against a pulled figure to mean "these disagree" rather than "the
ledger is empty". Without it, wiring the primitive to the pulled observation makes
the newly-onboarded taxpayer's experience worse, not better. I do not know what
that condition should be, and I am not confident it can be derived from any signal
currently persisted. If the ruling adopts this recommendation it inherits that
problem, and the problem is load-bearing rather than incidental.

## Verification

Discovery was semantic-first, as mandated:

    uv run --no-sync vaultspec-rag search "reconcile a filed AEAT declared casilla value against the value the engine computed and report the divergence" --type code --port 8766 --timeout 120
    1. src/cadrumo/application/modelo/_reconcile_casilla.py:1
    2. src/cadrumo/application/modelo/_reconcile.py:1

The RAG hit was then confirmed by targeted reads: the enrolment set
`_DECLARATION_CASILLA_RECONCILE_MODELOS` at
`src/cadrumo/application/modelo/_reconcile.py:92`, and the `reconcile pull` verb
body in `src/cadrumo/entrypoints/cli/_modelo_reconcile_cli.py:202`, which resolves
`capture_justificante_snapshot` and `reconcile_capture` and never touches the
declaration path.

No pytest lane was run and no production file was changed: this row is an
investigation and its scope says so.

## Notes

STALE DISCLOSURE, opened as a finding rather than fixed here. The docstring of
`modelo_reconcile_bytes` states that declaración reconciliation is not offered on
the bytes path because "the only authenticated live-capture flow today captures
justificante snapshots, never a filed declaración". The filed-history pull
falsifies that premise: it captures filed declaración observations with per-casilla
values AND stores their artefact bytes. The disclosure was true when written and
became false when the filed pull shipped, which is the harder class to notice
because every fact in the sentence still parses. It is not fixed here because this
row changes no production file, and because the right fix depends on the ruling —
if the pulled observation becomes a reconciliation input, that docstring's whole
rationale is replaced rather than corrected.

WHAT THIS DOES NOT ESTABLISH. It does not measure how many casillas a real pulled
observation and a real populated ledger would actually disagree on, because that
needs captured artefacts a live read would be required to obtain, and no live read
was performed. The undercutting paragraph above is therefore a reasoned
expectation about divergence volume on an empty ledger, not a measurement. It
would be cheap to measure once any real captured filing exists in a bucket with a
populated ledger, and it should be measured before the recommendation is
implemented rather than after.
