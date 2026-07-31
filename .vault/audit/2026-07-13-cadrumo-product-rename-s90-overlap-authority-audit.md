---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s90-overlap-authority'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:2e3e9861f177bfacc311b01bf30ea509a7b6fd328e3541de3eaaa3d091c4f027'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename-s90-overlap-authority` audit: `S90 overlap authority code review`

## Scope

- Independently review commit `934a20eaaf6359dac2d5de98e2dd11031a4fe299` as the surgical remediation of mixed commit `12d80d1d42f5cc16e7923160d3d8a6bacfd25b21` against the binding identity ADR and overlap-audit requirements.
- Verify the ADR, runtime identity, contract tests, four parity expectations, preserved documentation wordmark, excluded locale/rule/documentation work, concurrent S89 plan row, reopened downstream steps, S90-only closure, execution record, live identity, rule synchronization, focused tests, plan checks, and vault health.
- Distinguish target-commit behavior from concurrent uncommitted S89 catalogue work without modifying either surface.

## Findings

### s90-parity-count | low | The execution record overstates the full parity-module pass count

The S90 record correctly attributes the sole full-module failure to `test_inter_locale_parity`, but states that 31 other tests passed. Both the target and current `test_parity.py` contain exactly 27 tests, and an independent full run reports 26 passed and one failed. This is a nonblocking evidence-count error; the separately claimed nine focused tests pass exactly.

### s90-pre-existing-hygiene | low | Formatting and plan-order warnings remain

`ruff format --check` reports that `test_parity.py` would be reformatted both from the exact target blob and from the current working file, confirming the execution record's pre-existing-format-drift note. Vaultspec plan check exits successfully but emits `PLAN022` because canonical Step identifiers are not strictly monotonic in document order, and the shared plan retains one generated annotation block. These warnings do not invalidate the surgical identity repair or block S89.

No critical, high, or medium findings were found. Verdict: **PASS**.

The accepted ADR restores `CADRUMO` as the exact product display and removes the mixed commit's title-case/wordmark-only mandate without losing the complete machine matrix. The target matrix section SHA-256 is `31de28d471e8c59b8f5cf669666063dd5094d811af90244754b5b633c2aec417`, byte-identical to the pre-mixed version, and covers `cadrumo`, `aeat`, `cadrumo-mcp`, `CADRUMO_`, both companion distributions, `cadrumo_data`, and `AEAT`. The truthful operator quotation is likewise restored byte-for-byte to its pre-mixed SHA-256 `88ca8b28a0f46161bd9397d2e38b332930220e921034a62155151da93607b040`.

Runtime `PRODUCT_IDENTITY.display_name`, its contract expectation, and the immutability assertion are restored to `CADRUMO`; the module and test prose follows the same binding display. Exactly four changed expectations in `test_parity.py` restore `CADRUMO`, while preserving `aeat` command invocations and lowercase machine identities. Nine focused real identity and locale-normalizer tests pass, scoped Ruff lint passes, and a live tuple assertion confirms `CADRUMO`, `aeat`, `cadrumo`, `cadrumo-mcp`, `CADRUMO_`, companion identities, and authority `AEAT`. No test fake, mock, stub, patch, monkeypatch, skip, xfail, mirrored business logic, or tautological assertion was introduced.

The correct documentation wordmark from the mixed commit is preserved: `docs/_templates/page.html` is byte-identical between the mixed commit and S90, with SHA-256 `1899458255db6591954e635a7f93aedbe6d3d641ebdc263ee8dd08064cb9f473`, contains the `CADRUMO` header lockup, and parses as valid Jinja. S90 itself changes no locale catalogue, naming-rule source or generated rule, or documentation-template file. All four mixed-commit locale blobs and the generated product-authority rule remain byte-identical through S90, and rule synchronization reports no missing, drifted, stale, warning, or error entries.

The target plan Git blob is `24be6fd6c436559853b194fde5bd3a0703f2684b` and remains byte-identical through the current audit HEAD. Vaultspec query parses S05, S86, S62-S66, S25, S67, and S89 as open and S90 as closed. The S89 row remains open with SHA-256 `1b0d257a2a34f1389995a87bcc69de60f0b2dff2fd66be08f70467c586facc69`; its scaffolded execution record predates the S90 commit and carries the same action and scope, corroborating the recorded cross-commit preservation. S90's record has valid frontmatter and is the only affected Step closed by the repair.

The current full parity failure is external to S90. Every catalogue in the target commit has the same 3,704 keys. Concurrent uncommitted S89 work leaves Catalan and Hungarian at 3,704 keys but English and Spanish at 3,702, specifically missing `cli.config.bucket` and `cli.config.unlock`; the untracked S89 execution record also predates S90. Thus the failure attribution is proven while the numerical pass count remains the LOW record defect above.

## Recommendations

- Resume S89; S90 introduces no blocking authority or overlap defect.
- Correct the S90 full-parity count from 31 passed to 26 passed while retaining the accurate S89-external failure attribution.
- Address the pre-existing `test_parity.py` formatting drift and plan annotation/order warnings only in dedicated hygiene work.
