# Taxpayer profile implementation checkpoint

Status: partial. Session `taxpayer-profile`, PROFILE-01 revision 0.1, session-policy revision 1.7, ACCEPTANCE-01 revision 1.6. Provider: Codex. Provider-assigned lead identifier, cc number, and UUID remain pending. Source state: HEAD `c3de61048917269dada80d30f738bae42608c3b5`; preflight anchor `f72ef01f760f87bbe36e83016ed6393921335090`.

## Discovery and ownership

Two bounded Luna Max attempts did not return a report and were stopped. The vaultspec-rag service could not start because its tool interpreter has no supported accelerator; no shared-tool repair, local-index fallback, or manual reindex was attempted. Under session-policy 1.7 this is a discovery-route capability gap. The lead continued from the brief's retained source maps and targeted reads only.

The anchor-to-HEAD and working-tree path filters found no changes under the profile domain/application packages, CLI profile configuration, TUI profile/app/registration surfaces, or `dev/acceptance`. Current dirty TUI work is in `entrypoints/tui/launcher.py` and Modelo workspace modules and remains outside this session's ownership. Income, IVA, assets, calendar, persistence namespace, and Modelo files have active peer changes. PROFILE-01 must not touch those overlapping files without fresh coordination. No test reservation exists yet.

## Bounded filing-critical field matrix

This is the autonomo path plus contrast fields needed to locate actual writer/consumer gaps. `CLI` means the shared setup/edit wizard projection; `TUI` means the schema-driven Account Profile manager. Both ultimately use canonical profile fact validation and encrypted record persistence. Collection support is recorded separately because a visible schema row is not proof of usable row creation/removal.

| Canonical path | Meaning/type | CLI writer | TUI writer | Consumer/readiness | Current limitation |
| --- | --- | --- | --- | --- | --- |
| `identity.tax_id` | legal identity/string with canonical identity validation | `tax-id` | scalar editor | identity guard, filing profile binding | representation authority is separate |
| `taxpayer_type.entity_type` | natural/legal/attribution enum | `entity-type` | choice editor | conditional setup and applicability | supported contrast set must be tested |
| `tax_residence.ccaa` | residence jurisdiction enum | `tax-residence-ccaa` | choice editor | regional income rules/readiness | not a fiscal-address substitute |
| `censo.activity_start_date` | ISO date | `activity-start-date` | typed scalar validator | deadlines and cross-period calculation gating | projection is current-only, not as-of history |
| `activities.{n}.*` | repeatable activity row | wizard activity surface is incomplete for the accepted row model | rows render, but row creation/removal is unproven | activity/applicability and filing selectors | multi-row writer parity requires reproduction; governing activity ADR is not accepted |
| `irpf.estimation_regime` | IRPF regime enum | wizard choice | choice editor | income applicability/bindings | conflicts and effective dating need tests |
| `iva.regime` | IVA regime enum | `iva-regime` | choice editor | Modelo 303 applicability/readiness | preference cannot override legal applicability |
| `withholding.has_employees` | boolean obligation driver | `has-employees` | boolean choice editor | retenciones readiness | false must remain distinct from unobserved |
| `withholding.pays_professionals_with_retencion` | boolean obligation driver | `pays-professionals-with-retencion` | boolean choice editor | Modelo 111 readiness | clear/unset behavior requires proof |
| provenance and source metadata | source/validity windows | imported or application-owned, not raw operator JSON | displayed through overview where projected | reconciliation and audit | event history is not reconstructable fact history |

Imported-only census evidence remains limited to the existing reviewed reconciliation mapping. Derived fields are not editable. Secrets and representation records are owned outside profile facts. The certificate byte parser remains an explicit unsupported/refusal path.

## Representative fact trace

`censo.activity_start_date` is declared by the profile schema at `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:383-389`. The shared wizard binds `activity-start-date` to that canonical path at `src/cadrumo/application/wizard/catalogue.py:661-662`, and CLI create/edit exposes the field from `src/cadrumo/entrypoints/cli/config/profile_command_specs.py:280`. The TUI manager persists the selected schema path off-loop at `src/cadrumo/entrypoints/tui/profile/overview.py:865-900`; installed composition injects the application write door at `src/cadrumo/entrypoints/tui/installed_session.py:106-121`.

The canonical writer trims or explicitly clears the value and publishes through one validated fact-change path at `src/cadrumo/application/user_profile/fact_write.py:69-136` and `:169-190`. It validates the whole next fact set, compares effective values for no-op behavior, and calls the authenticated `ProfileRecordRepository.apply_fact_changes` CAS boundary. The encrypted record repository loads and updates at `src/cadrumo/application/user_profile/profile_record_repository.py:373-378` and `:457`; its accepted decision binds it to the profile-local secure-object database.

