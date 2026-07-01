---
tags:
  - '#audit'
  - '#modelo-verify-nonzero-guards'
date: '2026-07-01'
modified: '2026-07-01'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-adr]]"
  - "[[2026-06-30-m210-categorical-conditional-predicate-adr]]"
---

# `modelo-verify-nonzero-guards` audit: review closeout (code review + honesty review)

## Scope

Wave `W03` `P09` closeout for the `modelo-verify-nonzero-guards` campaign. Two
independent fresh-context reviews were run against the completed work: a code
review (safety / correctness / architectural intent) and an honesty review
(claim-vs-reality against the campaign close, per the campaign-close honesty
mandate). This document persists both reviews' findings and records the
disposition of each, plus the follow-up items surfaced during remediation. The
campaign is not structurally complete until every honest-pass item is closed
with verification or formally deferred with a tracked follow-up, and the scoped
campaign changes are committed without sweeping unrelated peer WIP; this
document is the review ledger. The scoped commit condition is satisfied by
commit `5592a0a3a`.

## Findings

### review closeout | critical | M210 inmobiliaria guard was unreachable in production — FIXED

The code review found the `casilla_equals_implies_nonzero(["tipo_renta",
"inmobiliaria", "base_imponible"])` guard could never fire for a real filing: it
reads operator-entered `tipo_renta` from `input_values_by_casilla_id`, but the
live calculate path (`calculate_modelo_revision` -> `resolve_calculation_inputs`
-> the CLI `--casilla` surface) was Decimal-gated end to end, so a
`data_type = "text"` casilla could never be populated. The same root cause left
the pre-existing `m210_resolve_base_imponible` inmobiliaria branch dead in
production. RESOLUTION: the write-side text channel was wired end to end — a
`text_casilla_inputs` channel routed from the CLI (`_calculate_input.py`,
`data_type`-aware `--casilla` routing + `ModeloCalculateTextInputError` + an
English empty-value locale key) through
`calculate_modelo_work_revision` and both bucket-aggregation wrappers into
`calculate_modelo_revision`, which now passes `text_inputs=` to
`calculate_registry_snapshot` and merges the canonical text entries into the
persisted `input_values_by_casilla_id`. The companion ADR's earlier
"already reaches" claim was corrected with a post-review note (true only for the
read half). Verified after the review fixes: ruff clean on the affected files,
the combined predicate/workflow slice passed with 87 tests, the broader registry
slice passed with 134 tests, the broader application verification slice passed
with 85 tests, and full-tree collect-only remained clean. This also unblocks the
pre-existing dead inmobiliaria base formula. A dedicated end-to-end integration
test is tracked as `DFR-M210-INMOBILIARIA-E2E` below; the predicate is proven by
unit-level FIRES/HOLDS tests and the text-channel validation by focused
regression tests.

### review closeout | medium | M123 aggregate guard false-positive claim — GROUNDED (sound)

The code review asked whether the M123 `implies_nonzero(["06", "09"])` ADVISORY
could false-fire against IRPF withholding exoneration/reduction cases. A
grounding pass (persisted in the `2026-07-01-modelo-verify-nonzero-guards-audit`
document) concluded no legitimate "base total positive / retenciones total zero"
case exists within the guard's capital-mobiliario scope: the capital-semilla 60%
reduction bottoms at 7.6% (never zero), and the negative-declaration cuantia
mechanism applies only to trabajo/pensiones. RESOLUTION: guard unchanged
(sound). Residual: RD 439/2007 arts. 74-76 (the type-based exoneration list) are
not bundled in the corpus — tracked as a follow-up below.

### review closeout | high | M202 casilla-33 and B2 lane were silently dropped — ADDRESSED

The honesty review found the M202 casilla-33 floor and the B2 grupos-fiscales
lane (casillas 61-66) were flagged in research then never decided or tracked.
RESOLUTION (persisted in
`2026-07-01-modelo-verify-nonzero-guards-m202-deferred-items-audit`): casilla-33
is a documented non-guard (an ungrounded LIS art. 40.3 large-group floor gated
by a categorical CN>=10M fact no casilla carries — not predicate-expressible);
the B2 tramo-3/tramo-4 edges got two new ADVISORY `percent()`-relationship
guards. A third, new critical finding was surfaced and escalated (below).

### review closeout | high | most campaign work remained uncommitted - RESOLVED

The honesty review flagged that most of the campaign's product sat uncommitted
in the shared worktree (only the M210 base guard had landed, via a peer's
pathspec-less commit). The earlier closeout draft incorrectly claimed this was
already resolved by atomic explicit-pathspec commits. That claim was false when
the honesty review ran. RESOLUTION: commit `5592a0a3a` landed the scoped
campaign files and vault records with an explicit pathspec while leaving
unrelated staged peer files outside the commit. Residual dirty worktree state
after that commit belongs to other active campaigns and is not part of this
feature closeout.

