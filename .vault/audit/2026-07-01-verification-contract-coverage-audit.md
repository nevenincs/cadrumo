---
tags:
  - '#audit'
  - '#verification-contract-coverage'
date: '2026-07-01'
modified: '2026-07-01'
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

## Recommendations

Do NOT mechanically enroll the 922 casillas: at `min_coverage = 1` it breaks
regulated verify verdicts and invents legal behaviour. The correct pipeline is an
ADR deciding the enrollment policy per modelo (which computed casillas are genuinely
reconcilable against that modelo's AEAT Diseño de Registros / oracle, and the
`min_coverage` that keeps VERIFIED filings VERIFIED), then a per-modelo grounded
campaign gated by verify-gate regression tests. Start with the three NO-VE computing
revisions (151, 210, 714 - 2-4 casillas each) and the small curated gaps
(130/131/200/303), each grounded in its revision's existing AEAT `source_refs` and
proven non-breaking against the verify gate. The M100 Renta bulk is enrolled last,
reconciled against the Renta WEB Open oracle. The S56 operator numeric value-oracle
is grounded in the same Renta WEB Open captured figures (Modelo 100), not a
fabricated number.
