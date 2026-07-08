---
tags:
  - '#audit'
  - '#integration-fixture-drift'
date: '2026-07-08'
modified: '2026-07-08'
related:
  - "[[2026-07-08-integration-fixture-drift-plan]]"
  - "[[2026-07-08-gate-drift-reconciliation-audit]]"
---

# `integration-fixture-drift` audit: `fixture-drift burndown close (79 to 21)`

## Scope

The follow-up campaign to the gate-drift-reconciliation close, which had recorded (correcting an earlier passphrase-gated hypothesis) that the integration suite carried 79 real failures even with `AEAT_SECRET_PASSPHRASE` set, driven by concurrent campaigns tightening contracts without sweeping every test fixture. This campaign drained the mechanically-fixable share and classified the remainder. All work was test-only; a progressively-dispatched sonnet fleet did the sweeps under coordinator review, with a background lock janitor and lock-aware committers absorbing the persistent stale-`index.lock` churn in this shared worktree. Baseline at start: 79 failed / 2588 passed.

## Findings

### burndown-result | high | integration failures cut from 79 to 21, entirely test-only

Net result: 79 failed -> 21 failed (2647 passed), 58 failures drained across 14 test-only commits, zero production files touched (verified by `git show --stat` across every commit). Phase P01-P03 (`402c677e5c`, `05b540a288`, `355b0a5a28`, `5bf3ff7377`) cleared the three named fixture-drift root causes - non-UUID `profile_id`/`_BUCKET_ID` constants against the uuid-profile-identities sweep, residual profile-create identity-flag drift, and the bucket-session-activation gap in isolated fixtures - taking the count 79 -> 51 (the residual histogram afterward showed uuid 0, session 0, identity 1). Phase P04 triaged the remaining 51 and fixed 30 more (10 commits: `5fa0870651` M303/profile applicability, `26523be588` M111 retencion seeding, `eebd861835` process-state wording, `4e5ac84557` bare-invocation redaction, `87687eef9b` 2025 minimo bindings, `52d8ddf9e7` boe-layout source rename, `f78807aecd` OFX fixture, `e46d9ec452` output-surface allowlist, `8cb017f450` M130->M100 oracle, `6f369552d5` stale NIF in calendar fixtures, `2ca721d14b` secret-leak gate), taking 51 -> 21.

### residual-21-are-production-drift | high | the remaining 21 need production edits or product decisions, not fixture fixes

The 21 survivors are all bucket C/D (production-drift or environment/decision), correctly out of a test-only sweep's scope. They group as: (1) MECHANICAL PRODUCTION HYGIENE - 4 dead command-citation strings in production (`test_suggestion_command_conformance`), 4 verbs missing from the `OperatorSurfaceContract` (`test_operator_surface_contract_drift`), 10 inline Typer help strings not sourced from the locale catalogue (`test_audit_remediation`), a locale string that lost the printed-number/export-ref diagnostic distinction (`test_modelo_casilla_canonical_ids`, 2), and `ModeloReconcileResult` carrying a bespoke `advisories` field instead of the shared notices channel in violation of the cli-notices-are-the-only-diagnostic-channel rule (`test_json_schema_conformance`, 2). (2) ARCHITECTURAL / BEHAVIOURAL - a `--help`/bare-invocation eager-import regression that pulls ~130 registry/workflow modules through `_active_sandbox_notice` (`test_lazy_command_tree`, 2); 4 legacy direct `get_calculation_revision`/`get_work_unit` selector calls needing a shared CLI-support wrapper (`test_architecture_boundaries`); and an M202 first-period readiness-vs-calculate inconsistency where `state_projection` was not updated to match the zero-default `_relation_prefill` applies (`test_modelo_202_required_binding_gate`). (3) PRODUCT-BEHAVIOUR DECISIONS - the calendar now deliberately DEGRADES (notice) instead of refusing on an unreadable local evidence store per an ADR/audit-cited change, but three tests still assert hard refusal (`test_overview_calendar_verb` unreadable-store x2 and the related strict-mode set); M349 readiness became structurally unreproducible after `ac11025c15` widened `applicable_entity_types` to include the attribution entity (`test_modelo_work_readiness_ux`); and the agent-eval lifecycle-contradiction golden lost its premise when M347 rev `2008-y-siguientes` gained real bindings via `8220834c35`, so readiness and verify now genuinely agree and the manufactured-contradiction fixture must be rebuilt (`test_lifecycle_contradiction_golden`, 3). One (`test_modelo_work_ux` decimal-override) is not yet root-caused. None is caused by this campaign.

### transient-parallel-flakes | low | a few failures are -n auto isolation flakes, not real

The triage confirmed the certificate cluster (`test_certificate` register/select/secret-set x4, `test_apoderado` status) and two other node ids are green standalone and fail only under `-n auto` worker isolation - pre-existing parallel-run flakes per the aeat-local-execution re-run-sequentially guidance, not real regressions. They are counted in the 21 but are not actionable as failures; a sequential re-run is the confirmation path.

## Recommendations

Route the 21 by class, honouring the operator model policy (mechanical to sonnet, architectural to opus, ADR-level only with operator approval). The MECHANICAL PRODUCTION HYGIENE group (dead citations, missing contract verbs, inline-help-to-locale, the locale diagnostic string, the bespoke-advisories-to-notices move) is low-risk, rule-aligned, and can be swept by sonnet with production write scope - it was excluded here only because the triage was capped test-only. The ARCHITECTURAL group (eager-import lift, legacy-selector wrapper, M202 readiness/calculate reconciliation) is opus-appropriate and each touches a load-bearing surface. The PRODUCT-BEHAVIOUR DECISIONS (calendar degrade-vs-refuse test expectations, M349 readiness semantics, agent-eval golden rebuild) are ADR-level: the intended behaviour is a product call, so they require operator approval before a fixer changes either the test's asserted behaviour or the production contract. Re-run the certificate/apoderado cluster sequentially to confirm the parallel-flake classification before counting them against any gate. The registry-authority core remained verified-clean throughout; this campaign changed only test fixtures and expectations.
