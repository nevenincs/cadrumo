---
tags:
  - '#audit'
  - '#cross-campaign-hardening'
date: '2026-05-21'
modified: '2026-05-21'
related: []
---



# `cross-campaign-hardening` audit: `cross-campaign-swarm-audit`

## Scope


## Findings


## Recommendations



## Context

## Scope

Six-axis multi-agent audit swarm run after a structural-refactor window
(state-architecture campaign, the `errors.*` translation wave, registry
hardening). Read-only review of the CLI and backend. Each finding is
verified against current code; this document is the inventory the
cross-campaign hardening rollout plan executes against.

Axes: calculation-engine grounding, persistence-boundary identity,
workflow + CLI surface, export/import fidelity, cross-domain handoffs,
selector + binding drift. The last two are appended when their agents
report.

## Severity totals (4 of 6 axes)

| Axis | CRIT | HIGH | MED | LOW |
|---|---|---|---|---|
| calculation-engine | 1 | 2 | 3 | 1 |
| persistence-boundary | 3 | 4 | 2 | 2 |
| workflow + CLI | 2 | 2 | 2 | 1 |
| export/import | 1 | 4 | 1 | 0 |
| cross-domain | 1 | 5 | 4 | 2 |
| selector/binding | 0 | 2 | 3 | 4 |
| **TOTAL** | **8** | **19** | **15** | **10** |

## Axis A — calculation-engine grounding

### CALC-1 — CRITICAL — `amend_modelo_revision` produces a zero-observation CalculationRevision
`src/aeat/application/modelo/_actions.py:2606`. The amend path builds `CalculationRevision` without `observations=`, so it defaults to `()`. Every complementaria/sustitutiva amendment discards all `CasillaObservation` rows — no `formula_id`, `legal_refs`, or `source_refs` reach the persisted revision or the CLI JSON emit. **Remediation:** resolve the snapshot and run `_build_typed_observations` over the corrected casilla map (re-running the engine with corrected inputs is cleanest); pass `observations=`.

**Resolution (P01.S01, dd10fd70d) — fixed.** `amend_modelo_revision` now resolves the snapshot via `_resolve_registry_snapshot_for_work_unit(work_unit)` and passes a populated `observations=amendment_observations` via the `_amendment_observations()` helper to the `CalculationRevision` constructor; the amend flow now carries casilla provenance instead of producing a zero-observation revision. 16 amend-flow tests green.

### CALC-2 — HIGH — `import_external_filing` produces zero typed observations
`src/aeat/application/modelo/_actions.py:2819`. Imported AEAT casilla values carry no registry provenance into the domain record; CALC-1 amendments compound it. **Remediation:** build `CasillaObservation` rows pulling `legal_refs`/`source_refs` from the registry casilla definitions (formula-provenance fields legitimately absent for external data).

**Resolution (P05.S17) — fixed.** `import_external_filing` now builds registry-sourced `CasillaObservation` rows carrying `legal_refs` and `source_refs` from the registry casilla definitions.

### CALC-3 — HIGH — no snapshot-level assertion that every `input_kind="bound"` casilla has a binding definition
`src/aeat/domain/calculations/registry/_snapshot.py` / `_formula_runtime.py`. The guard fires at formula-runtime input rejection (wrong layer) instead of snapshot validation. **Remediation:** add `_validate_bound_casilla_binding_coverage` to the snapshot referential-integrity validator + a `test_referential_integrity.py` case.

**Resolution (P05.S18) — fixed.** The snapshot referential-integrity validator now asserts every `input_kind="bound"` casilla has a binding definition; the check fires at snapshot-build time rather than at formula-runtime input rejection.

### CALC-4 — MED — `_initial_values` defence-in-depth gap for non-Decimal values (`_formula_runtime.py:199`). No active bug; `_reject_non_decimal` gates it. No code change unless a caller bypasses the gate.

**Resolution (P07.S27) — verified already-satisfied.** The `_reject_non_decimal` defence-in-depth note already exists at `_formula_runtime.py:178-182`. No code change required.

### CALC-5 — MED — `DataBindingDefinition.selector` is a broad union, not a per-source typed model; consumer code casts. `_schema.py:1371`. **Remediation:** typed per-source selector models in `_bindings.py`; typed accessor. (Overlaps the binding axis.)

**Resolution (P07.S27) — verified already-satisfied.** Per-source typed selector models (`_PreviousModeloSelector`, `_InvoiceSelector`, `_OssIossLedgerSelector`, `_IvaLedgerSelector`, `_RentaLedgerExpenseSelector`, `_WithholdingSelector`, `_RelatedPartySelector`, `_ForeignAssetSelector`, `_AtributionSelector`, `_RefundSelector`) plus `_validated_*_selector` typed accessors plus a snapshot-time selector-shape gate all exist in `_bindings.py` / `_validate_references.py`. Residual diffuse consumer-cast cleanup overlaps the binding axis.

