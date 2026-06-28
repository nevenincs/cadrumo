---
tags:
  - '#audit'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
  - '[[2026-05-21-secure-object-database-drift-research]]'
  - '[[2026-05-22-secure-object-integrity-p05-s15-review-audit]]'
  - '[[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]'
  - '[[2026-05-14-cli-workflow-redesign-integrity-warning-stability-adr]]'
---



# `secure-object-integrity-P05-S16` Code Review

P05S16-001 | HIGH | Blind quarantine remains available for active-profile unreadable tax evidence
The secure-object integrity plan makes this wave read-only attribution first and explicitly says the repair surface must explain corrupted state without blindly quarantining tax evidence. The implementation correctly routes integrity findings toward `repair list` and `integrity attribution`, but the existing `repair quarantine --yes` path remains a live destructive path: `src/aeat/entrypoints/cli/_config/__init__.py` calls `quarantine_unreadable_secure_objects()` after only the `--yes` check, and `src/aeat/application/diagnostics.py` moves every undecryptable secure-object row into `secure_objects_quarantine` and deletes it from active `secure_objects`. There is no namespace risk gate, attribution report requirement, replacement-evidence requirement, preserve-first decision record, or special block for critical filing/submission/receipt namespaces. This is a safety blocker for plan closeout because the final cluster leaves an operator one flag away from removing active tax evidence from application state before the attribution/remediation ladder exists.

P05S16-002 | HIGH | Unreadable-row origin attribution is still a placeholder, not an attribution signal
The plan objective requires the operator to see whether unreadable rows likely match test contamination or another storage-routing fault. The implementation exposes `likely_origin` and `origin_confidence`, but `src/aeat/application/repair_integrity.py` hardcodes every unreadable row to `likely_origin="undetermined"` and `origin_confidence="not_evaluated"`. The tests in `src/aeat/application/test_repair_integrity.py` assert those placeholder values rather than proving any real attribution branch. This means the command can group by namespace and safe key context, but it does not meet the stated attribution intent for identifying test-key contamination, stale migration residue, active-profile evidence, or storage-routing faults. It also weakens the safety story around P05S16-001 because the operator still cannot separate likely disposable contamination from preserve-first evidence.

P05S16-003 | HIGH | Verification surface codifies pytest monkeypatch isolation despite the local no-monkeypatch rule
The local execution notes and quality gates prohibit fakes, mocks, patches, monkeypatches, skips, and xfails as shortcuts for passing tests. This final cluster reintroduces and then blesses monkeypatch-based environment mutation as the accepted secure-SQL isolation pattern: `src/aeat/entrypoints/cli/test_repair_privacy_contract.py` uses an autouse `monkeypatch.setenv("AEAT_DATABASE_URL", ...)` fixture; `src/aeat/tests/secure_sql.py` requires `pytest.MonkeyPatch` and calls `monkeypatch.setenv`; `src/aeat/tests/test_secure_sql.py` exercises that helper; and `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py` treats an autouse fixture that calls `setenv` as sufficient hygiene. The public privacy tests exercise useful real CLI behavior, but the verification method is not compliant with the repository's stated test policy and repeats the same class of issue earlier S08 review had to remove. The gate matrix therefore is not sufficient for final closure until the isolation pattern is expressed through real settings construction, subprocess environment setup, or another non-monkeypatch route.

P05S16-004 | LOW | Locale/process evidence is acceptable for the secure-object attribution command
Reviewed the scoped locale changes for `cli.config.repair.integrity_attribution_help` in `src/aeat/locales/en.yml`, `es.yml`, `ca.yml`, and `hu.yml`, plus the P05.S14/P05.S15 execution records. The command help exists across all four catalogues and describes safe metadata grouping of undecryptable secure-object rows. The recorded `aeat.locales audit` and `scaffold --check` gates are sufficient for this command. Existing registry-source scaffold self-reference values remain catalogue cleanup debt outside the secure-object attribution command and are not escalated here because I did not find direct secure-object impact.

## Resolution re-review - 2026-05-22

P05S16-RR-001 | RESOLVED | No CRITICAL/HIGH blockers remain after S16 HIGH remediation re-review
Re-reviewed the three prior HIGH findings against the remediated implementation and focused gates. I found no CRITICAL or HIGH blocker remaining for S16 closeout. The active repair surface is now preserve-first, unreadable-row origin attribution is derived from safe namespace/context metadata rather than placeholders, and the touched secure-SQL isolation helper/tests no longer rely on pytest monkeypatch as the accepted clean pattern.

P05S16-RR-002 | RESOLVED | P05S16-001 blind quarantine blocker is closed
`src/aeat/entrypoints/cli/_config/__init__.py` now refuses non-dry-run active-profile quarantine with `cli.config.repair.quarantine_preserve_first_refused` before invoking any destructive archive/delete behavior. `src/aeat/application/diagnostics.py` also fail-closes `quarantine_unreadable_secure_objects()` by raising under the preserve-first policy, leaving `preview_quarantine_unreadable_secure_objects()` as the read-only path. The real-behavior coverage in `src/aeat/application/test_diagnostics.py` proves the application entrypoint leaves all secure-object rows in place and creates no quarantine archive table, while `src/aeat/entrypoints/cli/test_repair_privacy_contract.py` proves `config repair quarantine --yes` refuses and the attribution report remains available without payload/taxpayer disclosure.

P05S16-RR-003 | RESOLVED | P05S16-002 origin attribution placeholder blocker is closed
`src/aeat/application/repair_integrity.py` now fills `likely_origin` and `origin_confidence` through `_repair_origin_attribution()` using only safe metadata: namespace classification, active-key digest match, bucket-context availability, unrecoverable HMAC context, and test namespace markers. The focused tests in `src/aeat/application/test_repair_integrity.py` cover repository keychain/restore mismatch, tax-evidence keychain/restore mismatch, test namespace residue, unregistered namespace/storage-routing fault, and missing active-profile bucket context. The implementation no longer hardcodes all unreadable rows to `undetermined` / `not_evaluated`.

P05S16-RR-004 | RESOLVED | P05S16-003 monkeypatch isolation blocker is closed for the touched secure-SQL surface
`src/aeat/tests/secure_sql.py` and `src/aeat/entrypoints/cli/test_repair_privacy_contract.py` now isolate `AEAT_DATABASE_URL` with direct `os.environ` save/restore and dispose the SQL engine before and after the isolated scope. `src/aeat/tests/test_secure_sql.py` verifies the helper routes the default engine to the temporary SQLite database and restores the active bucket session afterward. `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py` now recognizes direct `os.environ["AEAT_DATABASE_URL"] = "sqlite:///{tmp_path...}"` assignment as the clean autouse isolation signal and keeps existing non-clean file-level exceptions in an explicit P02.S06 backlog classification rather than treating monkeypatch-based isolation as clean.

P05S16-RR-005 | RESOLVED | Locale refusal key and verification evidence are acceptable
The new `cli.config.repair.quarantine_preserve_first_refused` key exists in `src/aeat/locales/en.yml`, `es.yml`, `ca.yml`, and `hu.yml`, and the existing `cli.config.repair.quarantine_help` text now signals that active quarantine is disabled by the preserve-first repair policy. Local re-review gates passed: `uv run ruff check` on the scoped remediation files; `uv run python -m aeat.locales audit`; `uv run python -m aeat.locales scaffold --check`; locale parity/honesty tests, 6 passed; focused diagnostics/repair/privacy/secure-SQL/hygiene tests, 69 passed; registry referential-integrity tests, 49 passed; and `uv run aeat --format json app registry verify` returned `"verified": true`.