The current projection parses the canonical value into the deadlines taxpayer profile at `src/cadrumo/domain/deadlines/profiles.py:413`. Calculation continuation reads the same wizard-free profile projection at `src/cadrumo/application/calculations/relation_prefill.py:396-416`, and the deadline engine gates pre-activity obligations at `src/cadrumo/domain/deadlines/engine.py:99-115`. This proves one shared input-to-consumer route in source, not installed-runtime acceptance.

## Initial PROFILE-01 outcomes

PR1-PR12 are not exercised. Source evidence supports existing shared writers, encrypted persistence, CAS, current projection, and registered frontend doors, but none is promoted to installed acceptance. PR6 historical resolution and production filing snapshot pinning remain unsupported/undetermined. PR7 real certificate ingestion is blocked on grounded document-layout evidence. Live access is blocked by scope.

## Next bounded actions

- P01.S02: add exact synthetic reproductions for explicit clear versus older dated value, stale CAS writes, in-flight user switch, census precedence, and representative typed TUI editors. Reserve only the selected nodes before running them.
- P01.S03: inspect current filing/profile snapshot callers and calendar ownership, then issue a decision packet if earlier-period evaluation cannot be expressed without new temporal semantics.
- Do not edit dirty Modelo, persistence namespace, launcher, or tax-lane files until their active owner confirms transfer or a disjoint insertion point.

## Verification reservations

- Owner `taxpayer-profile` / root; reserved 2026-09-21; status queued: direct clear-after-dated-value projection probe using synthetic `UserProfileFact` values only.
- Owner `taxpayer-profile` / root; reserved 2026-09-21; status queued: `uv run pytest -n 0` for `test_effective_window_end_is_reported_not_enforced.py::test_a_closed_window_still_projects_its_value`, `test_profile_edit_verb.py::test_a_blank_optional_flag_clears_the_fact_and_records_one_change`, `test_pointer_transition_authority.py::test_real_child_a_to_b_to_a_advances_every_transition_and_refuses_stale_aba`, `test_censo_pull_verb.py::test_a_clear_and_a_value_conflict_raise_separate_notices`, `test_manager_field_editors.py::test_a_date_box_says_which_layout_it_wants`, and `test_app.py::test_change_user_returns_typed_identity_and_revokes_old_profile_root`. No aggregate lane is reserved.

## P01.S02 reproduction results

- Explicit clear after an older dated value: **failed/reproduced**. A temporary exact regression asserted that a 2021 `value=None` fact removes `contact.postcode` after a 2019 value. `record_to_path_values` returned `28001`; pytest exited 1 with 1 failed. Sanitized run metadata: `20260921T152855.776195Z-pytest-30676-c63fa612/run.json`. The temporary test was removed; the permanent test must land with the P02 projection fix.
- Stale selection/CAS foundations: **proven at focused unit level**. Pointer A-to-B-to-A stale ABA refusal passed. `ProfileRecordRepository.apply_fact_changes` independently compares expected revision and digest before replacement; a profile-switch-specific in-flight integration remains missing.
- Entity switching: **partial**. The focused TUI handover test passed and proves a successful F5 outcome revokes the old composed catalogue/search root and returns the new immutable profile identity. It does not start a profile write before F5, so the brief's in-flight-write transition remains not exercised and is assigned to P03.S07.
- Census precedence and clear visibility: **proven at focused entrypoint level**. The exact CLI notice test passed: an explicit clear and an ordinary value conflict remain separate outcomes. Source inspection confirms reconciliation consumes `record_to_effective_facts`, so it sees the latest clear and does not share the value-projection defect.
- CLI clear and TUI date usability: **proven at focused entrypoint level**. CLI blank optional edit persisted an explicit clear and one change; the TUI date editor exposed the required date layout. Collection row creation/removal, numeric units, and installed continuation remain not exercised.
- First reserved command selected three unit nodes and deselected the three integration nodes under the repository default marker expression: 3 passed, 3 deselected, exit 0, metadata `20260921T152912.909723Z-pytest-17540-4811be5e/run.json`. The explicit `-m integration` follow-up ran the three previously deselected exact nodes: 3 passed, exit 0, metadata `20260921T152929.219311Z-pytest-56856-ee8dfe50/run.json`.

Reservations above are released. No aggregate gate or shared external resource was used.
