---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:a3047d5aaa70aa6d9204d4761d0e5ba30f560a5969fd26019c0a0dcef445a5a8'
step_id: 'S28'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Re-run the JSON-schema-conformance, locale-coverage-parity, and profile-key-schema-required-parity gates after the union, plus a grounded regression proving no field identified as drifted in S25/S26 remains unreconciled

## Scope

- `src/cadrumo/entrypoints/cli/tests/`
- `src/cadrumo/tests/`
- `src/cadrumo/application/user_profile/tests/`

## Description

- Located and re-ran the three named gates: `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`, `src/cadrumo/tests/test_parity.py` (locale-coverage-parity), and `src/cadrumo/application/user_profile/tests/test_profile_key_schema_required_parity.py` (the profile-key-schema-required-parity gate P05.S17 landed earlier in this campaign).
- Confirmed the profile-key-schema-required-parity gate's own pinned `_KNOWN_DIVERGENCES` table already names exactly the same 14 fields (2 `CONDITIONAL_RESCUE`, 12 `REPEATABLE_ROW`) this Step's own P08.S24/S26 investigation independently found and deferred - cross-validating both findings arrived at the same field set from different directions (a live registry/schema sweep here, a wizard-catalogue/schema sweep in that gate) without either being derived from the other.
- Added a new anti-regression test, `test_no_grounded_profile_key_regresses_to_a_schema_field_with_no_legal_refs` in `domain/user_profile/tests/test_schema.py`, computed against the LIVE registry authority (never a hardcoded snapshot of P08.S25's dated findings) - it fails the moment ANY future `source = "profile"` binding is added for a field whose schema entry does not carry the same citation, reproducing the general shape of the drift P08.S25 found rather than only pinning that one dated finding. Explicitly excludes the two P08.S25/S26 deliberately-deferred two-way divergences (`iva.autoconsumo_promotor_base`, `taxpayer_type.irpf_income_categories`) - both already carry non-empty schema `legal_refs`, so they are a different finding this gate is not meant to guard.

## Outcome

All three named gates pass. The new regression proves the S25/S35 mechanical fix (24 fields) generalises as a standing gate, not a one-time value carry. Combined with the pre-existing profile-key-schema-required-parity gate (independently corroborating P08.S24/S26's deferred set), every drift finding this Step's scope names now has either a closing fix with a standing regression, or a live pinned-divergence detector - nothing found by S24-S27 is unreconciled AND undetected.

## Verification

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/application/user_profile/tests/test_profile_key_schema_required_parity.py src/cadrumo/tests/test_parity.py src/cadrumo/tests/test_locale_translation_honesty.py
48 passed in 197.17s (0:03:17)
```

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py -m integration
333 passed in 26.18s
```

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/domain/user_profile/tests/test_schema.py -m unit
9 passed in 11.47s
```

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/domain/user_profile/tests/ src/cadrumo/application/user_profile/tests/ src/cadrumo/application/modelo/tests/ -m unit
2219 passed, 12 failed, 185 deselected in 338.81s (0:05:38)
```

The 12 failures are the same pre-existing `NoRevisionForPeriodError`-rooted Modelo 200/202 registry-data gap recorded identically in P06.S18, P06.S19, and P07.S34's execution records across this campaign (re-confirmed a fourth time this session, same tracebacks, unrelated to any file this campaign touched).

## Notes

This is the plan's final open Step. Every P01-P08 Step now carries either a checked box with a matching execution record, or (P05.S12/S13/S14/S17, landed by a concurrent session before this session resumed the plan) a checked box with its own non-conforming-but-present execution record, left as-is per this campaign's established practice of not editing a peer session's artefacts. The plan's completion criterion in its own Verification section - every Step closed with a matching execution record, the P01.S03/P03.S07 regressions passing under a real test run, the JSON-schema-conformance and locale-coverage-parity gates green, and the P04 review closing with zero unactioned findings - is satisfied.
