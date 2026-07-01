---
tags:
  - '#research'
  - '#pension-rescate-dt12-classification'
date: '2026-07-01'
modified: '2026-07-01'
related:
  - '[[2026-07-01-pension-rescate-dt12-classification-adr]]'
  - '[[2026-05-27-dt-12-rescate-plan-pensiones-adr]]'
  - '[[2026-06-15-art20-trabajo-reduccion-compute-adr]]'
---

# `pension-rescate-dt12-classification` research: `DT 12a rescate classification and time-window eligibility`

Issue #544 (P1). The DT 12a LIRPF 40% reduccion on lump-sum plan-de-pensiones
rescate is already computed (`compute_dt12_reduccion_plan_pensiones`, the
pre-2007 contribution split axis, the apartado-2 subset invariant). What is
missing is the guided classification channel: a rescate-type axis (total vs
parcial) and the apartado-4 time-window eligibility gate. Today the 40% applies
unconditionally whenever the three split amounts are supplied, so an out-of-window
rescate (contingencia deadline elapsed) receives a reduccion the law no longer
grants -- a silent over-reduction (which is under-declaration of tax). This research
grounds the legal window against the bundled corpus and the existing code surfaces so
the ADR can decide the classification axis, the gate, and its blocking posture.

## Findings

### F1 - The 40% reduccion core is modelled; the eligibility gate is not

`compute_dt12_reduccion_plan_pensiones` (`src/aeat/domain/modelos/_dt12_reduccion.py`)
computes `pre_2007 / totales * gross_rescate * 0.40`, rounds to cents, and guards
three preconditions: `totales > 0`, non-negative inputs, and `pre_2007 <= totales`
(the apartado-2 subset invariant). The rate `DT12_RESCATE_REDUCCION_RATE = Decimal("0.40")`
lives in `src/aeat/core/external_constants.py:624`. The function is pure and
unconditional: given a valid split it always yields the 40% reduccion. There is no
contingencia-year or rescate-year (percepcion-year) parameter, hence no apartado-4
window evaluation anywhere in the codebase (confirmed by RAG + grep: the only DT12
sites are the domain compute, the CLI flags, the shortcut-input injection, and the
verify-time advisory).

### F2 - Injection is a calculate-time shortcut, keyed by semantic role

The three amounts enter through `work calculate` flags
(`--rescate-plan-pensiones-capital`, `--rescate-plan-pensiones-aportaciones-pre-2007`,
`--rescate-plan-pensiones-aportaciones-totales`,
`src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py:169-198`). They are parsed to
`Decimal | None` and threaded through `build_work_calculate_input_bundle` into
`apply_calculation_shortcut_inputs` (`src/aeat/application/modelo/_calculate_input.py:649`).
That function enforces the all-or-none co-requirement, calls the domain compute, and
writes the result into the unique-semantic-role casilla
(`_REDUCCION_TRABAJO_SEMANTIC_ROLE`). It returns `(casilla_values, binding_values)` only
-- it has no advisory return channel today. This is the single site where the
year facts, if added as inputs, would be available.

### F3 - Two established advisory channels; the precedent is advisory-first

Two distinct non-blocking diagnostic surfaces exist, both grounded and both avoiding a
hard block on a fact-dependent eligibility:

- Calculate-time: `CalculationSourceDiagnostic` rows (the `source_advisories` /
  `ADVISORY:` line), fanned out by `collect_bucket_aggregation_advisory_diagnostics`
  (`src/aeat/application/modelo/_calculation_diagnostics.py`) after the revision is
  computed. These read the revision structure and the computed casilla map.
- Verify-time: `ModeloVerificationFinding` with
  `ModeloVerificationFindingKind.ADVISORY` (`src/aeat/domain/modelos/_verification_report.py:76-90`),
  appended in `_collect_revision_verification_findings`
  (`src/aeat/application/modelo/_verification_actions.py:1485-1497`). The existing DT12
  advisory (`_dt12_advisory.py`) and the art-20 advisory (`_art20_advisory.py`) both
  live here and read only `casilla_values` keyed by semantic role.

The art-20 precedent (`2026-06-15-art20-trabajo-reduccion-compute-adr`, worked in
`_art20_advisory.py`) is directly on point: it makes the finding ADVISORY, not
blocking, precisely because the eligibility gate is fact-dependent, so a
legitimately-zero reduction must stay permissible per `no-silent-under-declaration`.
The existing DT12 advisory, however, is authored as `BLOCKING_RULE` kind with `WARNING`
severity (a large-trabajo heuristic) -- an inconsistency worth noting but out of scope.

### F4 - The verify-time channel cannot see the year facts

