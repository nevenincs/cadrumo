---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:7a97d7d79776c3ed0c89c84a80b95cd5b433d71f3292be202d541893ccd575d6'
related:
  - "[[2026-08-10-casilla-schema-read-model-adr]]"
  - "[[2026-08-10-casilla-schema-plan]]"
---
# `casilla-schema` audit: `S23 modelo work review read model`

## Scope

Reviewed W03.P07.S23 against the accepted read-model ADR, the campaign plan and research, and the canonical derivation and blocker-spine dependencies. The review covered the new application-owned frozen read model and producer, its direct facade exports, and the two real encrypted-persistence tests. It checked law-resolved revision selection, persisted calculation and verification joins, concrete binding/formula/relation origins, official-reference derivation, blocker projection, identifier types, the S24/S25 ownership split, duplicate-authority absence, and prohibited test constructs.

## Findings

### date-binding-replay | high | Persisted date bindings make the read producer refuse valid calculated work

`build_calculation_replay_payloads` deliberately persists all resolved decimal, enum, and date bindings in the one `CalculationRevision.binding_overrides` replay map, with dates encoded as ISO strings. In `_resolved_bindings`, only enum-consumed identifiers are split out before every remaining value is parsed as `Decimal`. A valid persisted M100 revision carrying `renta-*-profile-taxpayer-birth-date = 1975-06-15` therefore raises `StoredCalculationDriftError` while merely building its review. The canonical registry already exposes `revision_date_binding_ids`; date-valued replay entries must be classified through that authority and excluded from the decimal comparison channel (or otherwise parsed into their real channel). The two focused tests exercise M130 only and cannot detect this common M100 failure.

### realised-origin-proof | medium | OPERATOR_OVERRIDE is stronger than the persisted evidence

`CalculationRevision.input_values_by_casilla_id` stores the fully resolved engine inputs, and `CasillaObservation` records only that a non-formula casilla was supplied; it does not persist whether that value came from an explicit casilla override or from a binding projection. The producer reconstructs origin by comparing the observation value with replay-resolved binding values. This necessarily labels an equal-value explicit override as `INHERITED`, and a later source-tier change can create or remove a mismatch when an optional binding was not persisted. Consequently the current `OPERATOR_OVERRIDE` assertion is not a truthful persisted-provenance claim. Either persist the origin at calculation time, or narrow the read-model vocabulary and documentation to an evidence-supported replay/value-divergence classification rather than asserting operator authorship.

### typed-record-identities | medium | The new typed read record erases canonical identity types

`ModeloWorkReview` declares `bucket_id`, `modelo`, `work_unit_id`, and `calculation_revision_id` as bare strings. Canonical `BucketId`, `ModeloCode`, `WorkUnitId`, and `CalculationRevisionId` owners already exist and are used by adjacent review/addressing records. The bare fields discard bucket constraints, modelo shape validation, and hex-identity validation at the new Pydantic boundary. The producer inputs and output record should use those canonical public types rather than redeclaring their wire representation as unrestricted strings.

## Recommendations

1. Split persisted replay bindings with the canonical enum and date-binding inventories before decimal parsing, and add a real encrypted calculated M100 regression that builds the review successfully.
2. Make realised origin epistemically honest: persist calculation-time origin or rename/narrow the classification so equality comparison is not represented as proof of operator override; add regressions for equal-value explicit input and for replay/source drift.
3. Type the record identities with the existing canonical aliases/value object and assert malformed values are refused plus facade identity remains exact.
4. Retain the current good boundaries: law resolution precedes stored-stamp comparison; official XML dictionary paths take precedence over printed numbers while fixed-width references fall back to the box number; verification reports are deterministically sorted by `run_at` before selecting the last report; both action errors used here are registered; one `BlockerRef` shape serves both grains; finding attribution remains S24 and progress remains S25.

## Verification

- Fresh VaultSpec RAG grounded the accepted read-model ADR, plan, research, producer, persistence contract, and canonical derivations.
- `pytest -q -n0 src/cadrumo/application/modelo/tests/test_modelo_work_review.py`: 2 passed.
- Scoped Ruff: passed.
- Scoped BasedPyright: 0 errors, 0 warnings, 0 notes.
- Facade runtime identity: passed for both `ModeloWorkReview` and `build_modelo_work_review`.
- Sole-declaration census: one `ModeloWorkReview`, one producer, and one `BlockerRef`.
- Prohibited test-construct census: no fake, stub, mock, patch, monkeypatch, skip, or xfail hits.
- Scoped `git diff --check`: passed.

## Verdict

