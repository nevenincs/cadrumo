---
tags:
  - '#reference'
  - '#profile-bundle-tui'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:a7cf9605bf8a8360a0339841da876219f2dcde6334a815cba9dca1ff60c5cf22'
related:
  - "[[2026-07-24-profile-bundle-tui-adr]]"
---

# `profile-bundle-tui` reference: `canonical bundle path`

Full-file grounding reads of the portable-bundle authority and the flow substrate performed before designing the interactive mode, plus a vaultspec-rag semantic sweep confirming no other interactive bundle surface exists.

## Summary

**Bundle authority (compose, never fork).** `UserProfilePortableExport` (`src/cadrumo/domain/user_profile/_portable_export.py`) is the v3-only portable payload: profile record, financial history tuples, generic secure-object carry (`CarriedSecureObject`, natural-key addressed, re-encrypted under the recipient DEK on import), and a `CoverageManifest`. `export_profile_bundle` (`src/cadrumo/application/user_profile/_bundle_export.py`) is the single publication authority — three-phase durable sequence (stage `0o600` temp → `PREPARED` journal → atomic replace → `COMPLETED` → `PROFILE_EXPORTED` event), per-destination exclusive lock, crash reconciliation via `reconcile_prepared_exports`. `serialize_profile_bundle` / `deserialize_profile_bundle` (`_bundle.py`) are the payload authorities.

**CLI surface.** `src/cadrumo/entrypoints/cli/_config/_profile_bundle.py` registers `export`, `import`, and `subject-access-request`. Export demands an explicit transport (`--encrypt` vs `--cleartext-local`); the passphrase rides `_secure_input` (hidden confirm-retype prompt or one bounded `--secrets-stdin` JSON object), never argv. Import auto-detects the encrypted envelope by strict parse of `EncryptedProfileBundleExport`, then validates tax-id checksum, filing baseline, UUID collision, and label collision before `atomic_create_profile` + `deserialize_profile_bundle` + the `PROFILE_IMPORTED` event. Cleartext exports emit the loud sensitivity `Notice`; imports emit the active-profile-switch `Notice`.

**Flow substrate.** `FlowDefinition`/`FlowPage` (`src/cadrumo/application/flows/_definition.py`) declare pages with `CopyRef` copy slots only (locale key, schema field, terminology concept — resolved loudly at render by `_copy.py`). Widgets include `SELECT`, `PATH`, `TEXT`, `SECRET` (masked everywhere: question screen, review, line frontend, status screen). `detect_frontend_capability` (`_capability.py`) is the single host probe; `select_flow_frontend` (`src/cadrumo/adapters/inbound/tui/_select.py`) maps capability to `FlowTuiApp` / `LineFlowFrontend` and refuses NON_INTERACTIVE. `run_scripted_flow` (`_scripted.py`) drives the identical engine headless for tests.

**Precedent.** `src/cadrumo/entrypoints/cli/_modelo_work_wizard_cli.py` is the shipped pattern for a bespoke entrypoint-built definition: per-run `SCHEMA_FIELD` copy tables keyed by an opaque run token, `select_flow_frontend` + abandonment refusal, answers read back off `FlowState.answers`, results emitted through the standard envelope.

**Roundtrip observation.** An export→import→re-export cycle re-stamps exactly `exported_at` (documented non-content-addressable provenance) and the profile's `created_at`/`updated_at` (import registers a new profile record in the recipient store); every carried field is strictly equal.
