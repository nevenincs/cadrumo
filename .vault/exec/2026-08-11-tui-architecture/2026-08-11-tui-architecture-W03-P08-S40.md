---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:58c54830f30978997e9ffca8fc3c68759f9ad8d2f36097a95111987c0d0a23ee'
step_id: 'S40'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Register profile field mutation, repeatable-row mutation, bundle export, and profile logout operations through existing user-profile authorities

## Scope

- `src/cadrumo/application/user_profile/_operation_definitions.py`
- Canonical row and manager-field application helpers, the registered generic secure-reference namespace and facade, and their real integration proofs.

## Description

Implemented the private canonical user-profile operation population:

- `user-profile.field-mutation` delegates exactly once to `apply_manager_profile_field_mutation`.
- `user-profile.repeatable-row-mutation` delegates exactly once to `add_profile_repeatable_section_row`, which alone composes `next_section_row_index`, `section_row_facts`, and `apply_profile_fact_changes`.
- `user-profile.bundle-export` requires `SECURE_REFERENCE` request/result storage and S114's five-minute one-shot `profile.bundle-export.passphrase` secret. Its executor consumes the secret, then calls the existing `export_profile_bundle` publisher; it does not recreate the export lock, journal, event, or reconciliation flow.
- `user-profile.logout` binds the exact active `profile:<UUID>` subject and calls `logout_active_profile`, the sole strong-close authority. It returns the subject reference because its secure operand store has intentionally been closed.

All four definitions declare `SECURE_REFERENCE`, definition-subject conflict scope, no owned resources, `NONE`/`UPDATED`/`UNKNOWN` effects, and `INTERRUPT` reconciliation.

The in-scope row schema/index/fact/write orchestration was removed from `_manager_actions.py`; that surface now collects values and calls the application row authority. Manager scalar-field trim-or-clear policy now lives once in `apply_manager_profile_field_mutation`; both manager field paths delegate to it.

Discovered shared persistence substrate gap: request/result test stacks had dynamic unregistered operation namespaces, which correctly made the real bundle exporter reject process-local inventory. Added exactly one registered `cadrumo.application.operations.secure_references` namespace with `{content_digest}`, financial ciphertext custody, `BUCKET_LOCAL`, and `PROCESS_LOCAL` disposition. It is declared in the canonical storage registry and exported only through `adapters.persistence.operations.operation_secure_reference_repository`. Replaced generic dynamic operation-result/operand test namespaces; no S40-specific bypass was added.

## Evidence

Pre-change Vaultspec-RAG queries:

- `profile field mutation repeatable row persistence secure custody operator operation only:prod`
- `profile bundle export operation secret passphrase one shot journal secure reference only:prod`
- `profile logout strong close active profile operation session artefact pointer only:prod`
- `canonical secure-reference operand namespace operation supervisor encrypted storage profile export process local only:prod`

Post-change fixed-point Vaultspec-RAG queries:

- `profile scalar field mutation canonical application operation manager frontend direct write only:prod`
- `repeatable section row index facts mutation manager action canonical application only:prod`
- `profile bundle export passphrase one shot secret operation journal publisher manager only:prod`
- `profile logout strong close operation presentation wrapper teardown only:prod`
- `registered canonical process local secure reference content digest operation operand request result namespace persistence adapter only:prod`

The final namespace RAG returned only `OPERATION_SECURE_REFERENCE_NAMESPACE` in `_namespace_registry.py:297` and the operations facade/factory. Exact corroboration:

```text
rg -n 'namespace="[^"]*(operation|operand|result)[^"]*"' src/cadrumo -g '*.py'
src/cadrumo/adapters/persistence/storage/_namespace_registry.py:299: namespace="cadrumo.application.operations.secure_references"
```

This is zero second **implementation/namespace owner**, not zero invocation scatter.

Real gates completed:

- `uv run --no-sync ruff check ...` over all S40-owned implementation and test paths: PASS.
- `uv run --no-sync pytest -m integration -q src/cadrumo/application/user_profile/tests/test_operation_definitions.py src/cadrumo/adapters/persistence/operations/tests/test_secure_refs.py`: PASS, `9 passed`.
  - Uses the real supervisor, filesystem journal/lease, encrypted SQL secure objects, active custody session, one-shot secret zeroisation, real export publication/journal, profile record persistence, and logout pointer/session sealing.
- Broad generic operation/auth/live/censal run: `76 passed, 5 failed`; two failures were explicit live registry validation failures for concurrent Modelo 184/303 deadline work. Three filed-history terminal failures were rechecked separately and a focused retry passed after the concurrent registry state changed.
- Manager/UI/fact-door regression run: `172 passed, 6 failed`. Failures are retained for adjudication rather than classified away: `test_a_blank_submission_on_an_optional_field_still_clears_it`; three manager screen active-session/profile-record failures; `test_populating_a_conditional_region_does_not_evict_its_siblings[status-populated]`; and `test_a_modal_secret_never_paints_its_value`. Hunk/stack comparison shows none enters S40's changed row helper/action or `_manager_populated` fixture; the field frontend executable hunk was only a removed comment. A reviewer follow-up must make the final attribution before any resume.

Independent post-change review found the canonical definitions, single export publisher/journal, one secret request path, old manager row block removal, and one secure-reference namespace/facade sound. It also correctly refused projection-only closure pending production composition.

## Outcome

PAUSED — implementation and focused evidence are retained, but S40 is not closed and its plan checkbox remains untouched.

The current tree has no duplicate implementation owner, but it still has five direct execution/invocation doors because production `OperationSupervisor` composition is not yet available:

| Residual path | Current direct call | Required handoff |
| --- | --- | --- |
| `_manager_frontend.py:191,371` | scalar field mutation | W02.P19.S122 production composition, then W06.P14.S77 deletion/cutover |
| `_manager_actions.py:1111` | repeatable row mutation | W02.P19.S122, then W06.P14.S76 |
| `_manager_actions.py:486-525` | passphrase collection and bundle publisher | W02.P19.S122, then W06.P14.S76 |
| `_manager_actions.py:1443-1448` | profile logout | W02.P19.S122, then W06.P14.S76 |
| `_custody.py:302-312` | CLI profile logout | W02.P19.S122; no specific S76/S77 deletion target covers this non-manager CLI surface, so a plan amendment is required before closure |

S43 is a public user-profile facade prerequisite only; it does not substitute for S122 production composition. The coordinator must complete authoritative W02.P19.S115-S124 (especially S122), then resume S40 to cut the doors over and remove them under S76/S77 (and the required CLI deletion-plan amendment).

## Notes

- No plan check or plan checkbox modification was performed.
- The retained frontend functions are not shims: they are live synchronous invocation authorities and therefore explicit blockers, not acceptable fixed-point wrappers.
- The unrelated `MANAGER_AUTH` batch in `_manager_actions.py:941-950` remains a distinct authentication-domain door with its own `MANAGER_AUTH` identity; it is neither a scalar-manager nor repeatable-row duplicate.
