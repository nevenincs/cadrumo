---
tags:
  - '#reference'
  - '#profile-bundle-tui'
date: '2026-07-24'
modified: '2026-10-03'
body_hash: 'sha256:f786b048854f7037d88c52f329989a5e9eabfd5af8735c4932ce3c8087ac7b94'
related:
  - "[[2026-07-24-profile-bundle-tui-adr]]"
---

# `profile-bundle-tui` reference: `canonical bundle path`

Full-file grounding reads of the portable-bundle authority and the flow substrate performed before designing the interactive mode, plus a vaultspec-rag semantic sweep confirming no other interactive bundle surface exists.

## Summary



Export demands an explicit transport (`--encrypt` vs `--cleartext-local`); the passphrase rides `_secure_input` (hidden confirm-retype prompt or one bounded `--secrets-stdin` JSON object), never argv. Import auto-detects the encrypted envelope by strict parse of `EncryptedProfileBundleExport`, then validates tax-id checksum, filing baseline, UUID collision, and label collision before `atomic_create_profile` + `deserialize_profile_bundle` + the `PROFILE_IMPORTED` event. Cleartext exports emit the loud sensitivity `Notice`; imports emit the active-profile-switch `Notice`.



**Precedent.** `src/cadrumo/entrypoints/cli/_modelo_work_wizard_cli.py` is the shipped pattern for a bespoke entrypoint-built definition: per-run `SCHEMA_FIELD` copy tables keyed by an opaque run token, `select_flow_frontend` + abandonment refusal, answers read back off `FlowState.answers`, results emitted through the standard envelope.

**Roundtrip observation.** An export→import→re-export cycle re-stamps exactly `exported_at` (documented non-content-addressable provenance) and the profile's `created_at`/`updated_at` (import registers a new profile record in the recipient store); every carried field is strictly equal.