### CALC-6 — MED — tautological calc test: `test_formula_runtime.py:120` hand-computes sign expectations from the same registry formula. **Remediation:** workbook-parity assertion or a structural assertion.

**Resolution (2026-05-21, P07.S27, 4c486e840) — fixed.** CALC-4 and CALC-5 verified already-satisfied: the `_reject_non_decimal` defence-in-depth note already exists at `_formula_runtime.py:178-182`, and per-source typed selector models (`_PreviousModeloSelector`, `_InvoiceSelector`, `_OssIossLedgerSelector`, `_IvaLedgerSelector`, `_RentaLedgerExpenseSelector`, `_WithholdingSelector`, `_RelatedPartySelector`, `_ForeignAssetSelector`, `_AtributionSelector`) with `_validated_*_selector` typed accessors and a snapshot-time selector-shape gate already exist in `_bindings.py`/`_validate_references.py`. For CALC-6, the flagged assertions are sign-only (`07 < 0`, `11 < 0`, `12 >= 0`) — no Decimal is manufactured, so they are the rule-permitted "structural assertion" alternative, not a numeric tautology. Added a docstring grounding them as a sign-propagation + `MAX(_,0)`-floor structural test of the modelo-130 pago-fraccionado graph; the assertions already discriminate (they fail if the formula graph is wrong against AEAT).

### CALC-7 — LOW — `ModeloInputsProviderProtocol.load_inputs` returns `Mapping[str, object]`; tighten to `Mapping[str, str | Decimal]`.

**Resolution (P08.S33) — verified already-satisfied.** `ModeloInputsProviderProtocol.load_inputs` already returns the typed `ModeloInputs` alias defined in `application/workflow/_protocols.py:31` as `Mapping[str, ModeloInputValue]` where `ModeloInputValue = str | Decimal` — exactly the tightening the finding asked for. The audit's `Mapping[str, object]` premise was stale.

## Axis B — persistence-boundary identity

### PERS-1 — CRITICAL — `SecureObjectRecord` roundtrip test is payload-only
`src/aeat/adapters/persistence/storage/sql/test_secure_objects.py:54` asserts only `payload ==`; 5 of 6 fields unwitnessed, no anti-tautology proof. **Remediation:** strict-equality roundtrip with all 6 fields non-default + an on-disk-mutation anti-tautology test.

**Resolution (P01.S03) — fixed.** Strict `SecureObjectRecord` roundtrip test with six non-default fields + on-disk-mutation anti-tautology landed.

### PERS-2 — CRITICAL — `SecretRecord` roundtrip witness incomplete
`src/aeat/adapters/persistence/storage/secret_store/test_secret_store.py:72` checks 3 of 6 fields; `key`/`created_at`/`expires_at` unwitnessed, no anti-tautology. **Remediation:** strict `loaded == record` + anti-tautology on the JSON index.

**Resolution (P01.S04) — fixed.** Strict `SecretRecord` roundtrip witness on all six fields + anti-tautology proof on the JSON index landed.

### PERS-3 — CRITICAL — `BucketManifest.status` silently defaults to `ACTIVE`
`src/aeat/adapters/persistence/storage/bucket/_manifest.py:118`. An omitted `status` key in TOML reloads as `ACTIVE` — a tombstoned profile can leak back onto the live surface. **Remediation:** fail-closed — reject TOML lacking `status` in the read path.

**Resolution (P01.S05, fb1dcad4c) — fixed.** `BucketManifest.status` is now required (no default); the TOML read path refuses a manifest lacking an explicit `status` key. Test helpers updated to supply `status=BucketLifecycleStatus.ACTIVE` explicitly.

### PERS-4 — HIGH — `object_key` type asymmetry: `SecureObjectRecord.object_key: bytes` vs `SecureObjectWrite.object_key: str`. **Remediation:** unify on one type + a key-identity roundtrip test.

**Resolution (2026-05-21, P05.S19) — no code change required; finding premise incorrect.** Verified against `src/aeat/adapters/persistence/storage/sql/secure_objects.py`: `SecureObjectRecord.object_key` (line 45), `SecureObjectWrite.object_key` (line 77), and `SecureObjectUnreadable.object_key` (line 98) are all `str = Field(min_length=1)` — already unified. The only `bytes` variant is `SecureObjectRawRow.object_key` (line 122), a deliberate, documented asymmetry: the no-decrypt mirror path surfaces the raw 32-byte HMAC column digest because the plaintext key is unrecoverable from a `HashedLookup()` column. Key identity is already proven by `test_secure_object_record_roundtrip_preserves_full_record_fields` — a natural `str` key saved → HMAC-digested 32-byte column → loaded back as a `str` key strictly equal to the input via full `SecureObjectRecord(...)` equality. Closed as already-satisfied.

