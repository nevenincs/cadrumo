---
tags:
  - '#research'
  - '#verification-power'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:2807f7e840ae22ddd92a6e4a0af588fb973cef9668e1798a53d137ac6afad669'
related:
  - '[[2026-07-01-verification-reconcile-when-present-adr]]'
  - '[[2026-07-01-verification-contract-coverage-audit]]'
---

# `verification-power` research: `verification power baseline and roadmap`

Enrollment (every computed casilla named in a `verification_expectation`) reached
100% via the reconcile-when-present class. Enrollment is a ceiling, not a
verification result. This research measures what the enrolled contracts actually
verify, and lays out the grounded, non-fabricating roadmap to raise it.

## Findings

### VP1 — the verify gate reconciles filed value vs engine value; the engine emits every casilla when bindings resolve

`application/verification/_verify.py` compares each enrolled casilla's filed
(extracted) value against the engine's computed value: `expected =
result.values.get(casilla_id, actual)`. Measured on the Modelo 130 verify case
with resolved bindings, the engine emitted a value for all 20 casillas including
12/12 computed. So the feared "silent self-compare no-op" (a casilla the engine
never emits, reconciling against itself) is RARE on a filing whose bindings
resolve — reconciliation is genuinely active. The real limiters are (a) whether
the verify path can resolve a filing's bindings at all (else the whole calc
raises — loud, not silent) and (b) whether the engine's emitted value is itself
correct.

### VP2 — external per-casilla AEAT grounding is ~1% of computed casillas; the rest are engine-only reconciliation

A reconciliation is only as trustworthy as the value it compares against. That
value is independently AEAT-grounded only where an external oracle supplies an
expected figure. Measured across the whole registry (non-validating loader, to
survive concurrent peer churn):

- Registry-wide: 1149 computed casillas; ~16 carry any external per-casilla
  grounding (~1%).
- Modelo 100 2025: 185 computed; 4 externally grounded (2%) — the Renta WEB Open
  open-simulator replays under `corpus/parity_replays/renta_web_open/`, and only
  across 5 employee-default-minimo scenarios.
- Modelo 130/200/303/714: 0 per-casilla external oracle values. Their
  `workbook_parity_refs` are fixture/whole-workbook parity (empty `output_cells`),
  which grounds the export end-to-end but does not supply per-casilla oracle
  figures the way the replays do.

So ~99% of enrolled reconciliations are filed-vs-engine. That still has real
power — it catches taxpayer transcription errors, extractor errors, and any
filing-vs-engine divergence — but it CANNOT catch a systematic engine error that
the filing happens to match, because there is no independent oracle for that
casilla. The coverage-gated finals are the exception: they are grounded by
workbook parity and the calc-chain tests.

### VP3 — the verdict does not expose the grounding tier, so VERIFIED can read as more confident than it is

`VerificationVerdict` carries `status`, `discrepancies`, and `coverage` (the
fraction of coverage-gated casillas the filing PRINTED — a presence metric, not a
grounding metric). It does not distinguish an externally-oracle-grounded
reconciliation from an engine-only one. An operator reading VERIFIED cannot tell
how much of the filing was independently checked versus cross-checked against the
app's own engine.

## Roadmap (grounded, no fabricated figures)

Raising verification power means raising the count of casillas whose engine value
is validated against an AEAT-authoritative expected value. Ordered by leverage and
autonomy, and bound by `aeat-safety-legal-gates` / `no-tautological-calculation-tests`
(never invent an expected figure) and `legal-grounding-verifies-bundled-authoritative-corpus`:

- R1 (transparency, autonomous, safe): surface the grounding tier on the verify
  verdict — per enrolled casilla, whether its reconciliation is externally-oracle-
  grounded or engine-only — and a filing-level "independently grounded fraction",
  so VERIFIED is never falsely confident. Non-blocking; changes no verdict. This is
  the honest metric that operationalizes the target. Needs an ADR (verdict-shape
  change).
- R2 (offline grounding expansion, autonomous, high-value): extract AEAT-authoritative
  worked examples already bundled under `corpus/manuals/renta/` and the AEAT
  workbooks into per-casilla oracle fixtures (same shape as the Renta WEB Open
  `expected_by_casilla_id`). Every figure must be traced to the bundled authoritative
  text per `legal-grounding-verifies-bundled-authoritative-corpus`; no figure is
  hand-computed from the registry formula under test. This raises the grounded
  fraction without live capture.
- R3 (live oracle expansion, operator-run): capture Renta WEB Open replays across
  richer scenarios (autónomo/estimación directa, ganancias patrimoniales, deducciones
  autonómicas) under `AEAT_LIVE_TESTS_ENABLED=1`. Each new scenario grounds more of
  the 181 currently engine-only M100 casillas. Safety-gated; the agent cannot run it.
- R4 (measurement gate, autonomous): a durable metric test that reports the
  external-grounding fraction per modelo and ratchets it upward, so R2/R3 progress
  is tracked and regressions (a grounded casilla losing its oracle) fail loudly.

## Constraints

The registry was intermittently non-validating during this research due to
concurrent peer M180 source-refs WIP; all measurements used the non-validating
`load_registry_tree` compiler per `registry-revision-content-inline-or-fragmented`
and `full-tree-gate-must-distinguish-owner`. Any code landing for this campaign
must wait for a clean-validating registry to prove non-regression.
