---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-19'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:20b9b0d146f39399ee322bde89f76a5ef4242aef7cb1ad1622d3176c6d077e12'
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

### source-bootstrap-postcondition | medium | Resolved redundant filesystem inference around canonical publication

Fresh Linux CI proved two duplicated filesystem observations were unsafe around canonical publication: source-shape checks could prevent compiler entry, and a post-publication `is_dir()` probe could discard a successful publisher return on the self-hosted workspace filesystem. The explicit override and embedded-sdist arms already return earlier. The remaining arm now returns the canonical publisher's destination directly, after which `_selected_pair` validates the descriptor and exact database bytes. A Git-archive `uv sync --locked` with no generated authority passed the publication path.

### self-hosted-runner-authority-posture | low | CI clean checkout explicitly selects the default arm

The shared setup action clears `CADRUMO_AUTHORITY_ROOT` only for clean-checkout initialization, preventing a self-hosted runner service environment from changing which build posture CI exercises. Product and developer invocations retain the required contract: a non-empty explicit override that does not exist fails. Actionlint, focused build-hook tests, Ruff, and ty pass.

Result: PASS. The medium finding is resolved; no critical, high, or actionable finding remains.

## Recommendations

None.
