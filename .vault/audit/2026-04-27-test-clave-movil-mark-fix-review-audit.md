---
tags:
  - '#audit'
  - '#test-clave-movil-mark-fix'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - '[[2026-04-27-test-clave-movil-mark-fix-plan]]'
  - '[[2026-04-27-test-clave-movil-mark-fix-adr]]'
---

# `test-clave-movil-mark-fix` Code Review

No findings recorded yet. Formal review runs after verification commands complete.

LOCK-001 | HIGH | Remove unrelated `vaultspec-rag` lockfile upgrade
`uv.lock:3083` upgrades `vaultspec-rag` from `0.2.3` to `0.2.4`, and `uv.lock:3088` adds `packaging` to that package's resolved dependencies. The research, ADR, plan, and execution summary describe a marker-only test change plus vault records; they do not justify a dependency-resolution change. This expands the merge surface for issue 436 and should be reverted or explicitly justified before merge. Status: REVISION REQUIRED.

Review verification notes: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` carries module-level `live_read` and `domain_aeat_remote` markers, the autouse fixture has a return type and docstring, and targeted searches found no stale `--ignore=src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` references in `justfile`, `.github/workflows`, `docs`, `tests/README.md`, or `.vaultspec/rules`. Source-only default collection reported 14 deselected tests, explicit `live_read` selection with `AEAT_LIVE_TESTS_ENABLED=0` skipped all 14 tests, and explicit `AEAT_LIVE_TESTS_ENABLED=1` ran all 14 tests successfully. No production provider or submission files are changed.

AUTH-001 | CRITICAL | Prior verification did not prove real AEAT Cl@ve authentication
Correction to the verification note above: the `AEAT_LIVE_TESTS_ENABLED=1` run exercised the module's injected hand-written browser-session stand-ins, not a real AEAT/Cl@ve authenticated browser session. No operator approval occurred, and AEAT remained unauthenticated. Therefore the test run must not be interpreted as live-auth success. The current module is live-marked but still bypasses the real remote authentication boundary through local stand-ins, which conflicts with the requested safety invariant that live tests prove the actual Cl@ve path or skip until the operator explicitly authenticates. Status: FAIL.

LOCK-001 resolution: reverted the `uv.lock` delta so the dependency graph remains unchanged for issue 436. Status: RESOLVED.

AUTH-001 resolution: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` is now documented and marked as a protocol-level unit test module, not a live-auth proof. The module no longer imports the live-test gate and no longer claims `AEAT_LIVE_TESTS_ENABLED` execution proves real AEAT/Cl@ve authentication. Status: RESOLVED.

WRITE-001 | CRITICAL | Removed Cl@ve representation auto-submit
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_clave_movil.py` still contained an automatic `DialogoRepresentacion` handler that clicked `form#repForm button[type=submit]` after Cl@ve approval. Even though this was representation/session dispatch rather than a filing submission, it was still an AEAT remote form submission performed without an explicit operator action in the code path. The helper has been deleted; the provider now raises when AEAT requests representation selection, and `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` asserts no click is fired. Status: RESOLVED.

DOC-001 | HIGH | Corrected stale slug vault artifacts
The research, ADR, and plan for this slug still encoded the rejected claim that the stand-in Cl@ve tests should be treated as live-auth tests. Those artifacts now state the corrected boundary: the tests are protocol-level unit tests, AEAT remained unauthenticated during the earlier run, and automatic representation form submission is forbidden. Status: RESOLVED.

DOC-002 | HIGH | Removed stale root README live-submit guidance
`README.md` still claimed filings were submitted dry-run by default and that real submission was available behind an explicit confirmation. That guidance contradicted the permanent no-submit policy and could mislead an operator into looking for a removed write path. The README now states that the project exports and verifies local filing files only, Kent uploads manually through AEAT, and live AEAT submission is permanently forbidden. Status: RESOLVED.

SCRIPT-001 | HIGH | Deleted executable recon helper that drove a hidden AEAT POST
`scripts/recon_modelo_100_detail.py` was a standalone executable helper that clicked a Modelo 100 expediente anchor whose `lanzarTewvForm` handler submitted a hidden POST form. Even though the intent was discovery of an already-submitted filing detail page, the script preserved a browser-driven AEAT form-submission surface outside the guarded product code. The script has been deleted. Status: RESOLVED.

SCRIPT-002 | MEDIUM | Deleted legacy live-AEAT recon capture scripts
`scripts/recon_modelo_100.py`, `scripts/recon_modelo_303.py`, and `scripts/recon_notifications.py` were undocumented one-shot discovery entry points that reused cached AEAT sessions and dumped authenticated HTML/screenshots/network traces under `scratch/`. They were not live-submit paths, but they kept stale executable live-site capture surfaces outside the guarded `aeat.adapters.outbound.aeat.sede` package. The scripts have been deleted; current read-side discovery belongs in the typed, tested sede readers. Status: RESOLVED.

DOC-003 | MEDIUM | Corrected stale scripts live-test marker wording
`scripts/README.md` still referred to the old `@pytest.mark.live` tier while the repository marker taxonomy is `live_read` / `live_write`. The wording now uses `@pytest.mark.live_read`, reducing stale marker guidance during live-test setup. Status: RESOLVED.

DOC-004 | MEDIUM | Corrected stale live marker guidance in CI and fixture docs
`README.md`, `.github/workflows/ci.yml`, and `scripts/_fixture_catalogue.py` still referred to the removed `pytest -m live`, `AEAT_LIVE_TESTS`, or `@pytest.mark.live` vocabulary. These have been corrected to `unit or live_read`, `AEAT_LIVE_TESTS_ENABLED`, and `@pytest.mark.live_read`. Status: RESOLVED.

PR-001 | HIGH | Pull request and Gemini review state were not yet established
GitHub checks on 2026-04-28 found no pull request for issue `#436`, no pull request for branch `bug/436-test-clave-movil-mark-fix`, and no pull request search hit for `test_clave_movil`. The remote branch exists at the same commit as local `HEAD`, but the safety-remediation worktree is still uncommitted, so there is no current PR surface for Gemini or other reviewers to inspect. Status: OPEN.

PR-001 resolution: PR `#450` was opened from `bug/436-test-clave-movil-mark-fix` against `main` after commit `0ae9cfc`. Status: RESOLVED.

PR-002 | INFO | Gemini and PR review findings checked on PR `#450`
GitHub review-thread, review, and comment queries for PR `#450` returned no review threads, no submitted reviews, and no comments. Gemini had not posted any findings at the time of this audit check. GitHub CI was running for `ubuntu-latest / Python 3.13` and `windows-latest / Python 3.13`. Status: OBSERVED.

GEMINI-001 | MEDIUM | Workflow adapter reached into `SubmissionEngine._preflight`
Gemini review on PR `#450` flagged that `SubmissionEngineAdapter.preflight()` was calling the private `SubmissionEngine._preflight.check(...)` attribute even though `SubmissionEngine` now exposes public `preflight(...)`. The adapter now delegates to `self._engine.preflight(draft, today=today)`, preserving the read-only preflight boundary while respecting subpackage API discipline. Status: RESOLVED.

PR-003 | INFO | PR `#450` CI and Gemini thread status rechecked after remediation
After commit `6db5d26`, PR `#450` CI passed on both `ubuntu-latest / Python 3.13` and `windows-latest / Python 3.13`. The Gemini review thread for `GEMINI-001` was resolved through GitHub's review-thread API. Status: OBSERVED.
