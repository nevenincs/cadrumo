---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:4f76da9596a6c61326a5ae49ec81fbfa92964c93c18bf4466f9b461f9c54e275'
step_id: 'S29'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-dead-surface-adr]]"
---
# adjudicate verify_declaracion against the live reconcile flow and record the overlap outcome in the exec record

## Scope

- `src/cadrumo/application/verification/`

## Description

- Ran mandatory semantic discovery against both the code and ADR corpora, then read the accepted dead-surface ADR, the entire verification package, and the live reconcile epicentres in full.
- Confirmed structurally that `verify_declaracion` has no production importer. Its only production references are docstring citations in `_reconcile.py` and `_reconcile_casilla.py`; the older `_verify.py` claim that it is a load-bearing reference implementation is displaced by the later accepted dead-surface ADR.
- Compared every capability produced or enforced by `verify_declaracion` with the living modelo reconciliation lifecycle.
- Ran the dead-package and living-reconcile behavioural suites together to establish the live boundaries before the deletion Step.

## Outcome

The adjudication finds no missing semantic that should be absorbed into the live post-filing reconcile implementation in this Step. The two surfaces answer different lifecycle questions wherever they do not overlap: the dead package recalculates an imported document without a persisted calculation revision, while the living reconcile intentionally compares external filed evidence with the canonical persisted revision and persists that result. Preserving the former behaviour inside reconcile would change the living lifecycle and create a second calculation path rather than close a gap.

| `verify_declaracion` capability | Live reconcile evidence | Disposition | Grounded reason |
| --- | --- | --- | --- |
| Parse and validate the filing period, then load the law-selected registry snapshot | `modelo_reconcile` parses with the addressed work unit's modelo, filing year, and period; `_reconcile_declaracion_casillas` resolves the registry snapshot from that work unit | covered | Reconcile already has a persisted, law-resolved lifecycle anchor. A second period parser and independent registry-root override would weaken that authority. |
| Reject a stamped declaration snapshot-reference mismatch | The production parser creates the observation against the law-selected snapshot, while reconcile resolves independently from the persisted work-unit triple and compares modelo, ejercicio, and period headers | dropped-with-grounded-reason | The mismatch branch protects construction of an injected standalone observation, not the production reconcile path. Reconcile must trust neither an observation-supplied revision nor a caller-selected registry root. |
| Fold verification expectations into computed, reconcile-when-present, tolerance, coverage-floor, and grounding sets | `_reconcile_declaracion_casillas` consumes `snapshot.verification_policy()`; `_pulled_filing_reconcile` consumes its tolerance | covered | The registry policy remains canonical living data even though this dead consumer is removed. |
| Build calculation inputs and execute a fresh registry calculation from printed values | Reconcile reads `CalculationRevision.casilla_values` selected by `_filed_revision_for_work_unit`; pulled-filing reconciliation reads the target revision under verification | dropped-with-grounded-reason | The reconciliation contract explicitly compares filed evidence with the canonical persisted revision. Fresh calculation is a different pre-filing question, duplicates the calculate lifecycle, and the dead wrapper is incomplete for current M100 because it cannot supply relation, enum, or date binding channels. |
| Detect missing formula-only binding values | The calculation lifecycle resolves and validates binding channels before a revision can become the persisted reconcile target | dropped-with-grounded-reason | Binding readiness belongs where the canonical revision is calculated. Reconcile should not reconstruct calculation inputs from a filed PDF or acquire a second missing-binding contract. |
| Convert numeric extracted values while excluding booleans and non-numeric rows | `_decimal_declaracion_values` implements the same Decimal/int-only projection | covered | The living declaration reconcile already owns the projection required for PDF value comparison. |
| Reconcile extracted computed casillas and reconcile situational casillas only when both sides carry them | `verify_declaracion` iterates extracted values and handles omitted computed casillas only through coverage/status; `_reconcile_declaracion_casillas` is stronger because it compares non-export-exempt computed ids in full and separately compares reconcile-when-present ids present on both sides | covered | The policy sets are the same, but the live filed-evidence path is intentionally stronger: it emits explicit missing/extra classifications and respects printed-record export exemptions rather than laundering omitted computed boxes into a ratio. |
| Apply registry tolerance to value comparison | `detect_casilla_divergences` receives `policy.tolerance`; pulled-filing findings use `_registry_reconcile_tolerance` | covered | The living path consumes the same strictest registry-published threshold. |
| Classify extraction-unreliable, unmodelled-rule, rounding, and correctness discrepancies | Parser coverage/failure semantics and the provisional-profile advisory own extraction reliability; authoritative policy scoping excludes unmodelled ids; within-tolerance differences produce no finding; material deltas become `VALUE_MISMATCH` | dropped-with-grounded-reason | The four-way taxonomy mixes parser quality, registry membership, tolerated noise, and value divergence. Those concerns already have separate living owners; porting the classifier would collapse them and duplicate `CasillaDivergenceKind`. |
| Carry expected, actual, signed delta, and casilla id per discrepancy | `CasillaDivergence` carries computed value, filed value, signed delta, id, and missing/extra/value kind; reconciliation diffs persist both rendered values | covered | The living carrier is at least as informative for the post-filing question. |
| Compute extraction coverage over computed casillas and gate status by `min_coverage` | The declaration parser refuses malformed, ambiguous, or below-profile-minimum extraction; reconcile then reports each missing computed casilla | dropped-with-grounded-reason | A second ratio after a successful parse is not needed for reconciliation honesty. The living layers already prevent low-coverage parse success and disclose missing reconciled values individually. |
| Derive `VERIFIED` or `NEEDS_REVIEW` with rounding non-blocking | `_finalise_reconciliation` derives `MATCHES` or `MISMATCHES` from typed diffs; advisories remain explicitly non-blocking | covered | Reconcile's verdict vocabulary reflects its actual external-evidence comparison. Retaining a second status enum would create two answers to one operator question. |
| Emit a locale-key narrative | Reconcile emits a concrete report narrative and persists typed diffs/advisories; modelo verification findings carry locale keys where operator localization is required | dropped-with-grounded-reason | The dead helper only selects one of two status keys and ignores its declaration, discrepancy, and coverage arguments. It adds no semantic detail beyond the living verdict. |
| Report registry snapshot id and verification expectation ids | The work unit is revision-bound and reconcile law-resolves the snapshot whose policy and grounding produce the comparison | dropped-with-grounded-reason | These fields describe the dead standalone calculation verdict. Reconcile's persisted work-unit and grounded diff records are its auditable anchors; copying dead report metadata would not restore a missing comparison. |
| Report `externally_grounded_casilla_ids` and `independently_grounded_fraction` | Every living casilla/total diff carries registry `legal_refs` and `source_refs`; the verification policy retains the external-grounding declaration for other living consumers and gates | dropped-with-grounded-reason | The accepted grounding-transparency ADR assigned the tuple and fraction specifically to `VerificationVerdict` as confidence metadata for fresh engine self-comparison. Post-filing reconcile compares against external filed evidence and persists grounding on actual findings. Moving the dead metric here would misstate a policy ratio as the strength of that external comparison. |
| Return a strict, frozen, JSON-roundtrippable verdict with verification timestamp | `ModeloReconciliationReport` and `ModeloReconciliationRecord` are strict frozen models; the record and bucket event persist atomically with `reconciled_at` | covered | The living lifecycle already has the durable typed carrier and timestamp. |
| Translate invalid snapshot, invalid policy, period, and missing-binding failures through a verification-specific error type | Reconcile uses typed evidence, unsupported-source, cross-bucket, work-unit, and advisory outcomes scoped to its lifecycle | dropped-with-grounded-reason | A verification-package error hierarchy has no surviving caller. Snapshot/policy absence is disclosed as `snapshot_unavailable`; calculation-input failures remain in calculation. Retaining or copying the dead error type would be a compatibility surface forbidden by the governing ADR. |

