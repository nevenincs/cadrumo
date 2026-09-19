---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:254797c12c641a0385108ea70ec833290a781154aacbccb23d02eeac5af1e2ef'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` audit: `S11 independent post review`

## Scope

Independent review of commit `7834c289ac`, the later plan/index reconciliation in commit `a1f1c85038`, and the current closure-outcome tests. The review checked the S11 action against the accepted closure decision, filesystem descriptor verification, test realism, mutation bites, and the execution/audit evidence.

## Findings

### s11-outcome-mutation-proof | high | S11 has no real composed mutation proof for every claimed closure outcome

The S11 commit changes only `test_source_connectivity_authority_contract.py`: it replaces an `os.open` patch with an in-repository symlink substitution. The current stale-evidence coverage genuinely mutates a loaded layout-source digest before calling the filing composer. By contrast, the complete and refused release cases in `dev/registry/conformance/tests/test_closure.py` construct `_temporal` and `_limb` fixtures directly, the below-filing-grade case merely observes a bundled registry fact, and the cross-limb case mutates a report-model coordinate rather than a report composed from the real three authorities. Those useful unit contracts do not meet S11's stated requirement to prove all five outcomes with mutation tests against composed authority output.

### s11-independent-review-attestation | high | The S11 audit cannot itself establish the claimed independent review

Commit `7834c289ac` creates the production-facing test change, the S11 execution record, and `2026-08-24-registry-completeness-closure-s11-source-connectivity-ratchet-audit` together. That audit records "Independent review" and "No findings" but contains neither a separate review commit nor evidence covering S11's five named outcome mutations. The later `a1f1c85038` index reconciliation lists S11 but does not add that missing evidence. The historical audit must not be relied on as the independent closeout for the broader checked plan row.

### s11-symlink-descriptor-bite | low | The narrowed symlink regression is real and fails closed on this worktree

The real substitution test passes on the Windows worktree with no mock, skip, xfail, or monkeypatch. The production verifier takes the Windows final-handle path and rejects it when it differs from the requested target. A separate in-process gate bite that disables `_same_filesystem_path` makes the same test fail by returning the replacement digest. Linux uses `O_NOFOLLOW` before the same final-path check; unsupported platforms fail closed when no stable descriptor path is available. The test therefore proves the security refusal it actually names, but it cannot prove the broader S11 closure-outcome claim.

## Recommendations

Add a successor plan Step that drives each of the five outcome categories through the real temporal, source-connectivity, filing-export, and closure-report composers, with mutation bites that fail if the relevant refusal or conjunction guard is weakened. Add a tracking-reconciliation Step that preserves the narrow symlink result while explicitly correcting the S11 record/audit reliance after the successor evidence has passed.
