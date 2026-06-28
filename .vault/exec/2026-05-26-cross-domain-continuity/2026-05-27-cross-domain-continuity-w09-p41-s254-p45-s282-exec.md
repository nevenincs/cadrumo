---
step_id: S254
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W09.P41.S254 + W09.P45.S282

## S254 — Batch 3 fixture migration completion

The three files in S254's scope (`test_profile_lifecycle_verbs`,
`test_root_grammar_invariants`, `test_root_help_shape`) were already migrated to
`isolated_profile_storage_root` / `isolated_sessionless_storage_root` in prior
commits. This step landed two regressions discovered during verification:

**Regression 1 — Infinite recursion in `_activate_subcommand_output_language`.**
Commit `03016c382` (W08.P36.S141-S143) introduced a duplicate local definition
of `_activate_subcommand_output_language` that shadowed the import from
`_common`, causing infinite recursion on every `config profile show` and
auth-subcommand invocation. The duplicate definition (lines 1568-1569) was
removed.

**Regression 2 — `repair profile --repair-manifest-status` blocked by strict
manifest guard.**
The `read_manifest` hardening (which raises `StorageValidationError` when
`status` is absent) blocked `_bucket_key_schedule` from returning the key
schedule for a legacy manifest. Since `profile_storage_session` calls
`_bucket_key_schedule`, the repair command could no longer open the session it
needs to read the encrypted profile record. Fixed by extending
`_bucket_key_schedule` to catch `StorageValidationError("missing required
lifecycle status")` and fall back to parsing `key_schedule` directly from the
TOML payload.

**Outcome:** 56/56 tests pass across the three S254 files.

## S282 — Auth env-var/class-name leak via `tr()`

`_authenticator.py::_require_bundle` previously raised:

```
CertificateLoadError("AEAT_CERTIFICATE_PATH is not set; cannot build CertificateBundle")
CertificateLoadError("AEAT_CERTIFICATE_PASSWORD_SECRET is not set; cannot build CertificateBundle")
```

Both messages exposed internal env-var names (`AEAT_CERTIFICATE_PATH`,
`AEAT_CERTIFICATE_PASSWORD_SECRET`) and the internal class name
(`CertificateBundle`) in operator-facing errors.

The raises were routed through `tr()` with new locale keys:
- `application.auth.certificate.load.path_unset`
- `application.auth.certificate.load.password_unset`

Locale prose was added to all four supported languages (en/es/ca/hu). The
`scaffold` tool was consulted but incorrectly reports `cli.root.*` keys as
orphans (scaffold does not track `_tr` alias); locale files were updated by
direct edit to avoid destroying those valid keys.

**Outcome:** 115/115 auth tests pass.

## Commit

`2b37264f4` — Task #102: S254 manifest-status repair path fix + S282 auth env-var leak