CHANGES REQUESTED. The application ownership, canonical joins, law-resolved target selection, verification ordering, official-reference precedence, error registration, facade identity, blocker singularity, and S24/S25 split are sound. S23 cannot close while valid date-bound revisions can fail to render, realised operator provenance is inferred beyond stored evidence, and the new typed boundary uses unrestricted identity strings.
## Re-review 2026-08-11

### date-binding-replay-resolution | high | RESOLVED - canonical date and enum channels are no longer decimal-parsed

The replacement `_persisted_decimal_bindings` reads historical `CalculationRevision.binding_overrides` only, derives enum and date identifier sets from `enum_consumed_binding_ids` and `revision_date_binding_ids`, and parses only the remaining decimal channel. The new real-registry, encrypted-repository M100 regression persists an ISO date binding and successfully builds the review. No live profile resolver remains in this read path.

### typed-record-identities-resolution | medium | RESOLVED - canonical identity owners now type the producer and record

The producer and frozen record now use `BucketId`, `ModeloCode`, `WorkUnitId`, and `CalculationRevisionId`. The facade remains an exact direct identity export and no duplicate model or producer was introduced.

### realised-origin-proof-follow-up | medium | Missing binding evidence still produces an unsupported OPERATOR_OVERRIDE claim

The equal-value case is now explicitly documented and tested without an anomaly, and removal of live source replay eliminates the earlier time-dependent comparison. However, the implementation says `OPERATOR_OVERRIDE` is emitted only for disagreement between a persisted bound value and the persisted observation, while its condition is `observation.value not in binding_values`. When no matching binding is persisted, `binding_values` is empty and every observation satisfies that condition. The existing canonical replay code explicitly documents persisted observation-backed bound casillas that lack a matching `binding_overrides` value and recovers those records during filing replay. Such a record therefore has absence of binding evidence, not evidence of an operator override, yet the review labels it `OPERATOR_OVERRIDE`. The focused M130 assertion itself demonstrates the logical gap: `concrete_bindings[0].resolved is False` and `origin_anomaly is OPERATOR_OVERRIDE` are asserted together. Require at least one persisted comparable binding value before asserting disagreement, or otherwise represent the unknown origin without claiming operator authorship, and add the observation-backed/missing-binding regression.

## Re-review verification

- Fresh VaultSpec RAG grounded the current producer, tests, accepted read-model ADR, and canonical replay behavior.
- `pytest -q -n0 src/cadrumo/application/modelo/tests/test_modelo_work_review.py`: 3 passed.
- Scoped Ruff: passed.
- Scoped BasedPyright: 0 errors, 0 warnings, 0 notes.
- Scoped `git diff --check`: passed.
- Facade runtime identity and sole-declaration census: passed.
- Prohibited test-construct census: no fake, stub, mock, patch, monkeypatch, skip, or xfail hits.

## Final verdict

CHANGES REQUESTED. The date-channel and typed-identity findings are resolved, and historical-only replay is materially better. The realised-origin finding remains open because absence of a persisted comparable binding value is still classified as positive evidence of an operator override.
## Final correction re-review 2026-08-11

### realised-origin-proof-resolution | medium | RESOLVED - override requires a persisted comparable binding and actual divergence

The final condition now requires a non-empty tuple of persisted comparable decimal binding values before it can emit `OPERATOR_OVERRIDE`, and then requires the persisted casilla observation to differ from every such value. No persisted comparable binding conservatively returns `INHERITED` with no anomaly; `absent_by_design` also returns that conservative result before comparison. The real encrypted M130 regression now proves both sides with persisted evidence: a persisted income binding of 9000 against the caller-casilla observation 10000 yields `resolved=True`, `LITERAL`, and `OPERATOR_OVERRIDE`; a persisted binding equal to 10000 yields `INHERITED` and no anomaly. Equal-value explicit authorship remains intentionally irrecoverable and no provenance claim is made.

### final-gate-refresh | low | RESOLVED - the corrected current tree is green

Independent post-correction gates completed on the stable current files: the three focused real encrypted tests passed in 25.19 seconds, scoped Ruff passed, scoped BasedPyright reported zero errors/warnings/notes, and scoped diff-check was clean.

## Final accepted verdict

PASS. All three original findings are resolved. S23 now uses canonical typed identities, reads historical replay facts without invoking live profile resolution, separates enum/date/decimal binding channels through canonical registry derivations, refuses unsupported operator-authorship claims when comparable persisted evidence is absent, and retains the previously accepted application ownership, law-resolved revision selection, official-reference precedence, deterministic verification ordering, exact facade identity, blocker singularity, and S24/S25 scope split. No new findings remain.
