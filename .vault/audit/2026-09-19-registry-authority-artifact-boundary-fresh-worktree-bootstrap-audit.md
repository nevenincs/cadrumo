---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-19'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:3d84f89b09d8a0687246a30c6b612263c1c89daf048102f29656e49e0c4dd92f'
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

### fresh-runner-source-detection | medium | Resolved duplicated source-shape inference that blocked CI bootstrap

Fresh Linux CI showed the editable-build hook could reach its missing-authority refusal before publication because `_authority_root` duplicated assumptions about which authoring paths prove a source checkout. The correction makes the already-selected control flow authoritative: an explicit override and an embedded sdist return earlier; otherwise absence of the default source publication invokes the canonical compiler directly. Focused build-hook and staging tests, Ruff, and ty pass after the correction.

Result: PASS. The medium finding is resolved; no critical, high, or actionable finding remains.

## Recommendations

None.
