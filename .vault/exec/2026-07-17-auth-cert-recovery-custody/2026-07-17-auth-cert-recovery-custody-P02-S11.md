---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Prove register, select, check, status, test, and login consume the same resolved certificate bytes

## Scope

- `src/cadrumo/application/auth/tests/test_certificate_sources_check.py`

## Description

This is a reconciliation record. The work it documents was executed under the
originating campaign feature stem before this plan existed; it was not
re-executed here. The originating execution record is the `S52` step record of
the `cli-authority-verb-conformance` campaign, whose action text this step row
carries verbatim.

- Prove register, select, check, status, test, and login all consume the same resolved certificate bytes and the same secure-storage secret.
- Prove a selected named source with no bound secret fails closed and never inherits an unrelated global password across the resolver, the central provider factory, status, test, preflight, and login.
- Prove renewing the selected source keeps every consuming surface on the same resolved bytes.
- Prove cross-bucket and cross-root routing keeps every consuming surface on its own resolved bytes.

## Outcome

The parity proofs exist at HEAD.
`src/cadrumo/application/auth/tests/test_certificate_sources_check.py` declares
twenty-seven tests, of which the following carry this step's claims directly.

Shared resolution across surfaces is proven by
`test_resolver_returns_selected_source_path_and_secure_storage_secret`,
`test_status_test_and_resolver_agree_on_the_selected_certificate_bytes`, and
`test_check_opens_the_bundle_with_the_secure_storage_secret_no_global_fallback`.

Fail-closed absence is proven by
`test_selected_source_without_secret_fails_closed_no_global_credential_leak`,
`test_central_provider_and_explicit_or_omitted_probes_fail_closed_without_named_secret`,
`test_check_named_source_without_secret_never_inherits_a_valid_global_password`,
`test_check_named_source_fails_closed_when_secure_storage_cannot_be_read`, and
`test_unreadable_explicit_settings_target_fails_closed_without_global_fallback`.

A bound secret winning over a deliberately wrong global credential is proven by
`test_bound_named_secret_wins_over_wrong_global_through_central_and_omitted_routes`.
Renewal is proven by
`test_reregistering_active_source_keeps_resolver_provider_status_and_test_on_new_path`.
Login participation is proven by
`test_login_refuses_selected_missing_file_before_unrelated_valid_global_certificate`.
Cross-bucket and cross-root routing is proven by
`test_explicit_settings_second_root_uses_its_own_cached_secret_store`,
`test_explicit_settings_same_bucket_id_uses_target_root_and_restores_ambient_session`,
and `test_preloaded_state_never_combines_its_certificate_path_with_another_bucket_secret`.
The unnamed single-certificate path is preserved and pinned by
`test_resolver_preserves_unnamed_single_certificate_credential_when_no_named_source_is_selected`
and its central-provider counterpart.

Delivery is attributable to two focused commits that add coverage to this file:
`f5273bda59`, "refactor(auth): unify certificate credentials on secure storage;
delete keyring backend", which added roughly one hundred forty lines of parity
coverage in the same change that removed the keyring alternative, and
`9dc920909d`, "fix(auth): fail closed named certificate checks", which added the
fail-closed nodes.

The originating record reports this file green within a ninety-nine-test focused
application auth run.

## Notes

Substantiated. The named test nodes are present at HEAD and two focused commits
with matching subject lines carry them.

The originating record cited `84c435bb94` among this step's delivery commits.
That commit is the certificate-secret CLI recovery proof and does not touch this
module; the attribution above corrects the citation to the two commits that do.

Later revisions to this file arrive through shared freeze and
accumulated-working-tree commits, `80f369609e`, `fc599ce0a8`, `1fe02a929a`, and
`9486f6d0d3`, and through the secret-store dependency-injection commit
`009ed60006`. Those later hunks are not attributable at hunk level from the
commit boundaries, but the step's own coverage predates them and is attributable.

The verification figures quoted above are transcribed from the originating
record and were not re-run for this reconciliation. This record confirms that
the asserted proof nodes exist and that their delivery commits resolve; it does
not independently confirm the suite is green at the current HEAD.
