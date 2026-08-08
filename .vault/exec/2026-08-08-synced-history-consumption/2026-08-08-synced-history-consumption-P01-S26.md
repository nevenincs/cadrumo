---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:9f40aa53ab8f32d19adc711cd2f50f2ce017187f3d2a03e9ab3f7f8ddd0d9e00'
step_id: 'S26'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference]]"
---

# Carry the diagnostic subject onto the operator notice context

## Scope

- `src/cadrumo/entrypoints/cli`
- `src/cadrumo/application/calculations`

## Description

- Search by meaning for the canonical projection point rather than editing the
  call site that surfaced the problem.
- Find that the projection is DUPLICATED and divergent, and close that rather
  than fixing one copy.
- Carry every structured subject the diagnostic already holds onto the notice
  context, omitting absent keys rather than writing them blank.
- Keep the aggregation-import lazy so the state-free CLI surface is unaffected.
- Gate on distinguishability by context alone, with a mutation restoring the
  prior flat context.

## Outcome

Carry advisories are now routable, and the fix closed a duplication rather than
patching a symptom.

THE PROJECTION WAS DUPLICATED AND DIVERGENT, which the volume row had not seen.
Two call sites built the notice context independently: the calculate command with
`reason`, `source_kind` and a conditional `resolver_id`, and the wizard command
with `reason` and `source_kind` only. The wizard ALSO dropped `suggestion`
entirely, so the remedy never reached an operator on that path — including the
remedy added to the carry advisory earlier today, which would have been silently
lost there.

Both now route through one `source_diagnostic_notice` in the module that already
declares itself the single advisory projection point. That removes the divergence
by construction rather than by keeping two copies in step.

THE CONTEXT NOW NAMES THE SUBJECT. `binding_id`, `relation_id`, `casilla_id`,
`source_ref` and the typed `binding_source` join the three existing keys, each
omitted when the diagnostic does not carry it so absence means "no such subject"
rather than "the subject is blank". Every field an operator would otherwise have
had to recover by parsing prose is now a key.

A THIRD NARROWING ON THE CARRY ADVISORY, forced by a real failure this row
uncovered. Two CLI tests failed because the bound-carry advisory was firing on the
Modelo 303 compensación slot — a value the IVA wallet decision owns under the
one-mechanism-per-calculation-type taxonomy. This resolver advising on it is a
second mechanism speaking about a value it does not own. The registry already
models the coordinate set, so the exclusion uses its own
`is_iva_wallet_owned_relation_target` predicate rather than a binding-id
comparison invented here.

That failure was MY earlier row's fallout, not this row's: the sweep after the
bound-carry emission covered `application/modelo/tests` and did not cover
`entrypoints/cli/tests`, so two real regressions sat unnoticed until this row ran
the CLI suite. The sweep was scoped by directory rather than by what the change
could break.

## Verification

    uv run --no-sync pytest <notice context gate> -n0 -q
    4 passed in 14.59s

    uv run --no-sync pytest <notice context gate> test_json_schema_conformance.py test_lazy_command_tree.py -n0 -q -m ""
    347 passed in 172.21s

    uv run --no-sync pytest test_modelo_source_mesh_calculate.py -n0 -q -m integration
    9 passed in 107.78s

    uv run --no-sync pytest <M200 live> <relation prefill mesh> <notice context gate> -n0 -q -m ""
    20 passed in 83.26s

The distinguishability gate discards the message and compares only the context
mappings, because the message is precisely the channel an automated operator is
told not to parse. It chains BOTH production functions — the resolver's own
diagnostic builder and the shipped projection — so no context dict is
reconstructed in the test; a copied dict would assert the author's idea of the
projection rather than the projection.

MUTATION, restoring the pre-fix flat context. It keeps the message, suggestion and
code intact and strips only the routable subject:

    PYTHONPATH=<scratch> ... -p mutate_flatten_notice_context -s
    MUTATION APPLIED: holder confirmed, original=<function source_diagnostic_notice ...>
    E   AssertionError: two carry advisories share an identical notice context ...
    E   assert 1 == 3