### review closeout | critical (follow-up) | M202 casilla-26 (B2 resultado previo) is consumed by no formula

Surfaced during the B2 investigation: casilla `26` (B2 resultado previo) is read
by no formula in any of the three M202 revisions — `modalidad-40-3-resultado`
(casilla `32`) reads only casilla `18` (B1), byte-identical across revisions.
Likely a formula-wiring defect, not a predicate-scope gap. Deliberately NOT
patched with a speculative predicate over unverified formula semantics.
Documented deferral `DFR-M202-B2-RESULTADO-FORMULA-WIRING`: verify the B2
resultado wiring against the AEAT instructions / Diseno de Registros xlsx before
any formula change.

### review closeout | low | unrelated reformatting + latent BLOCKING_RULE mis-declaration gap

The code review noted (a) minor unrelated reformatting bundled into touched
files (harmless), and (b) that the new `casilla_equals_implies_nonzero` operator
is ADVISORY-only by convention with no registry-build guard preventing a future
`BLOCKING_RULE` mis-declaration — an accepted, pre-existing asymmetry (mirrors
`equals` / `advisory_when_ratio_ge`), documented in the companion ADR. No action
required; recorded for visibility.

## Recommendations

Resolved deferrals and remaining follow-ups from this closeout:

- `DFR-M210-INMOBILIARIA-E2E`: RESOLVED — `test_modelo_210_inmobiliaria_e2e.py`
  drives `calculate_modelo_revision` -> `verify_modelo_revision` with a
  `tipo_renta` text input reaching the persisted `input_values_by_casilla_id`,
  asserting the inmobiliaria ADVISORY fires on a genuine sub-cent silent-zero
  base and holds when the base computes (the `dias_imputacion = 0` scenario is
  refused by the engine, so a one-day sub-cent fact rounding to EUR 0.00 was
  used instead). Committed `d10662573`. 2 tests pass.
- `DFR-M210-TEXT-INPUT-LOCALE-PARITY`: STILL OPEN — the text-input empty
  refusal is present in `_calculate_input.py` as
  `application.modelo.errors.calculate_text_input_empty`, but a scoped
  catalogue search found no locale/catalogue entry for that key. The existing
  core error registry key `errors.refused.modelo_calculate_text_input` is a
  different envelope-level message. This needs a sanctioned locale/error-message
  pass rather than a closeout claim.
- `DFR-M123-RIRPF-EXONERATION-CORPUS`: RESOLVED — RD 439/2007 art. 75.3
  (BOE-A-2007-6820, vigente) was bundled as `rd-439-2007-art-75.html` and
  catalogued as `rd-439-2007:art-75`. The corrected conclusion is not that only
  letras b/c touch capital mobiliario; it is that art. 75.3 exceptions with no
  withholding obligation do not populate a positive M123 withholding-base
  declaration, while carve-back/payment-on-account cases remain covered by the
  existing positive-base advisory. Committed by the owner as `b860c576e`.
- `DFR-M202-B2-RESULTADO-FORMULA-WIRING`: RESOLVED — confirmed a real defect
  against the bundled AEAT M202 instructions (casilla 32 dropped the B2 casilla
  26 resultado); fixed to `add([18],[26])` across all three revisions with a
  `required_text` evidence-gate citation and non-tautological tests. Committed
  `cb002833a`.

Two adjacent pre-existing defects were surfaced while proving DFR-M210 (NOT
caused by this campaign; they live in other subsystems and are tracked for a
separately-grounded follow-up):

- `FUP-M210-ENUM-DISPATCH-ARG-INDEX`:
  `_ENUM_DISPATCH_BINDING_ARG_INDEX["m210_resolve_rate"] = 3` is stale for the
  current 6-arg form (country binding is now at index 5), so the bucket-profile
  auto-resolution of `country_of_fiscal_residence` can misroute the string onto
  the Decimal channel and raise. Needs an index correction + a regression.
- `FUP-FILING-DRAFT-TEXT-CASILLA`: the post-verify filing-draft builder
  (`_decimal_input` in `application/filing`) does not accept `data_type = "text"`
  casilla inputs, so an inmobiliaria M210 draft would raise on `tipo_renta`.
  The verify-stage guard (this campaign's scope) is unaffected; extending the
  text channel into the filing-draft stage is the follow-up.

The fresh honesty review did run and is persisted here. Its commit-state blocker
is resolved (the campaign's substantive work is committed across
`a7992b56f`, `3cb07b8bd`, `5592a0a3a`, `b860c576e`, `cb002833a`, `d10662573`).
No re-export hunk is part of this closeout. Current follow-up work must import
and test from owning modules directly, not from package facades, per the active
no-reexports direction.
