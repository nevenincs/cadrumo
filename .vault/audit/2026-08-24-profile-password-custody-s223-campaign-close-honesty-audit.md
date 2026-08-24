---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:092b1fca7bf8465e074c78bb2914e9072334d969952f9ab97f239eb3c9532fec'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
  - "[[2026-08-18-profile-password-custody-campaign-close-audit]]"
  - "[[2026-08-24-profile-password-custody-fresh-context-campaign-close-audit]]"
  - "[[2026-08-24-profile-password-custody-s206-recovery-parity-review-audit]]"
  - "[[2026-08-24-profile-password-custody-s209-posix-kdf-descriptor-attestation-review-audit]]"
  - "[[2026-08-24-profile-password-custody-s220-exec-evidence-audit]]"
  - "[[2026-08-24-profile-password-custody-s219-docs-audit]]"
  - "[[2026-08-24-profile-password-custody-s222-platform-gate-audit]]"
---
# profile-password-custody audit: fresh-context campaign-close honesty review

## Scope

Bounded fresh-context review at current HEAD fb38015559bd1961bb7897a1ca6dfefb4f8cd95b, restricted to the five named carry-forwards from S219-S222: the remaining global no-skip sites, the S222 session/receipt refusal-snapshot gap, S220 committed annotation warnings, the two documented-command failures, and global locale drift. The existing S206/S209/S221/S222 records and feature-scoped Vaultspec results were read as recorded evidence. This review made no production, test, or user-documentation edits and does not ratify the peer S223 closure already present in the shared branch.

## Findings

### global-no-skip-sites | medium | The canonical no-skip gate remains red at two sites

The recorded current run of uv run --no-sync pytest -q -n 0 dev/tests/test_no_skip_xfail.py reported 23 passed and 2 failed. The custody carry-forward is src/cadrumo/application/user_profile/tests/test_capsule_source_reads_are_anchored.py:85, where pytest.skip is used when symlink construction is unavailable. The same gate also reports dev/packaging/tests/test_distribution_evidence_emit.py:245, a separate packaging/release-owner skip for a non-Windows launcher case. S222 named only the custody site, but both violations keep the global ratchet red. The custody owner must replace the platform skip with a deterministic supported refusal fixture or centrally governed live gate; the packaging owner must resolve its own skip. Do not count the S222 platform matrices as closing either global violation.

### session-receipt-refusal-snapshot | low | Refusal witnesses omit session and receipt artifacts

The S222 LOW finding remains present in src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py:454-495. The storage snapshot excludes names containing session or receipt, and the refusal assertion compares that filtered snapshot. A refusal-path regression could therefore create or alter one of those artifacts without failing the equality witness. Existing S222 source review and focused refusal evidence found no current production mutation, so this is a bounded test-witness gap rather than a demonstrated custody defect. Extend the exact same-scope, cross-scope, descriptor-refusal, and root/leaf-inapplicability witnesses to include these artifacts or assert their absence separately. Carry it forward as LOW until the test-only witness is repaired.

### s220-annotation-warnings | low | The committed S220 warning set is resolved

The S220 repair commit a287297827a removed the committed template annotations and corrected the two provenance findings. The recorded feature-scoped commands vaultspec-core vault check annotations --feature profile-password-custody --json, body-sections, and exec-mapping returned empty diagnostics, and the subsequent feature-scoped check all was clean. No S220 annotation carry-forward remains. The only later annotation source was the S223 scaffold itself; this body edit removes that scaffold content through the owning Vaultspec edit verb.

### documented-command-failures | medium | Both S219 command-conformance failures remain actionable

The recorded command uv run --no-sync pytest -q -n 0 -m integration src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py reported 347 passed and 2 failed. The first failure is docs/_sequences/contracts/workstation-setup/install-agent-harness.seq:2, whose result frame cites aeat --format json app agent --output ./operator-workspace even though agent is not an aeat app subcommand and --output is not an option there. The second is docs/how-to/profile-setup.md:375, whose inline aeat config profile delete NAME --yes span violates the mandatory cli-sequence or static-frame display rule. Route each to its owning sequence/documentation owner and rerun the complete conformance module before closure. A passing target sequence check does not close these failures.

### global-locale-drift | medium | The whole-corpus locale gate remains red

The recorded command uv run --no-sync pytest -q -n 0 dev/docs/tests/test_docs_localization.py reported 9 failures: each of es, ca, and hu has 30 of 57 incomplete page catalogues, each has three download.md dash-policy violations, and each has the orphan reference/environment-overrides.po catalogue. These are global documentation-campaign findings, not S206/S209 custody failures, but they remain a red gate and must have explicit owning teams and dispositions. Reconcile the incomplete/fuzzy catalogues, remove or restore the orphan, and correct the dash-policy translations before claiming the global locale gate green.

## Recommendations

Do not ratify the existing S223 checkbox or its committed no-blocker outcome while the two no-skip sites, two documented-command failures, and three-locale drift remain red. Preserve the S220 resolved disposition and the S206/S209 positive matrix evidence recorded in S221/S222; retain the S222 snapshot gap as an explicit LOW carry-forward. The feature-scoped Vaultspec check all was clean in the recorded run and the custody-owned tree has not changed since that evidence, but structural Vaultspec cleanliness does not override the red application and documentation gates. Reopen or supersede S223 only through the owning plan/exec CLI workflow after these carry-forwards have owners and fresh gate evidence. No full S206/S209 platform rerun was performed in this bounded review.
