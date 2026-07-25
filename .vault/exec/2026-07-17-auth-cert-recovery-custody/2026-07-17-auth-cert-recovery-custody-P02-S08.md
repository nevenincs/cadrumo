---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Route auth status, test, login, central session acquisition, live callers, state projection, and modelo provider construction through the active certificate credential resolver by centralizing exact certificate credential projection in the application provider factory

## Scope

- `src/cadrumo/application/auth/_certificate_sources.py`

## Description

This is a reconciliation record. The work it documents was executed under the
originating campaign feature stem before this plan existed; it was not
re-executed here. The originating execution record is the `S49` step record of
the `cli-authority-verb-conformance` campaign, whose action text this step row
carries verbatim.

- Centralize certificate provider construction behind one application projection carrying path, password, and friendly name exactly, including explicit absent values.
- Route auth status, test, login, preflight, central session acquisition, state projection, and modelo workflow provider construction through the same projected provider settings.
- Preserve omitted-provider reporting so status and test do not invent a provider when workflow state has none.
- Resolve selected named-source secrets only from the selected profile's secure store and fail closed rather than inheriting a global password.
- Make the secret-store factory route-aware across both secret and blob roots.
- Record storage-root provenance on bucket sessions and require bucket identity plus root identity before reusing an active session.
- Open explicit-settings operator spans before applying their settings scope so a same-identifier bucket in another root cannot inherit ambient key material.
- Add real certificate, encrypted-storage, two-bucket, two-root, same-identifier, route-cache, status and test, and session-restoration regressions.

## Outcome

The centralized projection exists at HEAD and every named consumer routes
through it. The choke point is
`src/cadrumo/application/auth/_credential_resolution.py`, which declares
`resolve_active_certificate_credentials` and
`project_active_certificate_credentials` and exports both. The `application.auth`
facade imports and re-exports both names, and the login path inside the facade
calls `resolve_active_certificate_credentials`. State projection consumes the
same authority: `src/cadrumo/application/_state_projection_auth.py` imports
`project_active_certificate_credentials` and uses it to populate the certificate
credentials it projects.

Parity across the consuming surfaces is proven rather than asserted.
`src/cadrumo/application/auth/tests/test_certificate_sources_check.py` declares
`test_status_test_and_resolver_agree_on_the_selected_certificate_bytes`,
`test_central_provider_and_explicit_or_omitted_probes_fail_closed_without_named_secret`,
`test_explicit_settings_second_root_uses_its_own_cached_secret_store`,
`test_explicit_settings_same_bucket_id_uses_target_root_and_restores_ambient_session`,
and `test_preloaded_state_never_combines_its_certificate_path_with_another_bucket_secret`,
which are exactly the routing, root-isolation, and fail-closed claims the step
makes.

The originating record reports focused verification at execution time of
forty-eight certificate and secret-backend tests, forty-four auth operator and
session tests, twenty state-projection tests, fourteen materialisation tests,
twenty-nine bucket-session and recovery tests, thirty-four master-key
fallback, adverse, and idle tests, and eleven modelo workflow gate tests, with
Ruff clean on every changed path and Import Linter analysing 3,435 files and
16,298 dependencies with all five contracts kept.

## Notes

PARTIALLY SUBSTANTIATED on attribution, fully substantiated on end state. Two
qualifications, both material.

First, the step row names
`src/cadrumo/application/auth/_certificate_sources.py` as its target file, but
the centralized credential projection this step exists to create does not live
there. It lives in the sibling module
`src/cadrumo/application/auth/_credential_resolution.py`, which was created
during the same wave. The named target file at HEAD holds only the certificate
source registry operations, registering, listing, selecting, removing, and
reading the active source record. Anyone auditing this step by opening the file
the row names will not find the work. The row's named target is wrong, or at
best names a collaborating module rather than the authority; the ADR-level
claim, one centralized projection, is nonetheless satisfied.

Second, no focused commit could be attributed to this step. The module holding
the projection was introduced by `80f369609e`, an operator-directed freeze
commit whose subject describes it as a snapshot of in-flight application work
covering the auth logout and reset split, workflow, configuration reset, and
credential resolution together. Its later revisions arrive through further
freeze and accumulated-working-tree commits, `fc599ce0a8`, `8ca3c1d134`,
`1fe02a929a`, and `9486f6d0d3`. None of these carries a subject line naming this
step's work, and their contents span multiple concurrent campaigns, so
hunk-level ownership cannot be recovered from the commit boundaries. The end
state is confirmed by direct inspection of the symbols, their consumers, and
the parity tests, which is the evidence this record rests on; the delivery
chain is not independently attributable.

The verification figures quoted above are transcribed from the originating
record and were not re-run.

The originating record disclosed that its final commit was deliberately held
back to avoid absorbing a concurrent bucket-lock owner's overlapping diff in the
master-key provider file, which is consistent with the work reaching the tree
through a later shared freeze commit rather than its own.
