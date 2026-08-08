---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:e923d6acf38d47ed28c80561e38c423ab623eb281bd7cde2e58e06a6f63f1beb'
step_id: 'S04'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-pulled-fact-classification-reference]]"
  - "[[2026-08-08-synced-history-consumption-pulled-fact-consumption-census-reference]]"
---

# Investigate whether previous renta values are consumed

## Scope

- `src/cadrumo/application/calculations`
- `src/cadrumo/_data/registry/aeat/modelos/100`

## Description

- Enumerate the renta carry surface from the loaded authority: every
  `previous_filing` binding whose source is a renta modelo, with its selector, its
  aggregation op, and whether its source modelo is its own.
- Measure the revision-year coverage of the modelos in the chain, since a carry
  can only reconfirm a stamp for a triple the registry has a revision for.
- Establish what the revision re-confirmation gate can actually refuse on a
  PULLED observation specifically, rather than on a carry in general.
- Test each carry against the one-mechanism-per-calculation-type taxonomy and
  name the row it enrols under, or record that no row covers it.

## Outcome

Yes, a pulled prior-year renta filing can feed the current year, and it does so
through a mechanism that has no row in the taxonomy.

MECHANISM. Of the 17 `previous_filing` bindings in the registry, 13 are
same-modelo static carries and enrol cleanly under the taxonomy's
"same-modelo static carry -> a direct previous_filing binding" row. Three more
are cross-modelo, modelo 353 reading modelo 322, and every one of them declares
`grouping = "per_grupo_member"`, so they are the taxonomy's cross-member fan-in
row and are correctly placed.

The seventeenth is not. `irpf.previous_year_economic_activity_net_income` on
modelo 130 declares `source = "previous_filing"` with a selector naming
`source_modelo = "100"`, `filing_year_delta = -1`, `period = "0A"`, an aggregation
op of `sum` over four modelo 100 casillas (`0224`, `1479`, `1553`, `1577`), and
`grouping = None`. That is a cross-MODELO fold-in, and the taxonomy's row for a
cross-MODELO fold-in is a relation — `cross_model_output`, `annual_summary` or
`previous_period` — not a `previous_filing` binding. It carries no grouping axis,
so the cross-member carve-out does not cover it either.

So the finding the gate asks for is the second branch: NO ROW COVERS IT, and the
taxonomy needs amending before any code lands on this carry. It is the one renta
carry that reads another modelo's annual return, which makes it exactly the carry
a pulled modelo 100 history would feed, and it is the one modelled outside the
declared mechanism set.

THIS IS AN EXISTING VIOLATION OF A STANDING RULE, not an unclassified row, and the
two get different treatment. An unclassified row invites a judgement call about
where it belongs. A rule violation admits only two dispositions: the fix, or an
explicit amendment that names the rejected design.

The standing rule requires that a new aggregation surface enrol under an existing
taxonomy row or amend the record before shipping. This binding does neither. It is
the taxonomy's own defect class — a fold-in modelled by the wrong mechanism, so the
enrolled resolver's coverage and the binding's actual shape diverge — which is
precisely what the taxonomy was written to prevent. Recording it as "unclassified"
would let the ruling absorb it as one more thing to classify, and it is not that.

REVISION RE-CONFIRMATION, and what it cannot do. Modelo 100 ships one revision
per filing year, 2020 through 2025, each covering exactly its own year. Modelo 130
ships one revision covering 2019 through 2030.

A pulled observation's stamp is not supplied by the pull.
`persist_filed_calculation_observation` calls `save_observation` without
`stamped_revision_id`, so the repository resolves the law-determined revision for
the observation's own `(modelo, filing_year, period)` and stamps that. The carry
gate then re-confirms the stamp by resolving the law-determined revision for the
same triple. The two resolutions are the same call against the same authority, so
for a pulled observation the re-confirmation CANNOT refuse.

That is not a defect: the stamp genuinely is law-determined, which is what the
rule requires. But it means the gate adds no assurance on this path, and any claim
that the pulled renta carry is "protected by revision re-confirmation" would be
overstated. The gate exists to catch a stamp a producer supplied from a snapshot
it held; the pull supplies none. The rule's warning that the carry path is where a
revision error compounds across years still stands — it is just not this gate that
would catch it here.