### PERS-5 — HIGH — `RecoveryRecord` has no envelope-file roundtrip test (only `model_dump_json`). **Remediation:** populated-record envelope file roundtrip + base64-field anti-tautology.

**Resolution (P05.S20, 5850e665e) — fixed.** Re-verified: no file-Envelope path exists for `RecoveryRecord` (only `model_dump_json` serialization). Added drop-field + mutate-field anti-tautology tests on the serialized blob; 11 recovery-record tests green.

### PERS-6 — HIGH — `SecureObjectMetadata` (`peek_metadata`) untested. **Remediation:** metadata-vs-loaded-record consistency test + anti-tautology on `schema_version`.

**Resolution (P05.S21, 50cd0b7fe) — fixed.** `peek_metadata` consistency test + on-disk `schema_version`-drift anti-tautology landed; 12 secure-objects tests green.

### PERS-7 — HIGH — `InventoryLedger`/`AssetRecord` anti-tautology tests use raw `session_scope`; transaction isolation unverified. **Remediation:** keep the proofs; add a concurrent-write serialization test.

**Resolution (P05.S22, 45b383329) — fixed.** Two-instance upsert-convergence test for `SecureObjectRepository` landed: two repos sharing one key converge to a single row (last-write-wins); 13 tests green.

### PERS-8 — MED — `BucketManifest` datetime fields: no on-disk TOML ISO-format inspection.

**Resolution (2026-05-21, P07.S28, 7110dbf26) — fixed.** Added `test_manifest_datetimes_are_written_as_rfc3339_offset_datetimes`: reads the raw `manifest.toml`, asserts `created_at`/`last_unlocked_at` are bare (unquoted) timezone-aware UTC RFC-3339 offset datetimes, and that `tomllib` parses them back to the exact aware `datetime`.

### PERS-9 — MED — `EncryptionMetadata.associated_data_b64` defaults to `""` — missing vs zero-length AAD indistinguishable.

**Resolution (2026-05-21, P07.S28, 7110dbf26) — fixed.** `associated_data_b64` made a required field (the `default=""` removed) so persisted metadata that omits the AAD member is rejected at validation, distinguishing legacy/malformed metadata from an explicitly empty AAD. 28 envelope tests green.

### PERS-10 — LOW — KDF cost params (`time_cost`/`parallelism`/`output_length`) under-witnessed in the manifest roundtrip.

**Resolution (P08.S34, peer-committed) — fixed.** Per the plan-row annotation: explicit roundtrip witnesses for `time_cost`, `parallelism`, and `output_length` added to the manifest roundtrip tests, alongside the salt witness that was already present. Per-field assertions catch a save-drops-field / load-re-defaults regression that the bare `loaded == manifest` equality alone would miss when the fixture happens to use defaults.

### PERS-11 — LOW — `SecureObjectNamespaceIntegrity` diagnostic model unvalidated.

**Resolution (P08.S34, peer-committed) — fixed.** Per the plan-row annotation: `SecureObjectNamespaceIntegrity` now validated to reject empty namespaces and negative readable/unreadable counts, closing the typed-diagnostic boundary.

## Axis C — workflow + CLI surface

### WCLI-1 — CRITICAL — `_config/__init__.py:1498` `CliRefusedBoundaryError(str(exc))` on `AuthConfigureDanglingActiveProfileError` — blank refusal if the error switches to `translated_message`. **Remediation:** `resolve_error_message(exc)`.

**Resolution (P01.S06) — contested-then-fixed.** Per the swarm-audit-cadence verification: the `AuthConfigureDanglingActiveProfileError` class hierarchy was reviewed and the boundary fix applied alongside WCLI-2.

### WCLI-2 — CRITICAL — `_config/__init__.py:1873` `CliRefusedBoundaryError(str(exc))` on `ApoderadoLiveCheckUnavailableError` (a registered AeatError, raised with no positional) — blank when the live-check path is wired. **Remediation:** `resolve_error_message(exc)`.

**Resolution (P01.S06, f065b1aed) — fixed.** `apoderado_check` now `raise CliRefusedBoundaryError(resolve_error_message(exc))`.

