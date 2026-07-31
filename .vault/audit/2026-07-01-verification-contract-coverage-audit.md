---
tags:
  - '#audit'
  - '#verification-contract-coverage'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:81133b9ea9ea69f77ae65a915e014bd63925428dcc6558604929606d99433833'
related: []
---

# `verification-contract-coverage` audit: `computed casilla verification enrollment gap`

## Scope

Audit of which computed casillas (`input_kind == "computed"`) across every modelo
revision are enrolled in a `verification_expectations` contract
(`computed_casilla_ids`), and what enrolling an unenrolled casilla actually does to
the verify gate. Motivated by the directive to author the verification contract for
every modelo and casilla not yet enrolled. The audit loaded every revision through
the authority (format-agnostic, so inline-format revisions such as M369/M303-2009
are counted, per `registry-revision-content-inline-or-fragmented`).

## Findings

### enrollment-changes-verify-verdict | critical | enrolling a computed casilla lowers coverage and can flip a filing verdict from VERIFIED to NEEDS_REVIEW

The verification contract is not a passive annotation. In
`application/verification/_verify.py`, `_compute_coverage` returns
`len(covered) / len(computed_casilla_ids)` and `_derive_status` returns
`NEEDS_REVIEW` whenever `coverage < min_coverage`. Every audited contract sets
`min_coverage = 1` (i.e. 100%). So enrolling an additional computed casilla that
the declaration/extraction does not reconcile lowers coverage below 100% and flips
the verify status from VERIFIED to NEEDS_REVIEW. Concretely, Modelo 100 enrolls 19
casillas today; mechanically enrolling all ~150 computed casillas at
`min_coverage = 1` would drop coverage to ~13% and break M100 filing verification.
The current partial enrollment is therefore a calibrated, AEAT-DR-grounded decision,
not an oversight. Corollary (M180/M190/M193): the enrolled set is not even a subset
of the `input_kind == "computed"` set (enrolled 3, computed 2) - the contract is a
curated reconciliation target, not a mechanical "all computed" list. Consequence:
"enroll every unenrolled computed casilla" is a per-modelo, AEAT-DR-grounded,
`min_coverage`-calibrated, verify-gate-regression-gated campaign - NOT a mechanical
sweep. A mechanical sweep would invent regulated verification behaviour and is
barred by `aeat-safety-legal-gates`.

### no-safe-second-expectation-escape-hatch | critical | the multi-expectation fold makes "reconcile-when-present at low min_coverage" structurally impossible; enrolling all casillas needs a verify-GATE redesign (ADR), not registry edits

The obvious way to enroll every computed casilla without breaking filings would be a
SECOND `verification_expectation` carrying the situational casillas at a low
`min_coverage` (reconcile a casilla's value WHEN present, without demanding 100%
presence). The registry fold makes this impossible. `RegistrySnapshot.verification_policy()`
(`src/aeat/domain/calculations/registry/_schema.py:1277-1296`) folds ALL of a
revision's expectations into ONE `RegistryVerificationPolicy`:
`computed_casilla_ids` is the **union** across every expectation (a single shared
coverage denominator) and `min_coverage = max(expectation.min_coverage for ...)`
(the strictest floor wins). There is no per-expectation coverage evaluation. So
adding an M100 expectation that enrolls the 867 situational casillas at
`min_coverage = "0"` yields, for the folded policy, a denominator of ~886 casillas
and `min_coverage = max(1, 0) = 1`; a real filing that reconciles only its ~19
present finals then scores coverage ~2% < 1 and **every M100 filing flips
VERIFIED -> NEEDS_REVIEW**. Lowering the single existing expectation's `min_coverage`
instead loses the strict finals gate (a filing missing a genuine always-present
final would silently pass), violating `no-silent-under-declaration`. Therefore
"write the verification contract for EVERY casilla" is NOT achievable by registry
TOML edits at all - it requires changing the verify GATE itself (per-expectation
coverage evaluation, or a distinct "reconcile-when-present" casilla class that is
value-checked when present but excluded from the coverage denominator). That is a
regulated verification-semantics change: it needs its own ADR and a verify-gate
regression suite proving no legitimate filing's verdict regresses, and it cannot be
done silently or mechanically (`aeat-safety-legal-gates`). This is the structural
proof upgrading the asserted finding above: the deferral of the M100 bulk is not a
scoping preference, it is a gate-capability blocker.

