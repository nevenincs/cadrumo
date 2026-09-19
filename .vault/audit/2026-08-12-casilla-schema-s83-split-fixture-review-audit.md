---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:195dd0c0a4b1cffa2b664490da9f7db112edbe25194d670d6da7e1acd3832114'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# `casilla-schema` audit: `S83 split fixture review`

## Scope

Formal read-only review of `W05.P11.S83`, limited to `src/cadrumo/application/modelo/tests/test_e2e_ledger_m303_quarters_to_m390_annual.py` and its execution record. The review checked law-determined M303 revision selection, the evolved withdrawn-export assertions, local-filing-to-M390 behaviour, advisory-origin fidelity, absence of the retired target token or a mirrored selector, prohibited test doubles, and execution-record honesty. Bounded verification reran formatting, lint, static typing, the exact four-test module, and the retired-revision gate against the current shared worktree.

## Findings

### exec-honesty | high | resolved: the execution record now distinguishes implementation-time proof from the transient review-time obstruction

The initial execution record stated a passing exact module without identifying that the first formal-review rerun was blocked before any S83 assertion by concurrent untracked legal catalogues carrying draft review status. The corrected record now identifies its four-pass evidence as implementation-time evidence and records the transient shared-worktree obstruction without presenting it as a current pass or an S83 defect. After those peer-owned catalogues were completed, the bounded receipt rerun of the exact module passed all four tests in 35.06 seconds. The finding is resolved.

No S83 target defect was found. `_calculate_m303_quarter_revision` constructs a typed `Period`, asks `resources().modelos.authority.snapshot` for the applicable revision, and passes only that result as the creation-time equality assertion. The 2024 scenario reaches all four quarters through that helper, so it traverses both split revisions without a period-to-revision map. The target contains no retired M303 revision token, selector mirror, mock, fake, stub, monkeypatch, skip, xfail, alias, or compatibility path. Its export assertions exercise the production `ModeloExportUnsupportedError`, exact typed context, and absence of an output artifact; the cross-period advisory filters on the production `registry_relation` origin. Ruff formatting, Ruff lint, and BasedPyright are green for the target.

The repository-wide retired-revision gate now reaches its intended assertion and remains red on ten occurrences outside the S83 target, exactly matching the corrected execution record's carry-forward. That external gate does not invalidate the target's zero-token proof or exact four-test pass.

## Recommendations

- S83 may close on the corrected execution record and the receipt-time exact four-test pass.
- Keep the ten external retired-token occurrences assigned outside S83; do not widen this step or add tolerance in the reviewed fixture.
