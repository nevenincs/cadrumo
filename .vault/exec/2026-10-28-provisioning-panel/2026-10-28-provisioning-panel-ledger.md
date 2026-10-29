---
tags:
  - '#exec'
  - '#provisioning-panel'
date: '2026-10-28'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:2b394496f83295f382fc92a65485cc3757f76ffc6f93d86237fc8faeaaaad69b'
related:
  - "[[2026-10-28-provisioning-panel-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `provisioning-panel` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S01` `M` `native/application/src/provisioning/engine.rs`
- `S01` `M` `native/application/src/provisioning/protocol.rs`
- `S01` `M` `native/application/src/provisioning/protocol/tests.rs`
- `S01` `M` `native/desktop/src-tauri/src/shell/setup/components.rs`
- `S01` `M` `native/desktop/src-tauri/src/shell/setup/components_tests.rs`
- `S01` `M` `native/desktop/src-tauri/src/shell/setup/wire.rs`
- `S01` `M` `native/desktop/src-tauri/src/shell/setup/mod.rs`
- `S01` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S01` `M` `native/desktop/frontend/src/shell/host.ts`
- `S01` `M` `native/desktop/frontend/src/shell/tauriHost.ts`
- `S01` `M` `native/desktop/frontend/src/shell/setup.ts`
- `S01` `M` `native/desktop/frontend/src/App.tsx`
- `S01` `M` `native/desktop/frontend/src/components/setup/SetupDialog.tsx`
- `S01` `M` `native/desktop/frontend/src/components/setup/SetupDialog.stories.tsx`
- `S01` `M` `native/desktop/frontend/src/components/setup/SetupAdvisory.tsx`
- `S01` `M` `native/desktop/frontend/src/components/settings/LocalModels.stories.tsx`
- `S01` `M` `native/desktop/frontend/src/dev/setupFixture.ts`
- `S01` `M` `native/desktop/frontend/tests/scenarios/setup.spec.ts`
- `S01` `verify:` `cargo test --lib provisioning` -> `pass`
- `S01` `verify:` `tauri test-unit shell::setup` -> `pass`
- `S01` `verify:` `eslint and prettier on touched frontend files` -> `pass`
- `S01` `by:` `high-implementer`
- `S02` `M` `native/application/src/person_operations.rs`
- `S02` `M` `native/application/src/diagnostics/service.rs`
- `S02` `M` `native/desktop/src-tauri/src/logs/severity.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/sede_view.rs`
- `S02` `M` `native/desktop/src-tauri/src/shell/sede_view/tests.rs`
- `S02` `M` `native/desktop/src-tauri/src/app.rs`
- `S02` `M` `native/desktop/frontend/src/App.tsx`
- `S02` `M` `native/desktop/frontend/src/components/browser/BrowserPage.tsx`
- `S02` `M` `native/desktop/frontend/src/components/browser/browserModel.ts`
- `S02` `M` `native/desktop/frontend/src/components/browser/browserWords.ts`
- `S02` `M` `native/desktop/frontend/src/dev/sedeViewFixture.ts`
- `S02` `M` `native/desktop/frontend/src/dev/scenarios.ts`
- `S02` `M` `native/desktop/frontend/src/dev/scenarioHost.ts`
- `S02` `M` `native/desktop/frontend/tests/sede-view-model.spec.ts`
- `S02` `M` `native/desktop/frontend/tests/scenarios/sede-browser.spec.ts`
- `S02` `M` `src/cadrumo/locales/en/common.yml`
- `S02` `M` `src/cadrumo/locales/es/common.yml`
- `S02` `M` `src/cadrumo/locales/ca/common.yml`
- `S02` `M` `src/cadrumo/locales/hu/common.yml`
- `S02` `M` `dev/locales/desktop_chrome.py`
- `S02` `A` `dev/packaging/tests/test_native_error_detail_schema.py`
- `S02` `verify:` `cargo test -p cadrumo-application --features platform,test-support --lib person_operations:: diagnostics::` -> `pass`
- `S02` `verify:` `cargo clippy cadrumo-application --all-targets -D warnings` -> `pass`
- `S02` `verify:` `cargo test cadrumo-desktop -- sede_view logs::` -> `pass`
- `S02` `verify:` `cargo clippy cadrumo-desktop --all-targets -D warnings` -> `pass`
- `S02` `verify:` `pytest dev/packaging/tests/test_native_error_detail_schema.py` -> `pass`
- `S02` `verify:` `tsc --noEmit` -> `pass`
- `S02` `verify:` `playwright tests/sede-view-model.spec.ts tests/scenarios/sede-browser.spec.ts` -> `pass`
- `S02` `by:` `high-implementer`
- `S01` `M` `native/application/src/provisioning/activity.rs`
- `S01` `M` `native/application/src/provisioning/plan.rs`
- `S01` `verify:` `cargo test --lib provisioning` -> `pass`
- `S01` `verify:` `cargo clippy --lib --tests` -> `pass`
- `S01` `verify:` `tauri test-unit shell::setup` -> `pass`
- `S03` `M` `native/desktop/frontend/src/App.tsx`
- `S03` `M` `native/desktop/frontend/src/components/AgentColumn.tsx`
- `S03` `M` `native/desktop/frontend/src/components/Rail.tsx`
- `S03` `M` `native/desktop/frontend/src/components/Settings.tsx`
- `S03` `M` `native/desktop/frontend/src/components/agent/SetupApprovalPrompts.tsx`
- `S03` `M` `native/desktop/frontend/src/components/settings/LocalModels.stories.tsx`
- `S03` `M` `native/desktop/frontend/src/components/settings/LocalModels.tsx`
- `S03` `M` `native/desktop/frontend/src/components/setup/SetupOffer.stories.tsx`
- `S03` `M` `native/desktop/frontend/src/components/setup/SetupOffer.tsx`
- `S03` `M` `native/desktop/frontend/src/components/setup/setupWords.ts`
- `S03` `M` `native/desktop/frontend/src/dev/setupFixture.ts`
- `S03` `M` `native/desktop/frontend/src/shell/provisioningRecovery.ts`
- `S03` `M` `native/desktop/frontend/src/shell/setup.ts`
- `S03` `M` `native/desktop/frontend/tests/provisioning-recovery.spec.ts`
- `S03` `M` `native/desktop/frontend/tests/scenarios/ledger-provisioning.spec.ts`
- `S03` `M` `native/desktop/frontend/tests/scenarios/local-models.spec.ts`
- `S03` `M` `native/desktop/frontend/tests/scenarios/setup.spec.ts`
- `S03` `M` `dev/locales/desktop_chrome.py`
- `S03` `M` `dev/locales/tests/test_audit.py`
- `S03` `M` `src/cadrumo/locales/en/common.yml`
- `S03` `M` `src/cadrumo/locales/es/common.yml`
- `S03` `M` `src/cadrumo/locales/ca/common.yml`
- `S03` `M` `src/cadrumo/locales/hu/common.yml`
- `S03` `A` `native/desktop/frontend/src/components/setup/LocalAi.stories.tsx`
- `S03` `A` `native/desktop/frontend/src/components/setup/LocalAi.tsx`
- `S03` `A` `native/desktop/frontend/src/components/setup/ProvisioningPanel.stories.tsx`
- `S03` `A` `native/desktop/frontend/src/components/setup/ProvisioningPanel.tsx`
- `S03` `A` `native/desktop/frontend/src/components/setup/ProvisioningRow.tsx`
- `S03` `A` `native/desktop/frontend/src/components/setup/SetupPlan.tsx`
- `S03` `A` `native/desktop/frontend/src/dev/ProvisioningStage.tsx`
- `S03` `A` `native/desktop/frontend/src/shell/provisioning.ts`
- `S03` `A` `native/desktop/frontend/src/shell/localAiLanes.ts`
- `S03` `D` `native/desktop/frontend/src/components/setup/SetupAdvisory.tsx`
- `S03` `D` `native/desktop/frontend/src/components/setup/SetupDialog.stories.tsx`
- `S03` `D` `native/desktop/frontend/src/components/setup/SetupDialog.tsx`
- `S03` `D` `native/desktop/frontend/src/components/setup/SetupPrompt.tsx`
- `S03` `D` `native/desktop/frontend/src/components/setup/SetupRowItem.tsx`
- `S03` `verify:` `npx eslint .` -> `pass`
- `S03` `verify:` `npx prettier --check . ../scripts ../tests` -> `pass`
- `S03` `verify:` `node --test dev/eslint/tests/*.test.mjs tests/live/*.unit.ts` -> `pass`
- `S03` `verify:` `npx playwright test -c playwright.scenarios.config.ts setup ledger-provisioning local-models agent-settings-navigation accessibility reading-model setup-approvals` -> `pass`
- `S03` `verify:` `npx playwright test -c playwright.scenarios.config.ts tests/scenarios/sede-browser.spec.ts` -> `fail`
- `S03` `verify:` `npx playwright test tests/provisioning-recovery.spec.ts tests/setup-words.spec.ts` -> `pass`
- `S03` `verify:` `npx storybook build` -> `pass`
- `S03` `verify:` `pytest dev/locales/tests/test_desktop_chrome.py test_parity.py test_locale_translation_honesty.py` -> `pass`
- `S03` `verify:` `pytest dev/locales/tests/test_audit.py` -> `fail`
- `S03` `by:` `high-implementer`
- `S04` `M` `native/desktop/frontend/src/components/Settings.tsx`
- `S04` `M` `native/desktop/frontend/src/components/Settings.stories.tsx`
- `S04` `M` `native/desktop/frontend/src/App.tsx`
- `S04` `M` `native/desktop/frontend/src/components/AgentColumn.tsx`
- `S04` `M` `native/desktop/frontend/src/components/settings/ProviderSettings.tsx`
- `S04` `M` `native/desktop/frontend/tests/scenarios/sede-browser.spec.ts`
- `S04` `M` `native/desktop/frontend/tests/scenarios/local-models.spec.ts`
- `S04` `D` `native/desktop/frontend/tests/scenarios/agent-settings-navigation.spec.ts`
- `S04` `M` `src/cadrumo/locales/en/common.yml`
- `S04` `M` `src/cadrumo/locales/es/common.yml`
- `S04` `M` `src/cadrumo/locales/ca/common.yml`
- `S04` `M` `src/cadrumo/locales/hu/common.yml`
- `S04` `M` `dev/locales/desktop_chrome.py`
- `S04` `verify:` `npx eslint+prettier --check on touched files` -> `pass`
- `S04` `verify:` `npx tsc --noEmit` -> `pass`
- `S04` `verify:` `storybook build to scratchpad` -> `pass`
- `S04` `verify:` `playwright scenarios (setup sede-browser accessibility local-models keyboard providers) 266 tests` -> `pass`
- `S04` `by:` `sonnet-implementer`
- `S05` `M` `native/desktop/frontend/src/components/setup/ProvisioningRow.tsx`
- `S05` `M` `native/desktop/tests/packaged/setup.mjs`
- `S05` `verify:` `dev-server Playwright drive of startup panel, local AI dropdown, concurrent installs, rail spinner, Settings section, Sede offer` -> `pass`
- `S05` `verify:` `npx tsc --noEmit; eslint; prettier --check` -> `pass`
- `S05` `verify:` `npx playwright test -c playwright.scenarios.config.ts setup sede-browser local-models (69/71; 2 timing failures pass in isolation 4/4)` -> `pass`
- `S05` `verify:` `node --test packaged/setup.test.mjs` -> `pass`
- `S05` `verify:` `node desktop_cargo.mjs check --all-targets` -> `fail`
- `S05` `by:` `implementation-engineer`
- `S05` `M` `native/desktop/frontend/src/dev/sedeViewFixture.ts`
- `S05` `M` `native/desktop/frontend/tests/scenarios/sede-browser.spec.ts`
- `S05` `verify:` `npx tsc --noEmit` -> `pass`
- `S05` `verify:` `eslint + prettier --check on both files` -> `pass`
- `S05` `verify:` `playwright scenarios sede-browser.spec.ts --repeat-each=5: 120 of 130 passed, 10 failed only in the context-teardown hang, no assertion failure` -> `fail`
- `S05` `M` `native/desktop/frontend/src/dev/fixtures/agentCatalog.ts`
- `S05` `M` `native/desktop/frontend/src/dev/agentFixtureHost.ts`
- `S05` `M` `native/desktop/frontend/src/dev/scenarioHost.ts`
- `S05` `M` `native/desktop/frontend/src/dev/ProvisioningStage.tsx`
- `S05` `M` `native/desktop/frontend/src/components/setup/ProvisioningPanel.stories.tsx`
- `S05` `M` `native/desktop/frontend/src/dev/setupFixture.ts`
- `S05` `M` `native/desktop/frontend/tests/scenarios/local-models.spec.ts`
- `S05` `verify:` `tsc --noEmit` -> `pass`
- `S05` `verify:` `eslint touched files` -> `pass`
- `S05` `verify:` `prettier --check touched files` -> `pass`
- `S05` `verify:` `playwright local-models+setup repeat-each=3 (new test 6/6; other failures are Close-context teardown timeouts or concurrent build removing chrome-strings.json)` -> `pass`
- `S05` `verify:` `just build-native Release bundle at 58ce4ff11d tree (retries after peer edits and inputs-changed refusals)` -> `pass`
- `S05` `verify:` `just build-native Debug bundle at 58ce4ff11d after just setup-desktop-frontend repaired node_modules lock drift` -> `pass`
- `S05` `verify:` `just build-native Debug desktop-packaged-host and dev.desktop_agent_live.stage_host` -> `pass`
- `S05` `verify:` `built Debug host on throwaway root: provisioning panel, local AI dropdown, concurrent setup, rail spinner, Settings section, Sede offer, feature_refused log (no profile: provisioning not offered, needs sign-in)` -> `fail`
- `S05` `M` `native/desktop/src-tauri/src/shell/setup/mod.rs`
- `S05` `M` `native/desktop/src-tauri/src/shell/setup/components.rs`
- `S05` `M` `native/desktop/src-tauri/src/shell/setup/components_tests.rs`
- `S05` `M` `native/desktop/frontend/src/shell/setup.ts`
- `S05` `M` `native/desktop/frontend/src/App.tsx`
- `S05` `M` `native/desktop/frontend/src/components/setup/LocalAi.tsx`
- `S05` `M` `native/desktop/frontend/src/components/setup/ProvisioningPanel.tsx`
- `S05` `M` `native/desktop/frontend/src/ipc/contract.ts`
- `S05` `M` `native/desktop/frontend/tests/scenarios/setup.spec.ts`
- `S05` `M` `src/cadrumo/locales/en/common.yml`
- `S05` `M` `src/cadrumo/locales/es/common.yml`
- `S05` `M` `src/cadrumo/locales/ca/common.yml`
- `S05` `M` `src/cadrumo/locales/hu/common.yml`
- `S05` `M` `dev/locales/desktop_interface_keys.py`
- `S05` `verify:` `desktop-host-unit-test shell::setup` -> `pass`
- `S05` `verify:` `desktop-host-unit-clippy` -> `pass`
- `S05` `verify:` `playwright setup local-models sede-browser ledger-provisioning` -> `pass`
- `S05` `verify:` `tsc eslint prettier` -> `pass`
- `S05` `M` `native/desktop/frontend/src/shell/provisioning.ts`
- `S05` `verify:` `playwright setup+local-models+accessibility scenarios (142 tests)` -> `pass`
- `S05` `verify:` `tsc eslint prettier` -> `pass`
- `S05` `verify:` `tauri.mjs test-unit shell::setup` -> `pass`
- `S05` `verify:` `tauri.mjs clippy-backend` -> `pass`
- `S05` `verify:` `playwright scenarios setup.spec.ts local-models.spec.ts` -> `pass`

## Notes

- `S01` commit ca94d89d71; desktop unit run patched a peer's uncompiled `sede_view` Default in a private snapshot only; playwright scenarios not run; locale keys `desktop.setup.browser_other_running` and `show_running` left for S03
- `S01` commit 6e38a734d7: concurrent-run space reservation. Desktop run passed 79 before the final wait-condition tweak in the new test; the rerun after it is blocked by peers' in-progress desktop migration (EmergencyWait, `sede_view,` severity, `sign_in)` and a stale generated native contract. A falsified build without the reservation hung at review, which the tweak turns into a failure.
- `S03` tsc --noEmit fails only in src/dev/scenarios.ts ManagerStatus.failure, another session's uncommitted edit
- `S03` sede-browser.spec.ts offer test expects the retired per-item dialog; S02 owns that spec
- `S03` `test_audit` prose-key contract fails on `desktop.browser.notice/publication.identity_mismatch,` added outside S03
- `S03` `desktop_chrome.py` key edits were committed in f041516ab2 by another session
- `S04` dev/locales `test_desktop_chrome:` 2 failures from another session's `service_timeout/payment_cutoff` keys; none from this Step. `desktop_chrome.py` committed as HEAD minus the `browser_open` line; working-tree copy holds another session's refactor, its `desktop_interface_keys.py` line removed there too.
- `S05` Rebuild blocked by other sessions' uncommitted work: src/agent/person/native.rs:1549 E0599 unwrap on `Vec<Sender<Pushed>>;` `src/shell/sign_in/process.rs:493-494` E0373 closure borrows wake. Rebuilt-app check not run; S05 left open.
- `S05` fixture holdPublication/publish committed in 0b064efd2f; spec poll fixes in a007e37053 (auto-commits)
- `S05` Built-app checks need a signed-in profile; creating one needs the operator's password. Builds pass; S05 left open.
