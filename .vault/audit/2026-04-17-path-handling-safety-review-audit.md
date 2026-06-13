---
tags:
  - "#audit"
  - "#path-handling-safety"
date: "2026-04-17"
modified: '2026-04-17'
related:
  - "[[2026-04-16-google-workspace-mcp-auth-review-audit]]"
  - "[[2026-04-16-google-workspace-mcp-auth-reference]]"
---

# `path-handling-safety` Code Review

PATH-001 | HIGH | `aeat sync` exposes directory traversal through raw `record_id` path joins
`src/aeat/application/sync/_divergence.py:216` allows any non-empty `record_id`, `src/aeat/application/sync/_repository.py:70` turns that string into `self._root / f"{record_id}.json"` without normalization or containment checks, and the CLI passes operator input straight through in `src/aeat/entrypoints/cli/sync/show.py:21` and `src/aeat/entrypoints/cli/sync/resolve.py:50`. A crafted `record_id` containing separators or `..` can escape `AEAT_SYNC_DIVERGENCE_FILE_DIR` and target arbitrary sibling paths for reads, and resolution flows can persist back to an unintended location when the loaded JSON validates as a `DivergenceRecord`.

PATH-002 | MEDIUM | Manuals corpus loaders trust persisted relative paths without root containment
`src/aeat/domain/manuals/_schema.py:209` and `src/aeat/domain/manuals/_schema.py:290` accept free-form strings for `SectionRef.relative_path` and `FetchedManualPart.relative_pdf_path`. Those values are then joined directly against the part root in `src/aeat/domain/manuals/_loader.py:191` and `src/aeat/domain/manuals/_fetch.py:236` with no `resolve()` + `relative_to()` style containment check. A malformed or tampered corpus record can therefore walk outside the intended manual part root and cause reads against arbitrary files reachable by the process.

PATH-003 | LOW | Service-account path resolution is inconsistent across launch surfaces and still depends on process cwd
The MCP shim normalizes service-account paths against `PROJECT_ROOT` in `src/aeat/entrypoints/mcp/launch_google_workspace.py:50-53`, but the general auth and doctor flows still consult `Path(sa_path)` directly in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py:236` and `src/aeat/entrypoints/cli/doctor.py:568-576`. When `GOOGLE_APPLICATION_CREDENTIALS` is configured as a relative path, different entry points can read different files depending on the current working directory, which is a path-confusion risk and makes credential handling less predictable than the hardened MCP path.

PATH-004 | HIGH | Relative paths from `env/.env` are still interpreted against process cwd across multiple write-capable subsystems
`src/aeat/config.py:105`, `src/aeat/config.py:211`, `src/aeat/config.py:409`, and `src/aeat/config.py:469` expose path-valued settings as raw `Path` objects, and a direct isolated load confirms repo-style values like `.tokens`, `corpus/manuals`, and `var/divergences` remain non-absolute. Runtime consumers then use those values directly for writes in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py:247`, `src/aeat/status/_reader.py:68`, `src/aeat/domain/manuals/_loader.py:56`, and `src/aeat/entrypoints/cli/sync/show.py:19` / `src/aeat/entrypoints/cli/sync/resolve.py:48`. Running the same project from a different cwd can therefore relocate OAuth tokens, caches, divergence records, and other persisted artifacts outside the intended repo-local gitignored tree.

PATH-005 | HIGH | The raw-ID-to-path bug class repeats in submission, amendment, and workflow read paths
`src/aeat/adapters/outbound/aeat/export/_engine.py:278` reads `settings.aeat_submissions_dir / f"{submission_id}.json"` and the operator-facing CLI passes user input straight through in `src/aeat/entrypoints/cli/submission/show.py:17`. `src/aeat/application/filing/_complementaria.py:113-115` does the same for `amendment_id`, which is then used by `aeat filing complementaria submit`. `src/aeat/application/workflow/_persistence.py:51` similarly reads `runs_dir / f"{run_id}.json"` and is exposed by `src/aeat/entrypoints/cli/workflow/show.py:32`. None of these IDs are path-constrained at the load boundary, so crafted values containing separators or `..` can escape the intended persistence roots and turn the show/load commands into arbitrary local JSON read gadgets.