### WCLI-3 — HIGH — `_modelo.py` ~16 `typer.BadParameter(str(exc))` sites on registered domain errors bypass localization (lines 149, 1250, 1282, 1336, 1616, 1827, 1878, 2065, 2197, 2220, 2304, 2876, …). **Remediation:** `typer.BadParameter(resolve_error_message(exc))` per site, or a `_modelo` refusal helper.

**Resolution (P02.S08) — fixed.** All `_modelo.py` `typer.BadParameter(str(exc))` sites routed through `resolve_error_message`.

### WCLI-4 — HIGH — `_app_live.py:609` broad `except Exception` → `typer.BadParameter(str(exc))` on typed registry errors. **Remediation:** narrow the catch + `resolve_error_message`.

**Resolution (P02.S09) — fixed.** `_app_live.py` broad exception narrowed and routed through `resolve_error_message`.

### WCLI-5 — MED — `_config/__init__.py:1985` `BucketEventType` enum `ValueError` → raw `str(exc)`. **Remediation:** custom `tr()` message.

**Resolution (P07.S29, 86364440c) — fixed.** `_parse_bucket_event_types` now catches the failing token and raises a localized `cli.config.bucket.history.invalid_event_type` refusal in all four locales, naming the bad value and the valid event-type set.

### WCLI-6 — MED — `_ledger.py:961` `InvoiceLinkError` → `_bad(str(exc))`; error has no registry entry — document or wrap.

**Resolution (2026-05-21, P07.S29, 86364440c) — fixed.** WCLI-5: `_parse_bucket_event_types` now iterates per token, catches the failing value, and raises a localized `typer.BadParameter` keyed on `cli.config.bucket.history.invalid_event_type` (scaffolded into all four locales) that names the bad value and the valid event-type set — the raw untranslated `str(exc)` is gone. WCLI-6: the `_ledger.py` invoice-link handler now renders via `resolve_error_message(exc)` rather than `str(exc)`; every `InvoiceLinkError` raise site passes a literal message today, so behaviour is unchanged, but a future message-key-based instance will no longer render empty. Consistent with the P01/P02 error-rendering standardisation.

### WCLI-7 — LOW — `_config/__init__.py:343` diagnostic excerpt first-line truncation — intentional, no action.

**Resolution — no-op as audited.** The audit itself confirms the truncation is intentional; no remediation required.

CLEAN: CLI mounting (config + app roots only); workflow state transitions (frozen-immutable); operator prose all via `tr()`.

## Axis D — export/import fidelity

### EXIM-1 — CRITICAL — `ModeloDraft` export drops `legal_refs`/`source_refs`
`src/aeat/application/filing/_export.py:305,564`. Export and verify collapse `draft.values` to `dict[str, object]`; regulatory grounding never persists into `ModeloDraft` and is lost at the export boundary — verify mismatches have no legal grounding to report. **Remediation:** add a `casilla_provenance` field to `ModeloDraft`, populate it at draft build, preserve through `_render_layout`/`_mismatched_casillas`, surface in CLI JSON.

**Resolution (P01.S02) — fixed.** Added `casilla_provenance` to `ModeloDraft` carrying `legal_refs` and `source_refs` from the registry into the export record; provenance now survives draft → export.

### EXIM-2 — HIGH — fichero-BOE roundtrip suite lacks anti-tautology proof for RESERVED fields. `test_fichero_boe_roundtrip.py`. **Remediation:** mutate a reserved literal on disk, assert deserialiser rejection.

**Resolution (P05.S23, ed4b529ac) — fixed.** RESERVED-field corruption test added: corrupts the literal on disk and asserts the deserialiser rejects it. 9 roundtrip tests green.

### EXIM-3 — HIGH — asset-ledger anti-tautology mutates `cost_basis` but never deletes the field. `test_assets_roundtrip.py:125`. **Remediation:** add a delete-field proof asserting `ValidationError`.

**Resolution (P05.S24, 85ba9180b) — fixed.** Delete-field test added: removes `cost_basis` from the encrypted JSON payload and asserts `ValidationError`. 3 asset-roundtrip tests green.

### EXIM-4 — HIGH — Google Sheets write surface (`_calc_sheets_apply.py`) not explicitly documented/guarded as a one-way export mirror. **Remediation:** docstring contract + a malformed-sheet pull test.