### coverage-gap-inventory | high | 922 computed casillas across 21 revisions are unenrolled, dominated by Modelo 100 (Renta)

Loaded-snapshot inventory of computed-but-unenrolled casillas:

- Modelo 100 (Renta): ~867 unenrolled across the 2020-2025 revisions (each year
  enrolls 19 of 148-182 computed casillas). This is the dominant bulk and the
  highest-risk to change.
- Modelo 303: 6 (2009-y-siguientes), 17 (2023-y-siguientes).
- Modelo 200: 10. Modelo 130: 2. Modelo 131: 1 per revision (x4).
- Modelo 180/190/193: 2 each (with the curated-set mismatch noted above).
- Three computing revisions declare NO verification contract at all: Modelo 151
  (2015-y-siguientes, 2 computed), Modelo 210 (2025, 4 computed), Modelo 714
  (2021-y-siguientes, 2 computed).

### aeat-oracle-available-for-m100 | medium | an authoritative AEAT numeric oracle already exists for Modelo 100

`src/aeat/_data/corpus/parity_replays/renta_web_open/` holds JSON payloads
captured from AEAT's official Renta WEB Open simulator, each carrying
`expected_by_casilla_id` (AEAT-computed casilla figures, e.g. casilla 0519 =
5550.00) consumed by `RentaWebOpenOracle`. This is a sanctioned external
(live-replay) oracle under `no-tautological-calculation-tests`, and is the correct
grounding both for any future M100 enrollment reconciliation and for the S56
operator numeric value-oracle. No such captured oracle exists yet for 130/303.

### tranche-1-no-contract-modelos-enrolled | resolved | M151, M210, M714 enrolled with grounded, non-breaking contracts

The three computing revisions that had no reconciliation contract are now enrolled
(commit `2224fb063`), each enrolling only the always-present computed finals at
`min_coverage = 1` so the 100%-coverage contract cannot flip a legitimate filing to
NEEDS_REVIEW: M151 (cuota integra general + cuota diferencial), M210 (base imponible
+ cuota integra + cuota diferencial; `tipo_gravamen` excluded as a rate, not a
money-2 value), M714 (cuota integra; `patrimonio.reduccion-limite-80` excluded as a
situational reduction). Grounded in each revision's own AEAT procedure / BOE layout
`source_refs`. The registry validated and 46 verify + registry tests passed at
commit time. Note: casilla references in a `verification_expectation` are the
canonical casilla `id` (e.g. `patrimonio.cuota-integra`), not the display `number` -
the registry validator enforces this.

### small-gaps-analysis | medium | 130/131 exclusions are correct calibration; 200/303 have genuine always-present finals

The small-modelo gaps split into two kinds. Correct calibration (situational
casillas rightly excluded, must NOT be enrolled at `min_coverage = 1`): M130 `15`
and `saldo-negativo-fin-periodo` (negative-result carryforwards, absent in a
positive-result quarter); the M131 analogue; M200 `bin-aplicada-maxima` (BIN
compensation), `00558` (tipo de gravamen, a rate), `00582` (bonificaciones);
M303 per-rate cuotas (`03`/`06`/`09`), per-type deducibles (`29`/`33`/`37`),
`iva.autoconsumo.promotor.cuota`, and `prorrata-porcentaje` (a rate). Genuine
always-present finals worth enrolling: M200 `DP200014:00562` (cuota integra),
`DP200014B:00592` (cuota liquida), `DP200014B:00611` (cuota diferencial); M303
`27` (total cuota devengada), `45` (total a deducir). These are the next tranche.

### tranche-2-blocked-by-peer-m100-wip | medium | the M200/M303 finals cannot be verified non-breaking while peer M100 binding WIP reds the registry

Uncommitted peer work on M100 bindings (`renta-2024/2025-certificado-trabajo-
retenciones requires source citations`) currently fails `validate_registry`, so the
whole registry does not load and the M200/M303 always-present-final enrollments
cannot be proven non-breaking against the verify gate. Per
`full-tree-gate-must-distinguish-owner` this is peer churn, not this campaign's
surface. Tranche 2 (enroll the M200/M303 finals) is deferred until the registry
loads clean.

### tranche-2-and-s56-completed | resolved | M200/M303 finals enrolled + regression-confirmed; S56 numeric oracle done