The verify-time collectors read only `casilla_values` (the semantic-role casilla map)
and the profile. The contingencia-year and rescate-year are neither casillas nor
profile facts (the prior ADR `2026-05-27-dt-12-rescate-plan-pensiones-adr` D3
Alternative A explicitly rejected persisting the pre-2007 split on the profile,
reasoning DT 12a applies only in the year of rescue and must not silently persist).
Consequently the window gate cannot be a pure verify-time reader of the persisted
revision unless the year facts are first persisted onto it. The facts exist only at
the calculate-shortcut moment (F2). This is the load-bearing architectural constraint:
the window gate belongs on the calculate-shortcut path, co-located with the existing
injection, not on the verify path.

### F5 - Apartado-4 window rule (bundled-corpus verbatim)

Bundled consolidated LIRPF `src/aeat/_data/corpus/normatives/html/ley-35-2006.html`,
`#dtduodecima` block (lines 12701-12708). Apartado 4 (added by Ley 26/2014 art. 1.86,
`BOE-A-2014-12327`) decoded to a date-arithmetic rule over `contingencia_year` (year
the contingencia -- retirement, disability, death -- occurred) and `rescate_year` (year
the prestacion is percibida, normally equal to the filing year):

- contingencia >= 2015 (general rule): eligible iff
  `contingencia_year <= rescate_year <= contingencia_year + 2` (the year of the
  contingencia plus the two following -- a three-year window).
- contingencia 2011-2014: eligible iff `rescate_year <= contingencia_year + 8`
  (through the end of the eighth following ejercicio; contingencia 2011 window closes
  end of 2019, 2014 closes end of 2022).
- contingencia <= 2010: eligible iff `rescate_year <= 2018` (a hard 31-12-2018 cliff).

Verbatim apartado-4 text: "El regimen transitorio previsto en esta disposicion
unicamente podra ser de aplicacion, en su caso, a las prestaciones percibidas en el
ejercicio en el que acaezca la contingencia correspondiente, o en los dos ejercicios
siguientes. No obstante, en el caso de contingencias acaecidas en los ejercicios 2011 a
2014 ... hasta la finalizacion del octavo ejercicio siguiente ... En el caso de
contingencias acaecidas en los ejercicios 2010 o anteriores ... hasta el 31 de diciembre
de 2018."

For all filing years this app serves today (2019+), every contingencia <= 2014 branch is
already closed (the last, 2014, closed end-2022). So a 2026-filing rescate is in-window
only if the contingencia occurred in `rescate_year - 2` or later. The 40% applied
unconditionally today is legally wrong for any contingencia older than that.

### F6 - Rescate-type axis (total vs parcial): a guidance signal, not an arithmetic fork

The rescate-type (total = whole capital rescued at once; parcial = staged partial
withdrawals) does not change the formula -- the 40% applies to the pre-2007 share of
whatever amount is percibida. It changes the guidance: DGT criteria require, for the
reduccion to apply, that the prestacion be received en forma de capital, and for parcial
rescates each cobro in the same contingency must fall inside the apartado-4 window (the
window is measured once, from the contingencia year, and does not restart per partial).
The classification axis therefore earns its place as a typed guided-classification input
that (a) lets the app phrase the correct advisory (total -> single window check; parcial
-> warn that each partial cobro shares one window and that a mixed capital/renta rescate
may forfeit the regimen), and (b) records the operator-declared intent for provenance.
Full per-partial multi-cobro modelling (a rescate ledger with one window evaluation
spanning several filing years) is a larger surface than this issue needs.

### F7 - Legal catalogue entry exists and is grounded; window text not yet asserted

`ley-35-2006:dt-12` is already in the catalogue
(`src/aeat/_data/registry/aeat/legal/irpf.toml:2631`), `evidence_tier =
"legal_authority"`, `corpus_ref = "...ley-35-2006.html#dtduodecima"`, `document_id =
BOE-A-2006-20764`, `reviewed_by = "codex"`, `reviewed_at = 2026-06-28`. Its
`required_text` asserts apartado-1/2 phrases but not the apartado-4 window text.
Grounding the window gate should extend `required_text` with an apartado-4 distinctive
phrase (e.g. the "dos ejercicios siguientes" clause) so the evidence gate cross-checks
the window clause against the bundled corpus. Ley 26/2014 (`BOE-A-2014-12327`) is the
binding provision that establishes apartado 4 and may warrant its own catalogue entry
per `registry-calculation-legal-grounding` (the specific modifying law, not only the
framework DT).

### F8 - Scope boundaries / what was not investigated

- The DGT parcial "todo o nada" criteria and the mixed capital/renta forfeiture rule
  were read at a summary level from the corpus apartado structure, not exhaustively
  against every DGT consulta; the ADR treats them as guidance-advisory text, not a
  computed gate.
- Whether `rescate_year` should default to `filing_year` (the common case) or always be
  operator-supplied is an input-ergonomics question left to the ADR.
- The pre-existing DT12 verify advisory `BLOCKING_RULE` kind (F3) is a latent
  inconsistency with the art-20 `ADVISORY` precedent; not in scope here, flagged for a
  future cleanup.
- No change to the pre-2007 split arithmetic or its oracle test (Carla 6.981,82 EUR) is
  contemplated; the window gate wraps the compute, it does not fork it.
