---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-19'
modified: '2026-09-20'
body_schema: 'body-v2'
body_hash: 'sha256:a58f76a597e0b93f20a19c2ab7c781cca898e5fa22cf61f19219e5357e84a920'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---
# `registry-authority-artifact-boundary` audit: `fresh worktree bootstrap`

## Scope

Reviewed the source-tree build bootstrap and complete worktree initialization path after `W03.P08.S138`, against the accepted indexed-storage boundary and the amended Justfile provisioning decision. The review traced a missing repo-root publication through editable build, descriptor-selected packaging, `just init`, final canonical republication, and exact runtime loading.

## Findings

### fresh-worktree-bootstrap | low | No unresolved bootstrap or packaging defect

The build hook invokes the canonical compiler only when an explicit override, the default source publication, and an embedded sdist publication have all been excluded. An explicit missing override raises at its exact cause, and an sdist rebuild consumes its embedded descriptor/database pair without reaching development tooling. Selection remains descriptor-driven and runtime never generates authority.

### complete-init | low | The provisioning facade preserves established owners

`just init` delegates locked Python synchronization and default Vaultspec installation to `dev.init`, delegates RAG provisioning to its official installer, and delegates final authority compilation to the canonical publisher. It adds no alternate compiler, RAG lifecycle alias, or runtime source fallback. The real command completed and the exact runtime-load check admitted 58 modelos and 146 revisions.

### synthetic-default-provenance | medium | Resolved internal default leaking into the explicit-override arm

Importing `dev._paths` deliberately seeds `CADRUMO_AUTHORITY_ROOT` with the checkout's `.authority` path for developer application processes. Fresh setup inherited that synthesized value into `uv sync`, where the build hook correctly classified it as an explicit dependency and refused its absence before it could provision the default. The sync subprocess now removes only a value resolving to the canonical checkout default; relocated operator values remain untouched and fail closed. The build resolver is total: every successful arm returns a path, while a missing explicit override raises directly.

### clean-linux-proof | low | Fresh setup and affected gates pass outside CI

A disposable Linux container started from a Git archive with no `.authority` or virtual environment. Locked `dev.env install` built the editable package and published the descriptor, Linux Ruff and formatting passed, ty, Pyrefly, and BasedPyright passed on changed production modules, 37 setup/packaging/storage/application tests passed, and all 99 CLI contract tests passed. CI setup also explicitly unsets any runner-service override before initialization so the job exercises the intended default posture.

Result: PASS. The medium finding is resolved; no critical, high, or actionable finding remains.

## Recommendations

None.
