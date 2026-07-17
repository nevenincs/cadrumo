---
tags:
  - '#exec'
  - '#release-readiness-gate'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-07-04-release-readiness-gate-plan]]"
---

# Implement the release audit-state gate, RC-soak procedure, and rollback procedure per GH issue #415

## Scope

- `dev/release/readiness.py`
- `dev/release/tests/test_readiness.py`
- `docs/_release_checklist.yaml`
- `docs/_release_notes_template.md`
- `justfile`
- `RELEASING.md`
- `src/aeat/tests/test_release_config.py`

## Description

- Read GH issue #415 and the prior triage comment confirming the premise as genuinely unbuilt.
- Grounded in the existing release surface: `justfile` release recipes, `RELEASING.md`, `release-please-config.json`, `.release-please-manifest.json`, the release-please ADR, `.github/workflows/publish.yml` (human-gated Trusted Publishing).
- Implemented `dev/release/readiness.py`: a read-only audit-state gate with four checks (version-surface parity, changelog sanity, no open `priority:P0-blocker` GitHub issue via `gh`, most recent packaging-smoke evidence), each carrying a `blocking` or `advisory` severity.
- Wrote 17 real-behavior tests in `dev/release/tests/test_readiness.py` exercising real files on `tmp_path`, a real subprocess call to a real explicit-path stub `gh` executable, and one sanity check against the actual repository.
- Authored `docs/_release_checklist.yaml` (machine-validated RC-soak window, versioning discipline, hotfix cycle times, rollback triggers) and `docs/_release_notes_template.md`.
- Extended `src/aeat/tests/test_release_config.py` with strict pydantic models parsing the new checklist YAML, plus 3 new tests (8 total in the file).
- Wired `just release-readiness` / `release-readiness-json` and a print-only `just release-rollback <version>`; made `just release-apply` run the gate first and refuse on a blocking failure.
- Documented the RC-soak procedure and the rollback procedure in `RELEASING.md`.
- Added per-file-ignores for the new modules' `S603` subprocess calls to `pyproject.toml`.
- Ran ruff check/format, `ty check`, and `pyright` against every touched file (all clean); ran a `src/aeat` collection-only sweep (clean except a pre-existing, unrelated `pywintypes` import error in `src/aeat/entrypoints/mcp/tests`, out of this Step's ownership boundary).

## Outcome

25 tests pass (`dev/release/tests` + `src/aeat/tests/test_release_config.py`). Confirmed the gate is live, not a stub: `just release-readiness` run against the real repository correctly reports BLOCKED because issue #116 (Live-AEAT-write safety charter) is a genuinely open `priority:P0-blocker`. No outward release action (tag, push, publish, PyPI yank) was performed by any new surface at any point; `release-rollback` only prints. Landed as commit `1045fea117` on `chore/eliminate-shims` via explicit pathspec (9 files).

## Notes

- Discovered mid-implementation that Windows `subprocess.run(["gh", ...])` with a PATH-prepended stub `.bat` silently resolves the REAL `gh.exe` instead (CreateProcess does not apply the same PATHEXT search `shutil.which` uses without `shell=True`). Fixed by adding an explicit `gh_executable` parameter to `check_no_open_release_blockers` so tests pass a resolved path directly, bypassing PATH-search semantics entirely (still a real subprocess call to a real executable, no mocking).
- `pyproject.toml` was concurrently modified in the shared worktree by an unrelated peer ruff-cleanup commit (`d99c3d6100`) that swept up my uncommitted per-file-ignore additions alongside its own changes before I committed. The content is correct and unaffected; only the commit attribution differs from what I intended. Did not revert or otherwise touch that peer commit.
- Deliberately did not build a real `aeat-cli-beta` PyPI project or an automated rollback executor: `aeat-cli` has not shipped a first stable PyPI release, so a hosted beta channel and automated rollback execution would be infrastructure with no real release to exercise against, and automating any of it would risk violating the project's absolute no-outward-release-action safety mandate. See the ADR's Rationale/Consequences for the explicit deferral.
- The GH issue-blocker check is best-effort/advisory when `gh` is unavailable or the network is unreachable; only a genuine open `priority:P0-blocker` issue is a hard release blocker.