PATH-006 | LOW | The affected path boundaries have no traversal-focused regression coverage
The current tests cover happy-path round trips but do not assert rejection of separators, `..`, or root escapes. Representative examples are `src/aeat/application/sync/test_repository.py`, `src/aeat/application/workflow/test_persistence.py`, `src/aeat/adapters/outbound/aeat/export/test_engine.py`, and `src/aeat/domain/manuals/test_loader.py`, all of which exercise valid ids/relative paths only. That leaves the current path-safety findings easy to reintroduce after they are fixed unless explicit negative tests are added.

## Rolling Review Update | 2026-04-17

PATH-001 | RESOLVED
`src/aeat/core/paths.py` now centralizes `resolve_record_json_path()` with token validation plus root containment, and the sync repository consumes it in `src/aeat/application/sync/_repository.py`. Regression coverage was added in `src/aeat/application/sync/test_repository.py` for traversal attempts on both load and save.

PATH-002 | RESOLVED
The manuals schema now rejects non-contained POSIX relative paths at validation time in `src/aeat/domain/manuals/_schema.py`, and the runtime loaders re-check containment with `resolve_relative_subpath()` in `src/aeat/domain/manuals/_loader.py` and `src/aeat/domain/manuals/_fetch.py`. Regression coverage landed in `src/aeat/domain/manuals/test_loader.py` and `src/aeat/domain/manuals/test_fetch.py`.

PATH-003 | RESOLVED
The cwd-dependent service-account inconsistency is closed by settings normalization in `src/aeat/config.py`: both `google_application_credentials` and `google_oauth_client_json` are now anchored to `PROJECT_ROOT` when loaded from env. Existing consumers in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py`, `src/aeat/entrypoints/cli/doctor.py`, and the MCP shim therefore converge on the same absolute path even when launched from different working directories.

PATH-004 | RESOLVED
Repo-relative `Path` settings are now normalized against `PROJECT_ROOT` in `src/aeat/config.py`, which closes cwd-dependent drift for token caches, divergence records, corpus roots, drafts, workflow runs, inbox artifacts, and related writeable directories. Relative SQLite URLs are separately normalized in `src/aeat/adapters/persistence/storage/engine.py`, with regression coverage in `src/aeat/adapters/persistence/storage/_test_engine.py` proving the database file anchors to `PROJECT_ROOT` instead of the process cwd.

PATH-005 | RESOLVED
The raw-id-to-path bug class is removed from submission, amendment, and workflow persistence boundaries by routing them through `resolve_record_json_path()` in `src/aeat/adapters/outbound/aeat/export/_engine.py`, `src/aeat/application/filing/_complementaria.py`, and `src/aeat/application/workflow/_persistence.py`. Regression coverage was added in `src/aeat/adapters/outbound/aeat/export/test_engine.py`, `src/aeat/application/filing/test_complementaria.py`, and `src/aeat/application/workflow/test_persistence.py`.

PATH-006 | RESOLVED
Traversal-focused regression tests now cover config path anchoring, sync divergence ids, submission ids, amendment ids, workflow run ids, manuals section refs, manuals PDF refs, and relative SQLite URLs. The targeted verification command passed cleanly:

`uv run pytest tests/test_config.py src/aeat/application/sync/test_repository.py src/aeat/application/workflow/test_persistence.py src/aeat/adapters/outbound/aeat/export/test_engine.py src/aeat/application/filing/test_complementaria.py src/aeat/domain/manuals/test_loader.py src/aeat/domain/manuals/test_fetch.py src/aeat/adapters/persistence/storage/_test_engine.py`

## Adjacency Sweep | 2026-04-17

Post-fix grep and lint review found no remaining production call sites that materialize `record_id`, `submission_id`, `amendment_id`, or `run_id` directly into `<root>/<id>.json` paths outside `src/aeat/core/paths.py`, which is the intended guardrail boundary. Remaining `f"{run_id}.json"` hits are test-only (`src/aeat/entrypoints/cli/workflow/test_cli.py`).

The remaining `relative_path` / `relative_pdf_path` occurrences are schema definitions, validated fixture data, and the hardened loader/fetch call sites in `src/aeat/domain/manuals/_loader.py` and `src/aeat/domain/manuals/_fetch.py`.

Service-account path references outside config are limited to normalized-settings consumers (`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py`, `src/aeat/entrypoints/cli/doctor.py`, `src/aeat/entrypoints/mcp/launch_google_workspace.py`, and related tests). No additional unresolved path-handling findings were identified in the audited critical-path surfaces.