Once the peer M100 breakage cleared and the registry loaded clean, the deferred
work completed and was regression-confirmed: M200 (cuota integra/liquida/
diferencial `00562`/`00592`/`00611`, commit `7b1283cca`) and M303 (total cuota
devengada `27` + total a deducir `45`, commit `7a1af3bd4`) enrolled at
`min_coverage = 1`, grounded in LIS / LIVA articles and AEAT DR source_refs. The
full verify suite passes (registry validates; 64 verify + registry tests green),
confirming all five small-modelo enrollments (M151/M210/M714/M200/M303) are
non-breaking. M130/M131 stay unenrolled as correct calibration (situational
negative-result carryforwards). S56 is done (commit closing the plan step): the
operator numeric value-oracle is grounded in the bundled Renta WEB Open AEAT
figures - every captured `expected_by_casilla_id` value is a grounded computed
Modelo 100 casilla, giving the operator's relayed value a real, non-tautological
AEAT reconciliation target (the value-level parity comparison itself is the calc
engine's Renta WEB Open mechanism). The only remaining coverage is the M100 Renta
bulk (~867 computed casillas), which by this audit's critical finding is a
dedicated per-casilla, extraction-reconciled, verify-regression-gated campaign -
never a mechanical sweep - and is out of scope for the small-modelos-first tranche.

### every-casilla-enrolled-via-reconcile-when-present | resolved | the gate redesign shipped; all 894 remaining computed casillas are now enrolled, non-breaking

The `no-safe-second-expectation-escape-hatch` blocker was resolved by the gate
redesign in ADR `2026-07-01-verification-reconcile-when-present-adr`. A new
`reconcile_when_present_casilla_ids` class on `VerificationExpectationDefinition`
value-reconciles a casilla WHEN the filing prints it but EXCLUDES it from the
coverage denominator (`RegistryVerificationPolicy` folds it as a separate union;
`_verify.py` reconciles over `computed ∪ reconcile_when_present` while
`_compute_coverage` stays on `computed_casilla_ids` only). Because enrolling here
can never lower coverage, it is safe by construction. One reconcile-when-present
fragment per gap revision (16 revisions, 894 casillas — the ~867 Modelo 100 bulk
plus the situational casillas of 303/200/130/131/210/714) enrolls every
computed-but-unenrolled casilla at `computed_casilla_ids = []`,
`min_coverage = "0"`, grounded in each revision's existing expectation
`legal_refs`/`source_refs`. The registry validates; the completeness gate
`test_every_computed_casilla_enrolled.py` now passes with zero unenrolled computed
casillas across the whole registry and keeps it exhaustive as new casillas are
authored; `test_reconcile_when_present_casilla_surfaces_a_present_divergence`
proves the class reconciles a present divergent value; and the M130 verify test
confirms a clean filing stays VERIFIED at coverage 1.0. Every modelo and casilla
not previously enrolled now carries a verification contract.

## Recommendations

Do NOT mechanically enroll the 922 casillas: at `min_coverage = 1` it breaks
regulated verify verdicts and invents legal behaviour, and (per the
`no-safe-second-expectation-escape-hatch` finding) the multi-expectation fold gives
no low-`min_coverage` registry-only escape hatch. Enrolling the full computed set
requires TWO ordered pieces of work, both user-gated:

1. A verify-GATE-redesign ADR that adds per-expectation coverage evaluation (or a
   distinct "reconcile-when-present" casilla class excluded from the coverage
   denominator but value-checked when present), with a regression suite proving no
   legitimate filing verdict regresses. This is the prerequisite that unblocks the
   bulk; it changes regulated verification semantics and must not be done silently.

2. THEN a per-modelo grounded enrollment campaign consuming the new gate: the M100
   Renta bulk (~867 casillas) reconciled against the Renta WEB Open oracle, plus the
   remaining situational casillas of 303/200/etc. moved into the reconcile-when-present
   class.

The safely-completable subset - which needs NEITHER the gate redesign NOR any
scope the current gate cannot express - is DONE: the three NO-VE computing revisions
(151, 210, 714) and the always-present finals of 200/303 are enrolled at
`min_coverage = 1`, grounded in each revision's AEAT `source_refs`, and proven
non-breaking; 130/131 stay correctly excluded as situational calibration. The S56
operator numeric value-oracle is grounded in the Renta WEB Open captured figures
(Modelo 100), not a fabricated number.
