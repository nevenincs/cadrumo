---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/plan/ location)
# Feature tag (replace cross-campaign-hardening with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#plan'
  - '#cross-campaign-hardening'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-21'
# Complexity tier (mandatory for new plans).
# Allowed: L1 (Steps only), L2 (Phases above Steps),
# L3 (Waves above Phases above Steps), L4 (Epic above Waves
# above Phases above Steps; PM association required).
# Pre-existing plans without this field default to L2.
tier: L2
# Related documents as quoted wiki-links.
# Carries the AUTHORISING documents (ADR, research, reference,
# prior plan) for every Step in this plan; Steps inherit this
# chain; per-row reference footers do not exist.
related:
  - "[[2026-05-21-cross-campaign-hardening-audit]]"
---

# `cross-campaign-hardening` cross-campaign hardening rollout

Severity-ordered rollout that executes every actionable finding in the
cross-campaign swarm audit (52 swarm findings — 8 CRITICAL, 19 HIGH,
15 MED, 10 LOW — plus 6 carried-over coordinator items, Axis G). Tier
L2: Phases above Steps. Each Step names its audit finding id; the
executor re-verifies the finding against current code before acting,
pairs every structural fix with a roundtrip or behaviour test, and
commits + pushes per Step or tight cluster. The coordinator task list
mirrors this plan as the live tracker.

Discipline: shared worktree — `git diff -- <file>` before the first
edit of any file; abort or cross-commit per the shared-worktree rule.
Run the locale-parity, CLI, and touched-domain suites after each Phase.
The contested item (Axis E vs WCLI-1 on `_config/__init__.py:1498`) is
resolved by inspecting the actual class hierarchy before `P01.S06`.

## Steps

### Phase `P01` - CRITICAL remediation

Eliminate the eight CRITICAL findings: provenance loss, persistence
roundtrip gaps, blank CLI refusals, and a domain→adapter import.

- [ ] `P01.S01` - CALC-1: restore casilla provenance on `amend_modelo_revision`; re-run typed-observation build over the corrected casilla map.
- [ ] `P01.S02` - EXIM-1: add `casilla_provenance` to `ModeloDraft`; carry `legal_refs`/`source_refs` through export + verify.
- [ ] `P01.S03` - PERS-1: strict `SecureObjectRecord` roundtrip test (6 fields non-default) + on-disk-mutation anti-tautology.
- [ ] `P01.S04` - PERS-2: strict `SecretRecord` roundtrip witness + anti-tautology on the JSON index.
- [ ] `P01.S05` - PERS-3: `BucketManifest` fail-closed on an absent `status` key in TOML reads.
- [ ] `P01.S06` - WCLI-1/WCLI-2: `_config/__init__.py` `str(exc)` refusals → `resolve_error_message` (verify the contested classification first).
- [ ] `P01.S07` - XDOM-1: export `SecureBoundRepository` from a public surface; re-point the three domain repository imports.

### Phase `P02` - HIGH: CLI error-rendering localization

Close the message-key-loss pattern across the remaining CLI handlers.

- [ ] `P02.S01` - WCLI-3: `_modelo.py` ~16 `typer.BadParameter(str(exc))` sites → `resolve_error_message`.
- [ ] `P02.S02` - WCLI-4: `_app_live.py:609` narrow the broad `except` + `resolve_error_message`.

### Phase `P03` - HIGH: hexagonal / private-import cleanup

Restore the hexagonal boundary at five application↔adapter and
application↔domain private-import sites.

- [ ] `P03.S01` - XDOM-2: route workflow `_engine.py` adapter imports through Protocol seams / shared types.
- [ ] `P03.S02` - XDOM-3: import `FiledDeclaracionObservation` from the public `sede` surface.
- [ ] `P03.S03` - XDOM-4: promote `_normalise_key` to the `domain.profile` public surface.
- [ ] `P03.S04` - XDOM-5: public accessor for `_profile_binding_selectors` on `domain.user_profile`.
- [ ] `P03.S05` - XDOM-6: public export for the auth-diagnostics namespace constant.

### Phase `P04` - HIGH: binding-source retirement

Close the `"invoice"` source-kind drift.

- [ ] `P04.S01` - BIND-1: close the `"invoice"` wildcard in `resolve_counterpart_binding_row_values`.
- [ ] `P04.S02` - BIND-2: snapshot-build rejection of retired `source = "invoice"` bindings.

### Phase `P05` - HIGH: provenance + roundtrip coverage

Provenance on import; snapshot validation; and the persistence
roundtrip / anti-tautology gaps.