A DATED CLIFF, and it is silent. Modelo 130's revision covers filing years to
2030 while its modelo 100 source tops out at 2025. The modelo 130 carry for
filing year 2026 asks for modelo 100 / 2026 / 0A. As of 2026-08-08 no modelo 100
revision covers 2026, so no such observation can exist — a pull of a modelo 100
2026 filing would refuse at the snapshot lookup inside
`registry_observation_from_filed_declaration` before it could be persisted. The
carry then finds nothing in the store and resolves to nothing, and
`resolve_bindings_from_local_store` documents that behaviour explicitly: bindings
the local store cannot satisfy are skipped silently, and the engine emits a blank
the operator fills by hand.

Same floor at the other end: modelo 130's 2019 filing year would carry from
modelo 100 / 2018, and no modelo 100 revision covers 2018 or 2019 either.

So the renta chain is bounded at both ends by its source's revision coverage, and
at both boundaries the failure is a silent blank rather than a refusal. That is
the campaign's own failure shape, arriving from a direction the research document
did not consider: not an unwired consumer, but a wired consumer whose source
revision does not exist.

## Verification

    uv run --no-sync python <scratch>/renta_probe.py
    100/2020..100/2025: one revision per year, 2020..2025
    130/2019-y-siguientes: 2019..2030
    same-modelo  13 previous_filing bindings
    CROSS-MODELO  3  353 <- 322, all grouping='per_grupo_member'
    CROSS-MODELO  1  130 <- 100, grouping=None, op=sum

The same-modelo and cross-modelo counts sum to 17, matching the census's
`previous_filing` subtotal, so no binding was missed in the partition.

The selector for `irpf.previous_year_economic_activity_net_income` was printed
whole rather than summarised, so the `source_modelo='100'`,
`filing_year_delta=-1`, `grouping=None` combination that places it outside the
taxonomy is read off the compiled object rather than inferred from the TOML.

The claim that the pull supplies no revision stamp was read from
`persist_filed_calculation_observation`'s call site: it passes `observation`,
`source_kind`, `captured_at` and `source_metadata`, and no
`stamped_revision_id`, so the repository's documented fallback resolves it.

No pytest lane was run and no production file was changed: this row is an
investigation.

## Notes

WHAT I COULD NOT MEASURE. Whether AEAT's declarations register actually exposes
modelo 100 casillas `0224`, `1479`, `1553` and `1577` on the consulta view the
reader is pinned to. Without them the modelo 130 carry has nothing to sum even
when the modelo 100 filing was pulled successfully, and the extraction-coverage
refusal is all-or-nothing per filing, so a register row lacking them would refuse
the whole modelo 100 observation rather than deliver a partial one. Establishing
that needs a real captured artefact, which no live read may be performed to
obtain, and it is not inferable from the registry. Stated as unmeasured rather
than assumed either way.

I have NOT amended the taxonomy. The gate offers naming the row or recording that
none covers it, and this record takes the second branch. Amending an aggregation
taxonomy is a decision-record change belonging to `P02.S07`, and doing it here
would pre-empt the ruling this lane exists to produce. The debt is stated so the
ruling has to dispose of it, and stated as a rule violation so it cannot be
absorbed as a classification question.

THE DATED CLIFF IS NOW A ROW, `P01.S13`. This record originally kept it as a
finding on the ground that a filing year AEAT has not published cannot carry, which
is true and is also the argument against keeping it a note: the failure is silent
by documented design, it arrives at BOTH ends of the range, and the condition that
makes it live is modelo 100 shipping a 2026 revision, which nobody is watching for.
"Re-check if X ships before this lane closes" is the shape that vanishes when a
lane closes. The row gates on the PROPERTY — every carry source's revision coverage
must span the consuming modelo's own coverage — rather than on the 2020-2025 and
2019-2030 spans, which are today's corpus and would turn the gate into a constant
someone updates.
