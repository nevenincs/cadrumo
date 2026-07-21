---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S30'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Canonicalize active-profile labels to immutable bucket UUIDs at the WorkflowState and profile-health boundaries by composing the core precedence resolver with the existing manifest resolver without adding resolver authority, then prove a real lifecycle-repository-backed label override resolves its encrypted record and keeps a lower-priority dangling pointer ineligible until the override is cleared, after which the pointer becomes authoritative and repairable

## Scope

- `src/cadrumo/application/workflow/_models.py`
- `src/cadrumo/application/workflow/_profile_health.py`
- `src/cadrumo/application/workflow/tests/test_active_profile_resolution.py`

## Description

- Ground the active-profile call graph with fresh Vaultspec-RAG searches and exact symbol scans across core precedence, workflow manifests, health, secure repositories, and CLI normalization.
- Preserve `resolve_active_bucket_id` as the sole selector-precedence authority and `resolve_profile_bucket` as the sole live label-or-UUID authority.
- Canonicalize `WorkflowState` bucket and record access to the manifest UUID and hold that UUID in scoped settings while secure storage is addressed.
- Route profile-health selection through the core resolver, preserve the original env-versus-pointer source, and scope the canonical UUID across workflow and lifecycle repository reads.
- Canonicalize the best-effort provider retry so a label cannot reappear as a physical bucket route.
- Persist a real encrypted lifecycle record above a real dangling pointer and prove precedence, exact-byte non-mutation, health validation, and confirmed repair after the override is removed.
- Run focused, adjacent, CLI, tombstone, storage-route, Ruff, diff, and uncached import-graph verification in isolated frozen environments.

## Outcome

- Landed the production and integration implementation in `49bf0c4d48` after the amended plan scope in `09645dc1e0`.
- The focused workflow and adjacent health modules passed fifteen tests; the final S30 integration node passed again after its health-status expectation was aligned with the canonical validator.
- Five CLI label/UUID/unknown/ambiguity tests, four selected tombstone/stale-active tests, and ten core storage-route tests passed.
- Ruff and diff checks passed.
- The uncached import graph analyzed 3,422 files and 16,158 dependencies with five contracts kept and none broken.
- Independent pre-implementation architecture review and fresh-RAG formal post-diff review passed with no findings.
- No second selector, manifest resolver, storage route, or repair authority was introduced.

## Notes

- The shared `.venv` remained intentionally untouched after the earlier dependency-reconciliation incident; every Python-backed S30 command used `uv run --isolated --frozen`.
- An initial strengthened assertion expected the deliberately small profile record to be incomplete. The real validator classified it as ready, so the assertion was corrected to the observed production contract and the exact node was rerun successfully.
- One delegated author lane completed semantic grounding but made no edits before it was stopped; the supervisor implemented the reviewed three-file scope directly, and no peer work overlapped those files.
- Unknown, tombstoned, and ambiguous overrides never fall through to the lower pointer. Health retains the original source for repair eligibility while registered selectors are reported by canonical UUID.
- No data loss, skipped tests, persistent failures, or runtime scaffolds remain.
