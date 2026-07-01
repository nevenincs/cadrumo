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
document is the review ledger, not a commit record.

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

### review closeout | high | most campaign work remains uncommitted - NOT YET CLOSED

The honesty review flagged that most of the campaign's product sat uncommitted
in the shared worktree (only the M210 base guard had landed, via a peer's
pathspec-less commit). The earlier closeout draft incorrectly claimed this was
already resolved by atomic explicit-pathspec commits. That claim is false at the
time of this audit update: relevant campaign files and vault records are still
modified or untracked in the shared worktree. DISPOSITION: keep this as a
closeout blocker until a scoped explicit-pathspec commit lands, or until the
orchestrator records why the campaign is intentionally left as active WIP. Do
not claim structural completion from this audit alone.

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

The following deferrals are explicitly tracked out of this closeout:

- `DFR-M210-INMOBILIARIA-E2E`: add an end-to-end integration test constructing
  registry-valid inmobiliaria inputs through `calculate_modelo_work_revision`,
  asserting the persisted `input_values_by_casilla_id` carries `tipo_renta` and
  the advisory fires.
- `DFR-M210-TEXT-INPUT-LOCALE-PARITY`: add the
  `application.modelo.errors.calculate_text_input_empty` locale key to the
  non-English catalogues through the sanctioned locale CLI once current locale
  peer WIP is no longer in the way.
- `DFR-M123-RIRPF-EXONERATION-CORPUS`: bundle RD 439/2007 arts. 74-76
  (BOE-A-2007-6820) into the corpus and cite the type-based exoneration list,
  closing the M123 residual grounding gap with verbatim text.
- `DFR-M202-B2-RESULTADO-FORMULA-WIRING`: verify and, if confirmed, fix the
  M202 casilla-26 / casilla-32 B2 resultado formula-wiring defect against the
  AEAT Diseno de Registros.

The fresh honesty review did run and is persisted here. It did not approve full
structural closure: it blocks closure on the still-uncommitted campaign state
and requires the deferrals above to stay visible until separate follow-up work
lands.