That `1 == 3` is the defect made visible: three advisories about three different
casillas collapsing to ONE distinct context. The plugin resolves the holder before
rebinding and re-checks identity after, so a no-op rebinding cannot print APPLIED
and pass.

`test_lazy_command_tree` was run explicitly because the shared helper needed a
`CalculationSourceDiagnostic` annotation, and the calculate module defers that
import for exactly this gate. It is deferred here too, under `TYPE_CHECKING`.

    ruff format --check <five files>  ->  5 files already formatted
    ruff check <five files>           ->  All checks passed!
    dev.quality.types                ->  zero occurrences of any of the five files

## Notes

THE MEDIAN OF 2 MUST NOT BE QUOTED OUT OF SCOPE. The volume row measured 13
revisions at median 2 and a maximum of 10, and every one of those figures is ONE
calculate of ONE modelo. It is not a median per session. A filer working several
modelos in sequence accumulates advisories across calls, and whether any surface
aggregates or de-duplicates them across a session was not examined. Anyone citing
the median as an operator-experience figure is citing it for a scope it was not
measured over.

WHAT THIS DOES NOT ESTABLISH. The gate asserts the projection, not a full Typer
round trip. The one unexercised link is the envelope emission itself, which
`test_json_schema_conformance` covers for notice shape across 333 cases but not
for these specific context keys. A CLI-level two-advisory persona would close that
and would need an M200 bucket built at the CLI fixture layer, which is a larger
lift than this row carried.

The remedy text itself is not asserted for correctness anywhere, only that it
reaches `suggestion`. Whether the binding-override instruction is actually
followable for each affected casilla is untested.

TWO OF MY OWN DIAGNOSES OF PEER STATE NEEDED CORRECTING, and both are the same
hazard: the cause you name is the one that gets quoted afterwards.

The held `index.lock` was reported with its mtime frozen across three checks over
roughly two minutes, and the rule's reading of frozen is that the holder may have
died. It later ADVANCED — 12:12:21, then 12:14:56, then 12:23:26 — so the holder
was alive throughout and this was contention, not death. The observation was
correct and the inference it invited was wrong. A frozen mtime over two minutes is
not enough to conclude a holder died in a tree this busy; only a longer window is.

The registry-validation refusal was quoted verbatim rather than inferred — the
message named a missing extracted corpus sidecar for
`corpus/normatives/html/ley-41-1994-art-78.html` — and that file plus both its
`.extracted.md` and `.extracted.json` sidecars are present now. Whether they were
absent at probe time cannot be established retroactively, so the underlying cause
stays UNKNOWN rather than being recorded as a missing sidecar. A legal-reference
refusal has several distinct shapes with different owners: a missing sidecar, a
`required_text` that does not match the resolved unit, and a `corpus_ref` naming a
file that exists under another name. The verbatim message names one of them; it is
not proof the named one was the defect.

THE RE-RUN ON THE FINAL TEXT, once registry validation was clean:

    uv run --no-sync pytest <five modules> -n0 -q -m ""
    3 failed, 23 passed in 213.31s

All three failures are one peer condition, and none touches this change:

    E   NoRevisionForPeriodError: modelo 200: no revision for year=2024 period='0A'

Modelo 200's `revision.toml` is UNCOMMITTED peer WIP and its `2024-y-siguientes`
revision now covers 2025 through 2030 but no longer 2024, so any test seeding a
prior-year 2024 Modelo 200 filing fails at snapshot resolution before reaching any
advisory. The two gates that pin this campaign's behaviour — the self-carries-advised
case and the first-ejercicio silence control — both PASS, confirmed by running them
in isolation:

    uv run --no-sync pytest <M200 live> -k "no_prior_filing or first_ejercicio"
    2 passed, 2 deselected

FOLLOW-ON READ. The grouping row should be re-read now rather than built on
today's assumption: with the subject on the context, ten Modelo 190 notices are at
least machine-separable, which changes what grouping has to achieve. It may now be
a presentation concern only.