The accepted `2026-08-10-casilla-schema-dead-surface-adr` therefore remains implementable as written: S30 may delete the package, tests, facade entries, displaced docstring citations, and registry consumer rows without first changing the living reconcile code. This Step deliberately performs none of those deletions.

## Verification

- Mandatory code RAG: `uv run --no-sync vaultspec-rag search "verify_declaracion fresh calculation classification coverage status narrative snapshot binding external grounding reconciliation only:prod" --type code --port 8766 --timeout 120` â€” exit 0; the dead verifier and registry verification-policy owner were the leading cluster.
- Mandatory ADR RAG: `uv run --no-sync vaultspec-rag search "accepted dead verification surface verify_declaracion overlap live reconcile disposition" --type vault --doc-type adr --port 8766 --timeout 120` â€” exit 0; the accepted dead-surface ADR was the leading result.
- Production reachability census: parsed production Python imports under `src/cadrumo` while excluding tests and the package itself â€” zero importers; only `_reconcile.py` and `_reconcile_casilla.py` contain textual `verify_declaracion` references, both in explanatory prose.
- Behaviour: `uv run --no-sync pytest -q src/cadrumo/application/verification/tests src/cadrumo/application/modelo/tests/test_reconcile_casilla_divergence.py src/cadrumo/application/modelo/tests/test_reconcile_declaracion_casillas.py src/cadrumo/application/modelo/tests/test_reconcile_declaracion_casillas_multi_modelo.py src/cadrumo/application/modelo/tests/test_pulled_filing_divergence_reconcile.py src/cadrumo/application/modelo/tests/test_m303_m349_intracom_reconcile.py` â€” 78 passed in 33.00 seconds.

## Notes

- No production or test code changed. The verification package remains intact for S30.
- No registry consumer row, facade export, or displaced citation was removed; those are S30 scope.
- No audit, plan check, staging, or commit was performed.

