---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-19'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:a0ea9e0a60a216f72080901ea1ee4333857983663a0ffca1a558c92829277d89'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---
# `registry-authority-artifact-boundary` audit: `fresh worktree bootstrap`

## Scope

Reviewed the source-tree build bootstrap and complete worktree initialization path after `W03.P08.S138`, against the accepted indexed-storage boundary and the amended Justfile provisioning decision. The review traced a missing repo-root publication through editable build, descriptor-selected packaging, `just init`, final canonical republication, and exact runtime loading.

## Findings

### fresh-worktree-bootstrap | low | No unresolved bootstrap or packaging defect

The build hook invokes the canonical compiler only when an explicit override, the default source publication, and an embedded sdist publication have all been excluded. An explicit missing override still fails closed, and an sdist rebuild consumes its embedded descriptor/database pair without reaching development tooling. Selection remains descriptor-driven and runtime never generates authority.

### complete-init | low | The provisioning facade preserves established owners

`just init` delegates locked Python synchronization and default Vaultspec installation to `dev.init`, delegates RAG provisioning to its official installer, and delegates final authority compilation to the canonical publisher. It adds no alternate compiler, RAG lifecycle alias, or runtime source fallback. The real command completed and the exact runtime-load check admitted 58 modelos and 146 revisions.

### source-shape-inference | medium | Resolved non-portable precondition before canonical compilation

Fresh Linux CI showed that checking selected authoring paths to re-prove a source checkout could return false before the compiler was invoked. Those checks duplicated knowledge the control flow already established. The explicit override and embedded-sdist arms return earlier; after both are absent, the canonical compiler is now the authority on whether the source inputs are coherent. A Git-archive `uv sync --locked` with no generated authority passed this exact path.

### self-hosted-runner-authority-posture | low | CI clean checkout explicitly selects the default arm

The shared setup action clears `CADRUMO_AUTHORITY_ROOT` only for clean-checkout initialization, preventing a self-hosted runner service environment from changing which build posture CI exercises. Product and developer invocations retain the required contract: a non-empty explicit override that does not exist fails. Actionlint, focused build-hook tests, Ruff, and ty pass.

Result: PASS. The medium finding is resolved; no critical, high, or actionable finding remains.

## Recommendations

None.
