---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:d25ccdbc4718862eac73323ad5e726fda4fc4fd6bd8a2937f66b5b536989cb59'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---

# `profile-password-custody` audit: `S04 envelope, recovery artifact, sentinel, and capsule publication review`

## Scope

Independent review of `W01.P02.S04` only: password and optional recovery envelope authority, portable recovery artifact boundaries, DEK sentinel proof, immutable capsule commit markers, one-rename publication, normal-unlock isolation, hostile filesystem handling, public exports, and real-behavior tests against the accepted custody decisions and binding plan. The review does not authorize production edits, plan closure, Git operations, later Steps, product storage, remote state, or service state.

## Findings

### filesystem-publication | high | Path-based publication does not establish hostile-filesystem or crash-safe atomicity

The initial `publish_profile_custody_capsule` candidate checked destination existence and then called path-based `os.rename`; on POSIX that can replace a raced empty destination directory rather than preserving collision refusal. Nested data-parent creation and later path-based opens admitted link, junction, or reparse substitution between checks, failed-staging cleanup was not proven safe against a substituted junction, recovery-artifact export had the same parent-check/open race, and `_fsync_directory` returned without durability work on Windows. The implementation therefore did not prove a fully durable marker inside one complete staging capsule, exclusive one-sibling publication, or bounded no-follow behavior under hostile concurrent filesystem changes.

### export-authority | high | Recovery artifact export trusts a caller assertion and omits the required warning receipt

The initial `export_profile_custody_recovery_artifact` accepted a caller-supplied `password_authenticated_profile_id`; matching that UUID to the recovery record was not proof that the current password had unwrapped the committed envelope and authenticated the canonical sentinel. The API returned only the artifact and carried no structured warnings for offline guessing exposure, separate storage, retained exported copies, or password-login independence. This allowed a caller to manufacture authorization and left the required operator contract unrepresented.

### enrollment-seam | high | Constructors accepted arbitrary wraps without a production supervised enrollment path

The initial candidate exposed strict record constructors but no production operation that derived a password or recovery key and encrypted the DEK through the supervised child. Tests populated `wrapped_dek` with synthetic byte patterns, so they could not prove password-envelope and recovery-envelope AAD separation, successful real unwrap, recovery-artifact sentinel proof, or the S03 generic seam's fail-closed behavior.

### security-evidence | high | Focused tests do not exercise the declared isolation and filesystem threat model

The initial five capsule tests replaced `recovery.v1.json` with a directory but did not trace the real normal-unlock dependency closure to prove zero stat, open, or read of recovery. They also did not exercise link, junction, or reparse refusal, destination collision races, crash points around marker and rename, external-artifact path races, authenticated export warnings, or recovery unwrap and sentinel failure. Passing those tests was insufficient evidence for the accepted S04 boundary.

### final-re-review | high | Recovery artifact import still follows hostile ancestry and Windows reparse leaves

The final candidate hardens capsule publication and external export, but `import_profile_custody_recovery_artifact` still delegates to `_recovery._read_regular_file`, which performs a path-based `os.open`. On POSIX `O_NOFOLLOW` protects only the final component and does not anchor the source ancestry; on Windows that flag is unavailable and the open follows a final symlink or reparse point. A concurrently substituted parent, junction, or reparse leaf can therefore redirect the explicitly named import outside the intended bounded path. The new hostile-path test covers the export parent only and does not exercise artifact import. Replace the import reader with component-wise no-follow, descriptor-relative POSIX traversal and Windows component plus final-leaf handle anchoring equivalent to the capsule reader, then prove parent-link, final-link, junction/reparse, non-regular, size, and identity-change refusal on the real platform.

### final-isolation-proof | high | Normal-read observation proves opens only, not zero stat and read of recovery

The final normal-read test installs a Python audit hook for `open`, while the returned `access_trace` is produced by the same implementation whose dependency closure it is meant to verify. The audit hook cannot detect a recovery `stat`, and a future direct stat outside the self-reported trace would leave the test green. The accepted gate explicitly requires zero stat, open, and read of `recovery.v1.json` on normal login. Add an independent observer or hostile filesystem arrangement that makes each of those operation classes fail if attempted, and drive the full committed-material plus password-unlock route. The code was source-reviewed as recovery-independent, but the mandated adversarial evidence is not yet present.

### re-review-status | medium | Earlier enrollment and export-authority findings are remediated but crash evidence remains narrow

The final candidate adds real supervised password and recovery wrapping, distinct canonical AAD domains, real password/recovery/artifact unwrap with sentinel proof, password reauthentication for export, structured warnings, descriptor-relative POSIX capsule publication, Windows stage-handle rename with no-replace semantics, immutable minimal marker publication, collision cleanup, and current-marker-only recognition. Focused Windows tests and three static gates pass. However, the seven tests do not inject termination at marker-write, pre-rename, post-rename, or publication-fence boundaries. The hidden staging name and marker-only recognition preserve the basic discovery boundary by construction, but crash-point evidence should be added alongside the import and isolation remediation before closure.

### final-remediation-review | low | All critical and high findings are closed

The final remediation closes hostile recovery-artifact import with component-wise `O_DIRECTORY` and `O_NOFOLLOW` traversal plus descriptor-relative leaf reads on POSIX, and no-delete, no-reparse ancestry anchors plus exact `CreateFileW` leaf-handle validation and `ReadFile` on Windows. Real tests accept a canonical artifact and refuse parent links, final links, directories, and oversized sources. Normal password isolation now runs committed-material loading and the actual supervised password unlock while an audit hook and independent C-call profile observer watch recovery-path open, stat, lstat, and read operations; the recovery path is also a directory so an accidental file read fails physically. A marker written and fsynced only under the sibling staging name remains undiscoverable and normal loading refuses it, proving the pre-rename crash boundary. The focused module passed all nine real Windows tests; Ruff, ty, and basedpyright also passed with no diagnostics. Source review confirms the current-format marker is the only recognition proof, the marker carries publication facts only, password and recovery AAD domains remain separate, no legacy parser or old provider import exists, and no unresolved critical or high finding remains in `W01.P02.S04`.

## Recommendations

Keep `W01.P02.S04` unchecked until every critical or high finding recorded above is remediated and independently re-reviewed. Do not start `W01.P02.S05` from this review.
