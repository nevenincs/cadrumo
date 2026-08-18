---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:f9b0682ee98e40c5ff4757e884ef41ad33ef98f8f9a4058d1b946bee67951a74'
step_id: 'S14'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh implement password-only restore, explicit restore-recover lineage, and new-identity portability, wiring the exclusive recovery-artifact export and import to the per-profile artifact module that ALREADY EXISTS in the custody package rather than authoring a second one, that module already being a guarded external export with no coupling to the archive transport

## Scope

- `src/cadrumo/application/bucket_maintenance/ and src/cadrumo/application/user_profile/ and src/cadrumo/adapters/persistence/storage/custody/_recovery_artifact.py`

## Description

- Add capsule archive and restore primitives (`_capsule_archive.py`, `_capsule_restore.py`) under the user-profile package, with password-only restore, explicit restore-recover lineage, and new-identity portability.
- Wire recovery-artifact export and import to the existing per-profile artifact module in the custody package — no second artifact module authored.
- Turn on recovery enrolment at profile creation in the same change (the accepted decision places enrolment at creation).
- Carry the distinguished setup state through workflow health and resolution so a mid-setup profile is never reported as complete or as no-profile.
- Drop the disk-usage verb's dead retired-manifest accounting; the retired-custody-absence detector remains the load-bearing reader of that name.
- Update the generated API reference stubs for the two new modules.
- Land with real-behavior coverage for archive, restore, recovery enrolment, and setup-state tracking; landing commit `350de5347b`.

## Outcome

Delivered: password-only restore and recovery-artifact restore both publish restored capsules through the restore authority with DEK-sentinel agreement; artifact export/import route through the single custody-package module; enrolment at creation minted before the create transaction (no second writer into a published capsule). The step was checked by the campaign while the execution record was never scaffolded; this record reconstructs the delivered state from the landing commit (`350de5347b`, 2026-08-17) so the checked row carries its evidence.

## Notes

- Reconstructed post-hoc from commit `350de5347b` and the checked row; the campaign's no-checked-step-without-record discipline is satisfied from 2026-08-18 onward.

Stamps re-attested through the edit engine after authoring the reconstructed body.