- [ ] `P05.S01` - CALC-2: `import_external_filing` builds registry-sourced `CasillaObservation` rows.
- [ ] `P05.S02` - CALC-3: snapshot validator asserts every `input_kind="bound"` casilla has a binding definition.
- [ ] `P05.S03` - PERS-4: unify `object_key` type across record/write + identity roundtrip test.
- [ ] `P05.S04` - PERS-5: `RecoveryRecord` envelope-file roundtrip + base64 anti-tautology.
- [ ] `P05.S05` - PERS-6: `SecureObjectMetadata` peek consistency test + anti-tautology.
- [ ] `P05.S06` - PERS-7: concurrent-write serialization test for `SecureObjectRepository`.
- [ ] `P05.S07` - EXIM-2: fichero-BOE RESERVED-field anti-tautology proof.
- [ ] `P05.S08` - EXIM-3: asset-ledger delete-field anti-tautology proof.

### Phase `P06` - HIGH: export coverage + Google Sheets guard

- [ ] `P06.S01` - EXIM-4: document + test Google Sheets as a one-way export mirror.
- [ ] `P06.S02` - EXIM-5: export tests for no-layout modelos, `binding_rows`, computed fields.

### Phase `P07` - MED cluster

- [ ] `P07.S01` - CALC-4/CALC-5/CALC-6: defence-in-depth note; typed per-source binding selectors (with BIND-4); replace the tautological formula-runtime test.
- [ ] `P07.S02` - PERS-8/PERS-9: TOML datetime ISO inspection; `EncryptionMetadata` AAD missing-vs-empty.
- [ ] `P07.S03` - WCLI-5/WCLI-6: `BucketEventType` enum-error `tr()`; `InvoiceLinkError` disposition.
- [ ] `P07.S04` - XDOM-7/XDOM-8/XDOM-9: `LedgerTransactionPayload` model; public URL-validation helper; public `sede` export.
- [ ] `P07.S05` - EXIM-6: verify verdict reports reserved-field unchecked casillas.
- [ ] `P07.S06` - BIND-3/BIND-4/BIND-5: numeric profile-binding Decimal-channel test; free-form source-kind cleanup; estimación-directa #521 disposition.

### Phase `P08` - LOW cluster

- [ ] `P08.S01` - CALC-7: tighten `ModeloInputsProviderProtocol.load_inputs` return type.
- [ ] `P08.S02` - PERS-10/PERS-11: KDF-param witnesses; `SecureObjectNamespaceIntegrity` test.
- [ ] `P08.S03` - XDOM-11/XDOM-12: re-point registry private imports + export `RegistrySnapshotRef`; non-303 period-binding tests.
- [ ] `P08.S04` - BIND-8/BIND-9: stabilise the `test_invoice_bindings` fixture filter; atribucion/refund source-kind disposition.

### Phase `P09` - carried-over coordinator items (Axis G)

Pre-existing coordinator task-list items folded into this rollout.

- [ ] `P09.S01` - GEN-1 (task #501): wire the live G313 Playwright driver actual fetch path (live-gated).
- [ ] `P09.S02` - GEN-2 (task #506): triage the discovery-swarm legacy/shim inventory into fixes.
- [ ] `P09.S03` - GEN-3 (task #517): non-303 period-token test coverage for `_resolve_declaration_period_inputs` (core already implemented; folds into `P08.S03`).
- [ ] `P09.S04` - GEN-4 (task #518): profile UUID-vs-label — DELEGATED to the `cli-workflow-redesign` campaign; tracking only.
- [ ] `P09.S05` - GEN-5 (task #520): CLI UX polish cluster; cross-check the `cli-workflow-redesign` bug-inventory clusters D/E first.
- [ ] `P09.S06` - GEN-6 (task #521): estimación-directa profile auto-resolution disposition; folds into `P07.S06`.

### Phase `P10` - verification + persona-testimonial re-audit

- [ ] `P10.S01` - run the full gate set (locale parity, CLI suite, registry suite, touched-domain suites) — green.
- [ ] `P10.S02` - persona-testimonial pass over the hardened CLI + backend; reproduce the original finding scenarios from an operator's seat.
- [ ] `P10.S03` - fold any testimonial regressions into a follow-up wave; re-run the affected gates.

## Parallelization

`P01` (CRITICAL) lands before every HIGH phase. `P02`, `P03`, `P04`,
`P05`, `P06` are HIGH phases with no hard interdependency and may be
executed in any order or interleaved. `P07` (MED) and `P08` (LOW)
follow the HIGH phases. `P09` items are mostly cross-references into
earlier phases or delegated; `P09.S04` requires no work here. `P10`
runs last and re-runs if `P10.S03` opens a follow-up wave.

## Verification

The plan is complete when every Step is `- [x]`. Mission criteria:
every CRITICAL and HIGH finding has a landed structural fix paired
with a roundtrip or behaviour test; the locale-parity, CLI, registry,
and touched-domain suites are green; and the `P10` persona-testimonial
re-audit reproduces no regression of an original finding scenario.
MED/LOW findings either land a fix or carry a recorded wontfix
rationale. Per-Step cadence: re-verify the finding, land fix + test,
run the touched suite, commit + push, check the box, update the task.
