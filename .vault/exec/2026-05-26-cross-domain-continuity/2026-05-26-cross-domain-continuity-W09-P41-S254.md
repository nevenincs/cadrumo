---
tags:
  - "#exec"
  - "#cross-domain-continuity"
step_id: S254
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-W09-P41-S253]]"
---

# cross-domain-continuity W09.P41.S254 — Batch 3 mixed-fixture triage (3 files)

## Outcome

Migrated the three Category B test files flagged as needing mixed-fixture
triage to the canonical secure fixture helpers. All 56 tests across the
three files pass. A pre-existing D5 regression in `config_profile_import`
was identified and fixed.

### Files migrated

| File | Fixture used | Result |
|------|-------------|--------|
| `test_root_grammar_invariants.py` | `isolated_sessionless_storage_root` | 7/7 PASS |
| `test_root_help_shape.py` | `isolated_sessionless_storage_root` + `isolated_profile_storage_root` | 12/12 PASS |
| `test_profile_lifecycle_verbs.py` | `isolated_profile_storage_root` (module) + `profile_storage_session` (per-test) | 37/37 PASS |

### Key structural decisions

- Module-level autouse `_isolated_backend` in `test_profile_lifecycle_verbs.py`
  uses `isolated_profile_storage_root` (file-backed). The old fixture used
  `AEAT_SECRET_STORE_BACKEND=unsecured`, which created sessions with
  `bucket_id="ephemeral"`. `_SYNTHETIC_SESSION_BUCKET_IDS` bypassed all
  bucket-ID matching checks; real per-bucket sessions cannot cross-load.

- `_seed()` uses `profile_create_storage_span` + `enforce_unique_tax_id=False`
  to avoid cross-bucket tax-id scan failures when multiple profiles exist.

- `_stage_bucket_manifest()` provisions key material with
  `profile_create_storage_span(bucket_id): pass` then calls
  `logout_active_profile()` so the manifest exists without an active session.

- Tests that read encrypted records after CLI invocation (e.g.
  `BucketEventHistoryRepository().load()`, `build_lifecycle_service().read()`)
  wrap the read in `profile_storage_session(profile_id)`. The session opened
  by the CLI command is closed when the runner returns.

- `test_repair_profile_manifest_status_backfills_legacy_active_manifest`:
  `profile_storage_session("operator")` must be opened BEFORE stripping the
  `status` field — `_bucket_key_schedule` reads the manifest at session open;
  stripping status first makes the session impossible to open.

- Tests invoking `profile_app` or `repair_app` directly (bypassing
  `decorate_typer_app`) were changed to route through `root_app` so that
  `command_error_boundary` is active and `ProfileAlreadyExistsError` renders
  correctly instead of propagating raw.

- Multi-profile setup tests (`rename`, `switch/delete`, `tombstone show`)
  replaced `_create_via_cli("alpha")` + `_create_via_cli("beta")` with
  `_seed("alpha")` + `_seed("beta")`. Wizard create uses
  `enforce_unique_tax_id=True`; when "beta" creates, `_refuse_duplicate_tax_id`
  scans all live profiles and fails when it cannot cross-load "alpha"'s
  encrypted record with the wrong bucket session.

### Production bug fixed — D5 regression in `config_profile_import`

Commit `af81954a6` introduced a Tier 1 UUID collision check in
`config_profile_import` but did not skip it when `--label` is provided.
The original pre-D5 code called `_atomic_create_profile(display_name=target_label,
facts=record.facts)` without `profile_id`, minting a fresh UUID. The
post-D5 code always preserved the bundle UUID, so `--label` on a previously
imported profile always raised "profile already registered".

Fix: `fresh_uuid_mode = explicit_label is not None`. When `True`, Tier 1
is skipped and `_atomic_create_profile(profile_id=None, ...)` is called to
mint a fresh UUID.

## Commits

- `2a897c177` — S254: complete Batch-3 fixture migration (test_profile_lifecycle_verbs)

## Files changed

- `src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py` — full fixture migration
- `src/aeat/entrypoints/cli/_config/__init__.py` — D5 regression fix + ruff clean
