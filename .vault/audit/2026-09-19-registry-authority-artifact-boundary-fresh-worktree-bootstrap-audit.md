---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-19'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:d8f851b79cf3d5e4f384d8206479145842613080e3a1c511428ff349c77f10a8'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---
# `registry-authority-artifact-boundary` audit: `fresh worktree bootstrap`

## Scope

Reviewed the source-tree build bootstrap and complete worktree initialization path after `W03.P08.S138`, against the accepted indexed-storage boundary and the amended Justfile provisioning decision. The review traced a missing repo-root publication through editable build, descriptor-selected packaging, `just init`, final canonical republication, and exact runtime loading.

## Findings

### fresh-worktree-bootstrap | low | No unresolved bootstrap or packaging defect

The build hook invokes the canonical compiler only for a real source tree whose default `.authority/` is absent. An explicit missing override still fails closed, and an sdist rebuild consumes its embedded descriptor/database pair without reaching development tooling. The isolated dependency closure reproduced complete publication, plain `uv sync` created the default repo-root authority, and the packaged/runtime boundary tests passed.

### complete-init | low | The provisioning facade preserves established owners

`just init` delegates locked Python synchronization and default Vaultspec installation to `dev.init`, delegates RAG provisioning to its official installer, and delegates final authority compilation to the canonical publisher. It adds no alternate compiler, RAG lifecycle alias, or runtime source fallback. The real command completed and the exact runtime-load check admitted 58 modelos and 146 revisions.

### fresh-runner-source-detection | medium | Clean-tree reproduction isolated the failure to the explicit override arm

The first CI failure looked like duplicated source-shape inference in `_authority_root`. Removing that inference made a Git-archive `uv sync --locked` publish successfully, but the second CI run still refused before compilation. That proved the self-hosted runner was taking the earlier explicit-override arm. The broader hook change was reverted so malformed sdists retain their precise fail-closed behavior.

### self-hosted-runner-authority-override | medium | Resolved CI contamination without weakening operator refusal

The shared setup action now clears `CADRUMO_AUTHORITY_ROOT` only for clean-checkout initialization, which deliberately exercises the packaged-default posture. Product and developer invocations retain the required contract: a non-empty explicit override that does not exist fails. Actionlint, focused build-hook tests, Ruff, and ty pass after the correction.

Result: PASS. Both medium findings are resolved; no critical, high, or actionable finding remains.

## Recommendations

None.