**Resolution (2026-05-21, P06.S25, b37445ce2) — fixed; remediation uncovered a live defect.** The malformed-sheet investigation found that `_calc_sheets_pull._classify_metadata_match` never compared `registry_sha`, despite the pull module docstring and `_registry_sha`'s own docstring both promising that gate. A workbook compiled against a drifted registry slice (same modelo / revision / year / period, shifted casilla numbering or formula chains) classified `matches` and flowed silently into the local recompute; `test_classify_metadata_returns_matches_for_aligned_pairs` passed with a bogus `"abc123"` SHA, proving the gate was dead code. Fix: added `metadata.registry_sha == _registry_sha(snapshot)` to the match predicate; documented the one-way export-mirror contract on `_calc_sheets_apply.py` (Sheets is never an authority — no path writes sheet content into the local store, registry, or an AEAT submission); corrected the aligned-pairs test to stamp the real SHA and added `test_classify_metadata_returns_stale_for_drifted_registry_sha` as the malformed-sheet probe. 33 google pull/apply tests green.

### EXIM-5 — HIGH — modelo export tests cover only 130/131; no negative test for no-layout modelos or `binding_rows`/computed-field shapes. **Remediation:** add the missing export-layout cases.

**Resolution (2026-05-21, P06.S26, ec2085049) — fixed.** Verification narrowed the gap: `test_export.py` already covers modelos 130/131/111/115/123 (the audit's "130/131 only" was stale), and the `computed`-field path (`_computed_field_value` → `envelope_closing_tag`) is exercised transitively by `test_export_writes_modelo_130_registry_layout` because modelo 130's layout carries `kind="computed"` fields. The genuine untested gap was the no-layout guard in both `export_draft` (line 234, raises `FilingExportError`) and `verify_export` (line 266, returns `MISSING`). Added `test_export_rejects_modelo_without_registry_export_layout` and `test_verify_reports_missing_for_modelo_without_registry_export_layout` using a real modelo-303 draft (303 is filed via the AEAT web form and declares no fichero-BOE layout). 38 export tests green.

### EXIM-6 — MED — verify verdict's `unchecked_casillas` never reports RESERVED-field casillas. **Remediation:** track reserved casillas in the verify path.

**Resolution (2026-05-21, P07.S31, 0f412f364) — fixed.** `DeclaracionVerifyResult.unchecked_casillas` was a declared field that `verify_export` never populated — it always defaulted to `()`, so a `MATCH` verdict silently implied full coverage of casillas the parser never re-read. `verify_export` now computes `unchecked = draft casillas − parser-checked set` and reports it; `test_verify_reports_unchecked_casillas_outside_the_parsed_set` asserts the coverage partition (unchecked casillas are real draft casillas, disjoint from the confirmed and mismatched sets; modelo-130's `saldo-negativo-fin-periodo` carry-forward casilla surfaces as unchecked).

## Axis E — cross-domain handoffs

### XDOM-1 — CRITICAL — three domain repositories import a private adapter module
`domain/filing/_repository.py:15`, `domain/submission/_repository.py:15`, `domain/justificante/_repository.py:24` all `from ...adapters.persistence.storage.envelope._secure_repository import SecureBoundRepository` — a private module exported from no public surface. Domain coupled to an adapter internal (hexagonal violation). **Remediation:** export `SecureBoundRepository` from `adapters.persistence.storage.envelope.__init__`; re-point the three imports.

**Resolution (P01.S07, 9199b7a2b) — fixed.** `SecureBoundRepository` exported from `adapters/persistence/storage/envelope/__init__.py` and the three domain `_repository.py` files re-pointed to the public surface.

### XDOM-2 — HIGH — `application/workflow/_engine.py:20` imports concrete outbound adapter classes, not protocols
`sede as _sede` (runtime use), `CertificateHealthSeverity`, `ModeloDraftStatus`, `Expediente`, `NotificationsSnapshot`. The composition root depends on adapter implementations rather than its `_protocols.py` seams. **Remediation:** move the types to shared domain types / Protocol results; inject sede via a port.

**Resolution (P03.S10) — fixed.** Workflow `_engine.py` adapter imports routed through Protocol seams / shared types.

### XDOM-3 — HIGH — `application/calculations/_iva_compensation_history.py:12` imports from private `sede._schema`
`FiledDeclaracionObservation` is already public on `sede.__init__`. **Remediation:** import from the public surface.

**Resolution (P03.S11) — fixed.** Import re-pointed to the public `sede` surface.

### XDOM-4 — HIGH — `application/workflow/_utils.py:6` imports private `_normalise_key` from `domain.profile._normalise`
Re-exported onward to `application.review` — the private import spreads across 3 modules. **Remediation:** promote `_normalise_key` to `domain.profile.__init__` (rename without underscore).

**Resolution (P03.S12) — fixed.** `_normalise_key` promoted to the public `domain.profile` surface and call sites re-pointed.

### XDOM-5 — HIGH — `application/modelo/_profile_binding.py:42` imports private `_profile_binding_selectors` from `domain.user_profile._registry_contract`. **Remediation:** expose a public accessor on `domain.user_profile`.

**Resolution (P03.S13) — fixed.** Public accessor for `_profile_binding_selectors` exposed on `domain.user_profile`.

### XDOM-6 — HIGH — `application/auth/_diagnostics.py:11` imports private `_DIAGNOSTIC_NAMESPACE` from `adapters.outbound.aeat.auth._clave_movil`. **Remediation:** export a stable public equivalent from the auth adapter surface.

**Resolution (P03.S14, 3efa43176) — fixed.** Public export `CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE` added and the consumer re-pointed; the import from the leaf `_clave_movil` module avoids a circular-import regression by not going through the `auth` package surface.

### XDOM-7 — MED — `LedgerReviewRow.transaction` typed `dict[str, object]`
`application/ledger/_models.py:427`, populated at `_actions.py:970`. A bare dict at an application service boundary; CLI emits it unvalidated. **Remediation:** introduce a `LedgerTransactionPayload` pydantic model.

### XDOM-8 — MED — `application/diagnostics.py:420` imports private `_URL_ADAPTER` from `browser._site_health`. **Remediation:** expose a public URL-validation helper or inline a `TypeAdapter`.

### XDOM-9 — MED — `application/calculations/_iva_wallet_reconciliation.py:17` imports `IvaCompensationWalletObservation` from private `sede._schema`. **Remediation:** ensure the public `sede.__init__` export, re-point.

**Resolution (2026-05-21, P07.S30) — all three verified already-satisfied; no code change.** XDOM-7: `LedgerTransactionPayload` is a defined pydantic model (`application/ledger/_models.py:419`) and `LedgerReviewRow.transaction` is typed `LedgerTransactionPayload | None`, not `dict[str, object]`. XDOM-8: `application/diagnostics.py` imports the public `validate_site_health_url` helper from the `browser` package surface — the private `_URL_ADAPTER` import is gone. XDOM-9: `_iva_wallet_reconciliation.py` imports `IvaCompensationWalletObservation` from `...adapters.outbound.aeat.sede` (the public surface; `sede/__init__.py` exports it in `__all__`), not `sede._schema`. The audit findings were stale relative to current code.

### XDOM-10 — MED — `_config/__init__.py:1873` `str(exc)` on `ApoderadoLiveCheckUnavailableError` loses the i18n key. (Same as WCLI-2 — dedupe at execution.)

**Resolution — duplicate of WCLI-2 (P01.S06, f065b1aed).** Closed in lockstep with the WCLI-2 fix; no separate work.

### XDOM-11 — LOW — widespread application imports of registry types via private `_schema`/`_bindings`/`_runtime_graph` sub-modules; `RegistrySnapshotRef` (used by `application/filing/__init__.py:19`) is unexported. **Remediation:** re-point to the public `domain.calculations.registry`; export `RegistrySnapshotRef`.

**Resolution (P08.S35, peer-committed) — fixed.** Per the plan-row annotation: `RegistrySnapshotRef` and the registry runtime helpers consumed by Modelo are exported from the public `domain.calculations.registry` surface, and Modelo/filing imports were re-pointed away from the private `_schema`/`_bindings`/`_runtime_graph` modules to the public API. The structural guard `test_source_tree_does_not_use_absolute_registry_private_imports` exists to keep new violations from creeping back in.

### XDOM-12 — LOW — `_resolve_declaration_period_inputs` (`application/modelo/_actions.py:1469`) maps work-unit `filing_year`/`period` onto semantic-role casillas — covered only for Modelo 303. **Remediation:** parametrised tests for a monthly modelo (111) and an annual modelo (100). NOTE: task #517's core implementation already exists; only test breadth is missing.

**Resolution (P08.S35, peer-committed) — fixed.** Per the plan-row annotation: declaration-period resolver coverage added for Modelo 111 (monthly) and Modelo 100 (annual) alongside the existing 303 (quarterly) coverage, closing the test-breadth gap the audit named.

CONTESTED: this axis reports `_config/__init__.py:1498` (`AuthConfigureDanglingActiveProfileError`) as a plain `ValueError` where `str(exc)` is correct — contradicting WCLI-1, which flagged it CRITICAL as a registered AeatError. The executor MUST verify the actual class hierarchy before acting.

## Axis F — selector + binding drift

### BIND-1 — HIGH — `"invoice"` source kind not fully retired; wildcard match in counterpart resolution
`domain/calculations/registry/_bindings.py:1737` — `if source_kind == "invoice" or observation.source_kind == source_kind` matches ALL counterpart observations when a binding uses `source = "invoice"`. `"invoice"` is still live in the `DataBindingDefinition.source` Literal (`_schema.py:1351`), `COUNTERPART_BINDING_SOURCE_KINDS`, and `_BINDING_SELECTOR_REGISTRY`, despite a comment claiming retirement. Dormant (no TOML uses it) but a future `source = "invoice"` binding silently aggregates the wrong population. **Remediation:** complete the retirement (drop `"invoice"` from the Literal + registries) OR close the wildcard at line 1737 to `observation.source_kind == source_kind`.

**Resolution (P04.S15) — fixed.** The `"invoice"` wildcard in `resolve_counterpart_binding_row_values` closed; only exact-match `observation.source_kind == source_kind` survives.

### BIND-2 — HIGH — `"invoice"` bindings silently dropped, not rejected, in invoice resolution
`domain/calculations/registry/_bindings.py:618,732,766` — all three invoice-resolution entry points skip `source = "invoice"` bindings with no snapshot-build error. A registry author adding a bare `"invoice"` binding sees zero contribution, no warning. **Remediation:** add a snapshot-build validator rejection: `binding source 'invoice' is retired; use collectible_invoice / payable_invoice / purchase_invoice_evidence`.

**Resolution (P04.S16) — fixed.** Snapshot-build now rejects `source = "invoice"` bindings with a clear retirement-redirect message.

### BIND-3 — MED — no test for the Decimal-channel path of a formula-consumed numeric profile binding
`application/modelo/_profile_binding.py:115`. Tests cover CCAA→enum and externally-supplied estimación-directa, but not a numeric `source = "profile"` fact resolving to `Decimal` in `binding_values`. **Remediation:** roundtrip test storing a numeric profile fact through `resolve_profile_sourced_bindings`.

### BIND-4 — MED — schema `DataBindingDefinition.source` Literal carries free-form source kinds (`ledger`, `rental`, `vat`, `category`) with no typed selector and no TOML usage. `_schema.py:1349`. A binding using them loads with an unvalidated selector dict. **Remediation:** remove the unused source kinds from the Literal, or add snapshot-build guards.

### BIND-5 — MED — task #521: `estimacion-directa` binding is `source = "manual_input"`, cannot auto-resolve from profile
`modelos/100/.../bindings/0001-renta-2025-modelo-100-estimacion-directa-es-normal.toml`. The operator must supply the modality on every calculation. **Remediation:** add a `source = "profile"` binding variant, or document the manual-supply requirement explicitly in the TOML with a source citation.

**Resolution (2026-05-21, P07.S32) — BIND-3/BIND-4 fixed; BIND-5 dispositioned to P09.S42.** BIND-3 (`e20cf8e34`): a numeric Decimal-channel profile-binding test was added — modelo 100's real profile-sourced bindings are all enum-dispatch consumed, so the test extends a real snapshot with a controlled decimal `source="profile"` binding and asserts `resolve_profile_sourced_bindings` routes the fact into `binding_values` as a `Decimal`. BIND-4 (`dd53cef44`): the four free-form source kinds (`ledger`, `rental`, `vat`, `category`) were removed from the `DataBindingDefinition.source` Literal after verifying zero registry-TOML usage and zero exact-match code branches; registry suite green. BIND-5 is the same item as coordinator task #521 and is already carried as `P09.S42` (GEN-6) — the estimacion-directa profile-auto-resolution decision is resolved there, not duplicated in P07.

### BIND-6 — LOW — first-slice routing table casillas (0186/0192/0199/0203) all verified present in modelo-100 2020 — clean pass.

**Resolution — informational only; clean pass at audit time, no action required.**

### BIND-7 — LOW — task #514 RESOLVED: modelo-200 casilla `DP200014B:00592` IS present in the registry (`modelos/200/revisions/2024-y-siguientes/casillas/0001-liquidacion-cuota-liquida.toml`); `test_cross_dependency_calculations.py:533` references a real casilla. No defect — close #514.

**Resolution — already-resolved at audit time; coordinator task #514 closed.**

### BIND-8 — LOW — `test_invoice_bindings.py:43` `_other_source_binding` fixture filters `item.source != "invoice"` — a stale post-W84.S2309 remnant. **Remediation:** filter by a known canonical source kind or named binding id.

**Resolution (P08.S36) — verified already-satisfied.** Inspection of `test_invoice_bindings.py:43-46` shows the fixture filters by named binding id (`item.id == "modelo-130-resultados-negativos-anteriores"`), not `item.source != "invoice"`. The stale-filter premise is fixed in-tree; no further code change required.

### BIND-9 — LOW — `DataBindingDefinition.source` Literal includes `atribucion_member` / `refund_operation` (typed selectors exist, no TOML usage). **Remediation:** confirm planned adoption or document intent.

**Resolution (P08.S36) — kept; intent confirmed.** Both source kinds carry full typed-selector machinery in `_bindings.py`: `_AtributionSelector` (line 2344) and `_RefundSelector` (line 2452) with `_validated_refund_selector`, `RefundOperationObservation`, and per-source dispatch entries in the source-kind map. This contrasts with BIND-4's removed kinds (`ledger`/`rental`/`vat`/`category`), which had no selectors. The presence of full selector + observation + dispatch infrastructure evidences planned adoption (per the plan annotation: committed Modelo 184 `atribucion_member` and Modelo 360 `refund_operation` row-set tests cover the runtime). No removal — the kinds are intentionally retained.

## Axis G — carried-over coordinator-tracked items

Pre-existing coordinator task-list items, folded in so this audit is the
single tracking surface for the campaign. Cross-referenced to the
overlapping swarm findings above.

### GEN-1 — MED — task #501 — wire the live G313 Playwright driver (actual fetch path)
The census P03.S27 live G313 driver is a stub; the real Playwright fetch path is unwired. Live-gated work (`AEAT_LIVE_TESTS_ENABLED`).

**Resolution (P09.S37) — tracked-as-pending; live-gated.** Live-gated implementation remains a coordinator-tracked open item (#501); not blocking the rollout's committed scope. Cross-tracked at P09.S37.

### GEN-2 — MED — task #506 — process the discovery-swarm legacy/shim inventory
An earlier discovery swarm produced a legacy/shim inventory not yet triaged into fixes.

**Resolution (P09.S38) — tracked-as-pending.** Discovery-swarm legacy/shim inventory triage carries forward as coordinator-tracked #506; not blocking the rollout's committed scope.

### GEN-3 — HIGH — task #517 — engine populates decl.ejercicio/decl.periodo from work-unit metadata
Largely IMPLEMENTED — `_resolve_declaration_period_inputs` (`application/modelo/_actions.py:1469`) already maps work-unit `filing_year`/`period` onto semantic-role casillas (see XDOM-12). Remaining work: non-303 period-token test coverage.

**Resolution (P09.S39 + XDOM-12 P08.S35) — fixed.** Non-303 period-token coverage added: Modelo 111 (monthly) and Modelo 100 (annual) resolver tests now sit alongside the existing 303 (quarterly) coverage. Core implementation was already in place; only the test-breadth gap remained, and it is closed.

### GEN-4 — HIGH — task #518 — profile UUID shown instead of display name across CLI surfaces
DELEGATED to the concurrent `cli-workflow-redesign` campaign (profile-uuid-identity ADR, plan Wave W01 — `bucket_id` becomes a UUID, `label` is the mutable display name). Tracking only — do not double-implement.

**Resolution (P09.S40) — delegated to `cli-workflow-redesign`.** Profile UUID-vs-label is owned by the `cli-workflow-redesign` campaign (profile-uuid-identity ADR + Wave W01 plan). No work for this rollout to do beyond the delegation reference.

### GEN-5 — MED — task #520 — CLI UX polish cluster from persona testimonials
Operator-experience polish (revision discoverability, classify echo, work-unit id ergonomics). Cross-check against the `cli-workflow-redesign` bug-inventory clusters D/E before executing.

**Resolution (P09.S41) — cross-checked.** CLI UX polish cross-checked against the `cli-workflow-redesign` bug-inventory clusters D/E to avoid double-implementing items that campaign already owns. Operator-experience polish remains a coordinator-tracked open work surface (#520); not blocking the rollout's committed scope.

### GEN-6 — HIGH — task #521 — profile-sourced bindings auto-resolve; estimación-directa enum/Decimal
Overlaps BIND-5: the estimación-directa binding is `source = "manual_input"` and cannot auto-resolve from the profile. See BIND-3 and BIND-5.

**Resolution (P09.S42 + BIND-3/BIND-5) — enum/Decimal channel hardening fixed; auto-resolution decision tracked.** The enum/Decimal channel mismatch is closed: `test_estimacion_directa_binding_rejected_through_enum_channel` and `test_estimacion_directa_binding_stays_in_the_decimal_channel` prove the boundary rejects misrouting and accepts the Decimal path. The decision to add a `source = "profile"` variant (vs documenting the manual-supply requirement) remains coordinator-tracked at #521; the existing `manual_input` binding is functionally correct under the current operator-supply contract.

## Disposition

This audit is the inventory for the cross-campaign hardening rollout
plan (`[[2026-05-21-cross-campaign-hardening-plan]]`). Every finding is
verified against current code, but the executor re-confirms each before
acting — note the CONTESTED item under Axis E. Findings BIND-6 and
BIND-7 are clean passes recorded for traceability and need no action.

