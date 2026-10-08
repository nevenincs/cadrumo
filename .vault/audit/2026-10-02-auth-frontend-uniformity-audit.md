---
tags:
  - '#audit'
  - '#auth-frontend-uniformity'
date: '2026-10-02'
modified: '2026-10-02'
body_schema: 'body-v2'
body_hash: 'sha256:2497cf63d619d4ac0cb9adb14467cd4f262b02b6231bcd308e97c007a3f55cfb'
related:
  - "[[2026-10-02-auth-frontend-uniformity-plan]]"
---

# `auth-frontend-uniformity` audit: shared authentication configuration

## Scope

Review S01-S03 against accepted profile-auth, TUI supervision, and certificate lifecycle decisions. Base 3d40c2a658; candidate 28fd5c3a76 and f1503bc78f plus S02 review corrections and S03 integration tests and capture refresh. Trace configuration through encrypted profile facts, operational state, CLI, installed TUI worker, registered operation, public observation, and result projection. Preserve concurrent filing and locale edits.

## Findings

### profile-subject | high | Bind delayed saves to the displayed profile before admission

The shared submission helper reconstructed its subject from the current active bucket. A delayed worker launched from an older profile screen must retain that screen's exact profile subject so the executor's active-profile guard refuses a switch. This requires an explicit profile identity at shared submission and composition, passed from the installed account closure and CLI admission. Initial status: REVISION REQUIRED pending the scoped correction and a real profile-switch refusal proof.

### failure-taxonomy | high | Preserve public failure category and retryability

Forwarding all supervised codes through CoreValidationError reclassified failures as integrity errors and discarded canonical retryability. The correction uses a registered core PublicErrorProjectionError carrying only a registered code and an optional validated diagnostic hash. The common envelope resolves the original code's category, message key, retryability and runbook; no private executor exception or context is recreated. Anonymous failures retain INTERNAL_INVARIANT with their opaque diagnostic reference. Status pending final error-contract verification.

### review-resolution | low | Both high findings are resolved and the integrated review passes

Candidate 90661f7f71 plus S03 artifacts. The displayed profile is passed through the shared composition and submission to the exact operation subject. A real second-profile registration followed by a delayed submission refuses, leaves the active replacement unchanged, and leaves the original unchanged after reauthentication. PublicErrorProjectionError preserves canonical error code, category, retryability and runbook, and refuses a private path as its diagnostic reference. Known failures expose no private context; anonymous failures retain the validated opaque diagnostic hash. No unresolved high or critical findings remain.

### verification-coverage | low | Real custody and served artifacts cover the affected journeys

The S02 suite passed 219 auth, profile admission, cross-frontend and CLI architecture checks. S03 profile/editor/fixture checks passed 64 cases, and operation public-contract/registry checks passed 119 cases. The combined core-error/frontend run passed 61 cases; its one test failure occurred only when reading an old profile without reauthenticating after a switch. The verification fixture was corrected, and that case passed separately. The 61 applicable results are reused because production code did not change. Scoped Ruff lint/format and ty passed for 16 paths. The canonical dev.docs CLI reference generator produced 20 pages, including the Cl@ve Móvil route option. Synthetic CLI-to-TUI-to-backend capture proof confirms matching provider and route persistence and masked typing without a live AEAT login.

The refreshed runs are profile-auth-uniformity-2026-10-02-en with 16 authentication frames, and profile-setup-auth-uniformity-2026-10-02-es/en/ca/hu with 52/26/26/26 wizard and profile frames. All 146 frames have matching current source fingerprints, zero geometry or glyph findings, zero missing/stale artifacts, and HTTP PNG bytes matching manifest hashes. Review includes the narrow validity-date modal and Spanish final positive confirmation. The review server remains running.

### persistence-boundary | low | Partial effects remain explicit at the existing custody boundaries

The encrypted profile fact command and workflow configuration use their existing persistence owners under one auth mutation scope. They are not presented as one database transaction. The registered operation records UNKNOWN before execution and narrows only on a proven result; unexpected partial failures therefore remain visible for reconciliation. Profile intent remains authoritative, and retry is idempotent. No new credential lifecycle or persisted schema is introduced. Concurrent locale register edits in the shared Catalan CLI catalogue were preserved; no unrelated filing or locale edits were reverted.

### capture-coherence | low | Freeze rendering inputs while concurrent TUI work continues

After the original successful HTTP and live-source check, other work changed shared TUI composition and Modelo files. Subsequent live-tree refresh batches correctly refused publication when their source fingerprint changed during rendering. S03 was reopened. The shared installed operation graph was checked again and passed its focused real-worker test at 20261002T084248.277875Z-pytest-85316-bbbe1b32.

The final 146 frames were regenerated from a source-only frozen copy of the then-current production package. Copy verification required equal full-package fingerprints before copying, after copying, and in the copy: bcb22e0d7398b5c824e0b176bac9acc21409a8d542e4f89d28858700286f76f1. Every renderer imported that copy explicitly; its TUI fingerprint is 59df2ffd9df7e2d0102a1f39f00f6c5596246e3e6848a4c0eb372373d2158c03. Twelve authentication/profile implementation files match the live worktree byte-for-byte. Current-source indicators for the entire TUI may subsequently change with unrelated editing; that does not turn these coherent snapshot frames into current live-tree captures. This distinction is retained in the final report.

All five final manifests agree with the frozen source and contain 146 frames with zero failures, geometry findings, missing glyphs, missing artifacts or stale artifact digests. Every PNG served by the existing HTTP server was fetched again and matched its manifest hash. No production files, other work, or the running server were changed to freeze the capture. PASS remains applicable to the auth implementation and coherent visual evidence.

## Recommendations

PASS. Both high findings are resolved; required checks have applicable passing evidence and the earlier failed fixture invocation remains recorded in the ledger. Close S03. Local setup and persistence were verified; live AEAT authentication was not attempted. Existing certificate acquisition, secret custody, and Cl@ve Permanente password delivery remain governed by their owning authorities.
