---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# `secure-storage-production-hardening` audit: `exception observability`

## Scope

Audited broad exception handlers and fallback branches in secure-storage-adjacent code for silent swallowing. The convention being enforced is that suppressed failures must either emit at least debug-level diagnostics or return an explicit typed degradation record.

## Good Patterns

- `src/aeat/application/state_projection.py` logs warning with `exc_info=True` when deadline schedule computation fails and returns an explicit empty obligations projection.
- `src/aeat/application/diagnostics.py` logs debug or warning for secure-state, registry, connectivity, and secure-object integrity probe failures while returning diagnostic checks.
- `src/aeat/core/i18n/_render.py` logs debug before falling back from active-profile language resolution or locale load failures.
- `src/aeat/adapters/persistence/storage/sql/secure_objects.py` converts some unreadable-row conditions into `SecureObjectUnreadable` records instead of suppressing them.

## Findings

- Medium: `src/aeat/application/state_projection.py` suppresses `OSError` and `ValueError` while resolving active-profile labels and returns `None` without debug logging. This can hide manifest/path corruption from operator projections.
- Medium: `src/aeat/application/workflow/_profile_bucket_scan.py` has both typed scan-issue surfaces and silent skip helpers. `list_profile_buckets()` and `_read_manifest_or_none()` can drop malformed buckets without logging when callers do not also call `list_profile_bucket_scan_issues()`.
- Medium: `src/aeat/application/modelo/_result_summary.py` catches broad `Exception` twice and returns `None`, causing headline calculation summaries to disappear without debug diagnostics.
- Low: `src/aeat/entrypoints/cli/_modelo.py` returns an empty known-period set when registry lookup fails, with no debug log. This is likely only help/hint degradation, but it is still opaque.
- Low: storage cleanup paths intentionally suppress cleanup failures, for example best-effort close and cleanup blocks. These should either keep explicit `noqa` rationale plus debug logging or be documented as deliberately non-observable where logging could leak sensitive context.
- Medium: `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py` suppresses import/setup failures during engine eviction and then suppresses `dispose_engine(...)` failures with `pass`. The cleanup must not raise from `close()`, but the branch should still emit debug diagnostics or a deliberate typed degradation marker so production shutdown and bucket switching failures remain observable.

## Repairs

- `W11.P18.S73` repaired `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py` so import/setup defects remain outside the cleanup catch and surface normally.
- `W11.P18.S73` replaced silent engine-disposal suppression with warning-level cleanup telemetry. The message records only the exception type and intentionally omits bucket identifiers, local paths, SQLAlchemy URLs, tracebacks, and key material.
- `W11.P18.S73` did not add `noqa` suppressions or coverage pragmas to the cleanup path; the residual catch is scoped to runtime cleanup after zeroisation has already run.

## Disposition

- `W11.P18.S73` owns concrete repairs for silent fallback branches that affect secure-storage readiness, profile discovery, projection labels, and operator-visible CLI output.
- `W11.P19.S77` should add or extend guard checks so newly introduced broad `except` blocks either log, return typed degradation, re-raise, or carry a documented best-effort cleanup exemption.

## Validation

The audit used targeted `rg` scans for `except` branches returning `None`, empty tuples, empty lists, empty dicts, `continue`, or `pass`, then inspected representative storage-adjacent call sites.

Follow-up validation for `W11.P18.S73` included focused ruff checks, bucket-session/master-key tests, central error-registry enforcement, runtime tests, state-projection tests, and a targeted code review of the cleanup observability boundary.
