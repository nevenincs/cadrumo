---
tags:
  - '#audit'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---



# `secure-object-integrity-P04-S13` Code Review

P04S13-001 | HIGH | Relational diagnostic still treats `secure_objects` as an expected relational table
`_relational_database_integrity_check_for_engine` builds `expected_table_map` from every table in `Base.metadata.sorted_tables`, which includes `secure_objects`. P04.S13 explicitly scopes the new diagnostic to relational SQL table and foreign-key integrity outside `secure_objects`, because secure-object decryptability and attribution are already handled by the dedicated secure-object diagnostics. As written, a database containing every non-secure relational table but no `secure_objects` table fails with `Relational database missing 1 table(s)` and detail `secure_objects`. The new missing-table test also asserts this behavior, so the regression suite locks in the scope violation instead of protecting the plan objective. This is a false positive on the P04.S13 clean-schema surface and duplicates remediation ownership between `relational_database.integrity` and `secure_objects.integrity`.

P04S13-002 | LOW | Focused review and gate notes
Reviewed `_relational_database_integrity_check_for_engine`, `_relational_schema_findings`, `_limited_schema_detail`, `_foreign_key_findings`, and the relational schema/foreign-key tests in `test_diagnostics.py` for privacy leakage, SQLite portability, diagnostic actionability, false positives, and test-policy compliance. Focused gate passed: `uv run pytest src/aeat/application/test_diagnostics.py -k "relational_database_integrity_check"`. Additional probe created all `Base.metadata` tables except `secure_objects` and confirmed the new relational diagnostic returns `fail` with detail `secure_objects`.

P04S13-003 | LOW | Re-review: prior HIGH resolved; no critical or high blockers remain
Re-reviewed the S13 fix after `_relational_database_integrity_check_for_engine` began excluding `_SECURE_OBJECT_TABLE_NAMES` from the expected relational table map. The missing-table regression now asserts a non-secure relational table absence through `corpus_artifacts` and asserts `secure_objects` is absent from the diagnostic detail. The added secure-object absence regression creates every metadata table except `secure_objects` and now returns `ok`, matching P04.S13's scope of relational SQL table and foreign-key integrity diagnostics outside `secure_objects`. Focused gates passed locally: `uv run ruff check src/aeat/application/diagnostics.py src/aeat/application/test_diagnostics.py`; `uv run pytest src/aeat/application/test_diagnostics.py -k "relational_database_integrity_check" -q`. No remaining critical or high blockers were found for privacy leaks, false positives on clean schema, SQLAlchemy/SQLite portability, diagnostic actionability, or test policy compliance.
