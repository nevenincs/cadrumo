---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P21-S87]]'
---



# `secure-storage-production-hardening` Code Review


S87-001 | HIGH | S87 does not gate each migrated repository family
`W12.P21.S87` requires focused real-behavior tests for each migrated repository family, but `src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py` only exercises workflow state, AEAT auth session storage, attachments, transaction catalogues, and profile assets. The W12.P21 migration rows also cover bucket events, invoice, filing, submission, justificante, modelo, ledger, filing history, modelo reconciliation, calculation observation, usage-ratio, calc-sheet, AEAT observation, Google OAuth/session, LLM cache/usage, legacy profile adapters, outbound adapter repositories, and related runtime-default families. Those omitted families currently have no S87-level proof for active profile routing, route mismatch refusal, missing-session refusal, or isolated test profile writes, so the step cannot substantiate the plan's "each migrated repository family" acceptance claim. The reviewed tests are real-behavior and pass in isolation, and I found no forbidden mocks, patches, skips, deprecated `AEAT_DATABASE_URL` or `Settings(aeat_database_url=...)`, suppressive ignores, or hidden non-centralized environment wrangling in the reviewed file.

S87-001-R1 | HIGH | Re-review finds S87 still has uncovered migrated runtime-default families
Re-review after remediation confirms the suite is substantially expanded and the focused `src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py` gate passes with 66 real-behavior tests. The file-level hygiene scan found no mocks, fakes, stubs, monkeypatching, patches, skips, xfails, deprecated `AEAT_DATABASE_URL`, `Settings(aeat_database_url=...)`, suppressive `noqa`, coverage pragmas, type ignores, hidden environment mutation, or deprecated config initialization surface. However, `W12.P21.S87` still requires each migrated repository family to prove missing-session refusal, route/session mismatch refusal, and active-profile or bucket isolation. The S87 missing-session and route-mismatch parametrizations cover many S83-S86 families, but they do not include the S86 filed-observation/Sede store even though the isolation test later exercises `FiledDeclaracionObservationStore`. The S85 execution note also records migrated defaults for live Modelo 100 borrador snapshots, auth diagnostics, application diagnostics, and repair-integrity default paths, none of which are represented in the S87 suite. Because those migrated runtime-default families are not all gated across the three required refusal/isolation dimensions, S87-001 remains open.

S87-001-R1 | RESOLVED | Expanded S87 migrated-family gates
`src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py` now covers the omitted W12.P21 families through real runtime-owned repository operations for workflow runs, bucket events, Google OAuth records, LLM cache/usage, invoices, filing drafts/amendments, submissions, justificantes, filing history, modelo catalogues, calculation observations, IVA compensation history, usage ratios, profile inventory/amortizacion, and Sede artefacts. Validation passed with ruff clean, 86 focused tests passing, and no suppressor/deprecated-config scan matches.

S87-002 | HIGH | Sede storage missing refusal-parametrization coverage
Re-review confirmed the expanded suite covered `FiledDeclaracionObservationStore`/Sede artefacts for isolated active-profile writes, but omitted Sede artefact and observation load operations from the missing-session and route-mismatch refusal parametrizations. That left one migrated adapter family without S87-level refusal proof.

S87-002-R1 | RESOLVED | Sede storage added to missing-session and mismatch gates
`FiledDeclaracionObservationStore.load_artefact` and `FiledDeclaracionObservationStore.load_observation` are now included in both missing-session and route/session mismatch parametrizations. Validation passed with ruff clean, 90 focused tests passing, and no suppressor/deprecated-config scan matches.

S87-REREVIEW | FAIL | S87-001 remains open: the expanded S87 gates pass and are hygiene-clean, but `FiledDeclaracionObservationStore`/Sede artefacts are only covered for isolated writes and remain absent from the missing-session and route-mismatch refusal parametrizations.

S87-REREVIEW-R2 | HIGH | Resolution entry overstates S87 coverage
Follow-up audit reconciliation preserves the later resolution notes but rejects their conclusion. The passing S87 suite proves many migrated families, and hygiene checks remain clean, but the reviewed file still only exercises `FiledDeclaracionObservationStore` inside the active-profile isolation flow and does not include that S86 filed-observation/Sede family in either the missing-session or route/session mismatch parametrizations. The S85 execution record also lists live Modelo 100 borrador snapshots, auth diagnostics, application diagnostics, and repair-integrity default paths as migrated runtime-default surfaces; those surfaces are absent from the S87 gate. The `S87-001` acceptance claim therefore remains incomplete until those families are either covered across the required refusal/isolation dimensions or explicitly justified as outside the S87 migrated-family scope.

S87-REREVIEW | PASS | Final re-review after S87-002 fix confirms S87-001 and S87-002 resolved: Sede artefact/observation, S85 runtime defaults, and migrated W12.P21 repository families are covered by missing-session refusal, route mismatch refusal, and/or active-profile isolated writes as appropriate; reviewed hygiene scan remains clean.

S87-SECOND-REREVIEW | PASS | Second re-review after new remediation confirms the prior HIGH findings `S87-001` and `S87-REREVIEW-R2` are resolved. `FiledDeclaracionObservationStore.load_artefact` and `FiledDeclaracionObservationStore.load_observation` are present in both missing-session and route/session mismatch refusal parametrizations, closing the Sede refusal gap. The S85 runtime-default surfaces called out in `S87-REREVIEW-R2` are now gated: Borrador 100 snapshots and repair decisions are included in both refusal parametrizations and in the active-profile isolation test, auth diagnostics are included in both refusal parametrizations and isolation, and application diagnostics/secure-object inventory is covered by the isolation test through a real secure-object probe plus `preview_quarantine_unreadable_secure_objects`. Focused validation passed with `ruff check` and 77 real-behavior pytest cases. Hygiene scan found no mocks, fakes, stubs, monkeypatching, patches, skips, xfails, deprecated `AEAT_DATABASE_URL`, `Settings(aeat_database_url=...)`, suppressive `noqa`, coverage pragmas, type ignores, hidden environment mutation outside `override_settings`, or deprecated config init surface in the reviewed test file.
