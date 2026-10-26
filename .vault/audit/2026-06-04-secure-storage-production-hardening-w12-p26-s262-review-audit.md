---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:b57f7fb8d591a396a2726accc2bfad1e84a92f47e36366f54423a3ee99512fc6'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S262` Review

## S262-001 | MEDIUM | Package manifest omitted lazy-resolved domain records

The retired module resolved `UserProfileFact`, `UserProfileRecord`, and `UserProfileStatus` through its PEP 562 dispatcher while omitting them from `__all__`. That made the manifest-bucket surface inconsistent: direct attribute access worked, but wildcard/public manifest consumers could not discover the same profile-record contract.

Disposition: fixed. The missing names now appear in `__all__`, and a public-surface regression test resolves all four profile records against the real domain package.

## S262-002 | LOW | Typing-only projection import list lagged runtime dispatch

The `TYPE_CHECKING` projection import list omitted `record_to_path_values` even though the runtime dispatcher and `__all__` expose it. This was not a runtime persistence defect, but it weakened the manifest-discovery contract for static consumers.

Disposition: fixed.

## S262-003 | PASS | Lazy boundary remains intact

The package still avoids loading `aeat.domain.calculations.registry` during plain `import aeat.application.user_profile`, preserving the state-free CLI startup contract.

## S262-004 | OPEN | Cross-module gate has unrelated current regressions

The full cross-module gate remains red for unrelated current findings:

- the retired module imported two missing private names from `aeat.application.modelo._actions`.
- the retired module had one public sibling import missing from `__all__`.
- the retired module had two public sibling imports missing from `__all__`.

These were not introduced by S262 and should be tracked in a follow-up wave rather than normalized by increasing the ratchet baseline.

## S262-005 | PASS | Validation

- the historical check
- the historical check
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

Disposition: close `AFR-160`.
