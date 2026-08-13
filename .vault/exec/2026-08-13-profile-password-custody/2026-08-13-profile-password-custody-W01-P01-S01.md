---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:95e89ad31abc66e4ce8287a7bf8a68d016a91a5306f394faca80baa6bf8adb70'
step_id: 'S01'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh define the strict v1 custody records, typed refusals, password limits, and taxonomy ownership

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/`

## Description

- Add the strict `ProfileCustodyEnvelope`, finite Argon2id parameter record, and authenticated wrapped-DEK record under `src/cadrumo/adapters/persistence/storage/custody/`.
- Reject duplicate JSON members, unknown fields, foreign schema versions, invalid canonical encodings, and altered self-digests at the raw persisted boundary.
- Enforce password input as 15 to 256 Unicode scalar values and at most 1,024 strict UTF-8 bytes without normalization or trimming.
- Establish registered typed custody refusals for retired custody detection, unsupported DEK rotation, KDF resource limits, and unavailable KDF supervision.
- Enroll only current profile-capsule custody artifacts in the core storage taxonomy and expose their resolved constants through the existing storage layout facade.
- Register the new typed errors and add localized messages through `dev.locales`.
- Add real production-import tests for record roundtrip, corrupted record refusal, Unicode password boundaries, taxonomy closure, and typed refusal coverage.
- Remediate the independent S02 review findings: validate the duplicate-free raw JSON mapping through canonical bytes and refuse every noncanonical source representation; preserve the canonical refusal discriminator when hostile context supplies the same key.
- Remediate the subsequent S02 review finding: cap a canonical v1 custody envelope at 704 UTF-8 bytes, reject oversized raw input before decoding or JSON parsing, bound generation, and close the base64 scalar-length surface so valid serialization cannot exceed that ceiling.
- Prove the exact-cap and cap-plus-one raw parser routes plus oversized generation refusal through production imports.

## Outcome

Normal password custody now has a strict, independently addressable v1 record contract with no provider selection, recovery access, or legacy-format fallback. The raw persisted boundary accepts only byte-exact canonical JSON after strict schema and self-digest validation, has a finite 704-byte pre-decode input limit, and typed refusal context cannot forge its canonical discriminator. Focused custody, taxonomy, error-registry, lint, and type gates pass.

## Notes

The initial parallel pytest attempt crashed before executing a test; the required sequential rerun completed successfully. The independent S02 review found and blocked completion on canonical-byte validation, refusal-context integrity, and raw parser boundedness; all findings were remediated before re-closing S01. `dev.locales scaffold --check` remains blocked by four unrelated concurrent `cli.overview.status.next_step.*` omissions; all custody error leaves are present.
