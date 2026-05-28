---
tags:
  - '#plan'
  - '#codebase-solidification'
date: '2026-05-28'
tier: L4
related:
  - '[[2026-05-28-codebase-solidification-adr]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `codebase-solidification` `Codebase solidification recurring hardening epic` plan

## Epic intent

Solidify the AEAT production codebase by recurring hardening passes
that close drift between the canonical centralized modules already
present in the tree and their actual enrollment across `src/aeat/`.
The epic is associated with the `chore/eliminate-shims` worktree on
this repository, which owns the agent-fleet coordination surface
that dispatches the recurring eight-axis audit swarm. The horizon is
open-ended; the closing condition is three consecutive Waves
producing zero fresh findings across all nine axes (A1 exceptions,
A2 logging, A3 locale, A4 pydantic boundaries, A5 duplication, A6
stubs / dead code, A7 hardcoded values / enum bypass, A8 typecheck
escapes, P09 test-suite semantic / coverage). Wave authorship and
Step execution are shared across the persistent backbone team
(legal-authority, adr-specialist, coder-alpha / beta / gamma,
generalist, commit-bot, reader pool); no single human reviewer is in
the loop, per project memory `autonomous_pm_no_human_loop`.

## Wave `W01` - close the inaugural 2026-05-27 audit findings

Wave 1 lands a Step for every finding surfaced by the inaugural
audit, paired with a verification Step that adds or strengthens a
real-behavior test. Wave 1 closes when every Phase reaches 100% Step
closure; the swarm re-audit that authorises Wave 2 dispatches when
Wave 1 reaches the 80%-closed threshold. Authorising documents are
declared in the plan's `related:` frontmatter and inherited by every
Step.

### Phase `W01.P01` - enroll the centralized exception hierarchy

Land an `AeatError` subclass for every stdlib raise the A1 audit
surfaced; route every `except Exception` swallow through
`build_error_envelope`; eliminate the two `class Foo(Exception)`
declarations that bypass the registry. Each fix Step is paired with
a verification Step that asserts the new subclass is registered in
`ERROR_REGISTRY` and that the raise round-trips through the
envelope.

- [x] `W01.P01.S01` - subclass `TaxationComparisonError` from `CoreError` and register an `ErrorCode`; `src/aeat/application/modelo/_taxation_comparison.py`.
- [x] `W01.P01.S02` - add real-behavior test asserting `TaxationComparisonError` is in `ERROR_REGISTRY` and round-trips through `build_error_envelope`; `src/aeat/application/modelo/test_taxation_comparison.py`.
- [x] `W01.P01.S03` - subclass `_BinaryXlsConversionError` from `CoreError`; `src/aeat/domain/calculations/registry/_workbook_parity.py`.
- [x] `W01.P01.S04` - add real-behavior test asserting `_BinaryXlsConversionError` registry binding; `src/aeat/domain/calculations/registry/test_workbook_parity.py`.
- [x] `W01.P01.S05` - introduce `ExportFormatError(CoreError)` and `ExportFieldError(CoreValidationError)`; `replace the seven `ValueError` / `raise` sites; `src/aeat/application/export/_tabular.py`.
- [x] `W01.P01.S06` - add real-behavior test asserting export error envelope and i18n for every fixed raise; `src/aeat/application/export/test_tabular.py`.
- [x] `W01.P01.S07` - introduce `IvaCompensationModeloError(CoreError)`; `replace the `ValueError`; `src/aeat/application/calculations/_iva_compensation_history.py`.
- [x] `W01.P01.S08` - add real-behavior test asserting IVA compensation modelo error envelope; `src/aeat/application/calculations/test_iva_compensation_history.py`.
- [ ] `W01.P01.S09` - introduce `WorkflowInputMismatchError(CoreError)` or reuse `CoreValidationError`; `src/aeat/application/modelo/_actions.py`.
- [ ] `W01.P01.S10` - add real-behavior test asserting workflow-input-mismatch envelope and registry binding; `src/aeat/application/modelo/test_actions.py`.
- [x] `W01.P01.S11` - introduce `AdapterTypeError(CoreError)` or reuse `McpLaunchError`; `replace the `TypeError`; `src/aeat/adapters/outbound/aeat/verify/__init__.py`.
- [x] `W01.P01.S12` - add real-behavior test asserting verify adapter type-error envelope; `src/aeat/adapters/outbound/aeat/verify/test_verify.py`.
- [x] `W01.P01.S13` - introduce `BrowserAdapterTypeError(CoreError)`; `replace the three `TypeError` raises across `_renta_web_open.py`, `_nif_iva_check.py`, `_groi_check.py`; `src/aeat/adapters/outbound/aeat/sede/_errors.py`.
- [x] `W01.P01.S14` - add real-behavior test asserting browser-adapter-type-error envelope and registry binding; `src/aeat/adapters/outbound/aeat/sede/test_browser_errors.py`.
- [x] `W01.P01.S15` - introduce `StorageCorruptionError(CoreError)`; `replace the `TypeError`; `src/aeat/adapters/outbound/storage/_local.py`.
- [x] `W01.P01.S16` - add real-behavior test asserting storage-corruption-error envelope round-trip; `src/aeat/adapters/outbound/storage/test_local.py`.
- [x] `W01.P01.S17` - introduce `ObservationKeyError(CoreValidationError)`; `replace the five `ValueError` raises at observation-key validation; `src/aeat/application/calculations/_observations_repository.py`.
- [x] `W01.P01.S18` - add real-behavior test asserting observation-key-error envelope for each replaced raise; `src/aeat/application/calculations/test_observations_repository.py`.
- [x] `W01.P01.S19` - introduce `AuthDiagnosticPhoneStateError(CoreValidationError)`; `replace the raw `ValueError(phone_state)`; `src/aeat/application/auth/_diagnostics.py`.
- [x] `W01.P01.S20` - add real-behavior test asserting auth-diagnostic phone-state envelope; `src/aeat/application/auth/test_diagnostics.py`.
- [x] `W01.P01.S21` - introduce `ProfileKeysRegistrationError(CoreError)`; `replace the `RuntimeError`; `src/aeat/domain/profile/_keys.py`.
- [x] `W01.P01.S22` - add real-behavior test asserting profile-keys-registration envelope on double registration; `src/aeat/domain/profile/test_keys.py`.
- [ ] `W01.P01.S23` - introduce `PensionReduccionError(CoreValidationError)`; `replace the six `ValueError` raises at pension reducción computation; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W01.P01.S24` - add real-behavior test asserting pension-reducción error envelope at every replaced raise; `src/aeat/entrypoints/cli/test_modelo.py`.
- [x] `W01.P01.S25` - introduce `BindingPrefillTypeError(CoreValidationError)`; `replace the `TypeError`; `src/aeat/application/calculations/_binding_prefill.py`.
- [x] `W01.P01.S26` - add real-behavior test asserting binding-prefill-type-error envelope; `src/aeat/application/calculations/test_binding_prefill.py`.
- [x] `W01.P01.S27` - introduce `WizardAnswerTypeError(CoreValidationError)`; `replace every coercion `TypeError` / `ValueError` raise (15+ sites); `src/aeat/application/wizard/_setup_answers.py`.
- [x] `W01.P01.S28` - add real-behavior test asserting wizard-answer-type-error envelope at every replaced raise; `src/aeat/application/wizard/test_setup_answers.py`.
- [ ] `W01.P01.S29` - confirm `RecoveryVerificationError` subclasses `AeatError`; `narrow the `except Exception` and reraise typed; `src/aeat/adapters/persistence/storage/master_key/_recovery_facade.py`.
- [ ] `W01.P01.S30` - add real-behavior test asserting recovery-facade envelope under each upstream exception class; `src/aeat/adapters/persistence/storage/master_key/test_recovery_facade.py`.
- [ ] `W01.P01.S31` - narrow the `except Exception` to specific `AeatError` subtypes; `remove the no-active-profile reclassification; `src/aeat/entrypoints/cli/_ledger.py`.
- [ ] `W01.P01.S32` - add real-behavior test asserting non-NoActiveProfileError exceptions propagate with their original envelope; `src/aeat/entrypoints/cli/test_ledger.py`.
- [ ] `W01.P01.S33` - narrow the autocomplete `except Exception` to specific `AeatError` subtypes; `log others at DEBUG via observability sink; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W01.P01.S34` - add real-behavior test asserting autocomplete propagates AeatError envelope and observability records non-AeatError; `src/aeat/entrypoints/cli/test_modelo.py`.
- [x] `W01.P01.S35` - wrap each of the seven `except Exception` clauses in `_record_unhandled` with `build_error_envelope`; `assign a synthetic `UNHANDLED_INTERNAL` `ErrorCode`; `src/aeat/application/workflow/_engine.py`.
- [x] `W01.P01.S36` - add real-behavior test asserting `_record_unhandled` envelopes carry an `ErrorCode` for every original exception class; `src/aeat/application/workflow/test_engine.py`.
- [ ] `W01.P01.S37` - narrow the four config-CLI `except Exception` catches to `AeatError`; `wrap unexpected exceptions in `ConfigBoundaryError(CoreError)`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [ ] `W01.P01.S38` - add real-behavior test asserting config-CLI envelope on AeatError and ConfigBoundaryError on unexpected; `src/aeat/entrypoints/cli/_config/test_config.py`.
- [x] `W01.P01.S39` - introduce `NamespaceRegistryError(CoreError)`; `replace the twelve `ValueError` raises at boot-time invariant checks; `src/aeat/adapters/persistence/storage/_namespace_registry.py`.
- [x] `W01.P01.S40` - add real-behavior test asserting namespace-registry-error envelope at every replaced invariant; `src/aeat/adapters/persistence/storage/test_namespace_registry.py`.
- [x] `W01.P01.S41` - introduce `IvaWalletReconciliationError(CoreError)`; `replace the four `ValueError` raises; `src/aeat/application/calculations/_iva_wallet_reconciliation.py`.
- [x] `W01.P01.S42` - add real-behavior test asserting IVA-wallet-reconciliation envelope at every replaced raise; `src/aeat/application/calculations/test_iva_wallet_reconciliation.py`.
- [x] `W01.P01.S43` - introduce `AggregationConfigError(CoreError)`; `replace the nine `ValueError` raises at aggregation-service composition; `src/aeat/application/aggregation/_service.py`.
- [x] `W01.P01.S44` - add real-behavior test asserting aggregation-config envelope at every replaced raise; `src/aeat/application/aggregation/test_service.py`.
- [x] `W01.P01.S45` - introduce `DiagnosticModelError(CoreValidationError)`; `replace the `ValueError` / `TypeError` raises in `DiagnosticCheck` invariants; `src/aeat/application/diagnostics.py`.
- [x] `W01.P01.S46` - add real-behavior test asserting diagnostic-model envelope at every replaced raise; `src/aeat/application/test_diagnostics.py`.
- [x] `W01.P01.S47` - introduce `ClassificationRuleError(CoreValidationError)`; `replace the regex-validation `ValueError`; `src/aeat/domain/transactions/_classification_rule.py`.
- [x] `W01.P01.S48` - add real-behavior test asserting classification-rule envelope on invalid regex; `src/aeat/domain/transactions/test_classification_rule.py`.

### Phase `W01.P02` - enroll the centralized logging factory

Replace every raw `logging.getLogger` in production code with
`get_logger`; route every observability sink through a helper that
installs `SecretScrubbingFilter` before attachment; eliminate
`print()` / `sys.stdout.write` / `sys.stderr.write` in production
paths; centralize third-party-logger silencing in
`configure_logging()`. Each fix Step is paired with a verification
Step that asserts secret scrubbing actually fires on records emitted
through the affected logger.

- [ ] `W01.P02.S49` - replace module-level `_LOGGER = logging.getLogger(__name__)` with `get_logger(__name__)`; `src/aeat/entrypoints/cli/_stdio.py`.
- [ ] `W01.P02.S50` - add real-behavior test asserting CLI stdio logger applies `SecretScrubbingFilter` to NIF-shaped records; `src/aeat/entrypoints/cli/test_stdio.py`.
- [ ] `W01.P02.S51` - hoist the function-body `_log = logging.getLogger(__name__)` to module-level `get_logger(__name__)`; `src/aeat/entrypoints/cli/_overview.py`.
- [ ] `W01.P02.S52` - add real-behavior test asserting overview logger scrubs taxpayer data; `src/aeat/entrypoints/cli/test_overview.py`.
- [ ] `W01.P02.S53` - replace the inline `_logging.getLogger(__name__)` with module-level `get_logger`; `src/aeat/core/errors/_registry.py`.
- [ ] `W01.P02.S54` - add real-behavior test asserting error-registry resolution-failure debug log scrubs sensitive context; `src/aeat/core/errors/test_registry.py`.
- [x] `W01.P02.S55` - replace the inline `logging.getLogger(__name__).warning` with module-level `get_logger`; `src/aeat/core/observability/_sink.py`.
- [x] `W01.P02.S56` - add real-behavior test asserting sink-failure warning carries scrubbed exception traceback; `src/aeat/core/observability/test_sink.py`.
- [ ] `W01.P02.S57` - add `pdfminer` to the `loggers` block of `configure_logging()` dictConfig; `delete the in-place mutation; `src/aeat/adapters/inbound/pdf/_pdfplumber.py`.
- [ ] `W01.P02.S58` - add real-behavior test asserting `pdfminer` logger level is governed by `aeat.core.logging` dictConfig; `src/aeat/core/test_logging.py`.
- [ ] `W01.P02.S59` - delete the duplicated `pdfminer` mutation; `rely on the centralized `loggers` block; `src/aeat/domain/calculations/registry/_record_design.py`.
- [ ] `W01.P02.S60` - extend the dictConfig test to confirm both `_pdfplumber.py` and `_record_design.py` paths defer to centralized config; `src/aeat/core/test_logging.py`.
- [ ] `W01.P02.S61` - replace the root-logger level-patch traversal with a `set_log_level(level)` helper exposed by `aeat.core.logging`; `src/aeat/entrypoints/cli/_log_levels.py`.
- [ ] `W01.P02.S62` - add real-behavior test asserting the helper updates root + every attached handler under every dictConfig variant; `src/aeat/entrypoints/cli/test_log_levels.py`.
- [ ] `W01.P02.S63` - install `SecretScrubbingFilter` on the sink before `root_logger.addHandler(sink)`; `expose `attach_run_sink(sink)` helper in `aeat.core.logging`; `src/aeat/core/observability/_context.py`.
- [ ] `W01.P02.S64` - add real-behavior test asserting JSONL run sink records are scrubbed before persistence; `src/aeat/core/observability/test_context_propagation.py`.
- [ ] `W01.P02.S65` - replace the auth-waiting `print(line, file=stream, flush=True)` with a typed CLI renderer routed through a structured logger; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.
- [ ] `W01.P02.S66` - add real-behavior test asserting auth waiting messages never carry unmasked verification codes through stderr; `src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py`.
- [ ] `W01.P02.S67` - replace `sys.stdout.write` with an injected render primitive; `src/aeat/application/wizard/_prompter.py`.
- [ ] `W01.P02.S68` - add real-behavior test asserting wizard prompter routes through the structured render path; `src/aeat/application/wizard/test_prompter.py`.
- [ ] `W01.P02.S69` - guard the module-level `print(...)` in the normatives docstring example behind `if __name__ == "__main__":` or convert to a proper doctest block; `src/aeat/domain/normatives/__init__.py`.
- [ ] `W01.P02.S70` - add real-behavior test asserting importing `aeat.domain.normatives` produces no stdout output; `src/aeat/domain/normatives/test_init.py`.
- [ ] `W01.P02.S71` - guard the LLM-adapter docstring example `print(response.text)` behind `if __name__ == "__main__":`; `src/aeat/adapters/outbound/llm/__init__.py`.
- [ ] `W01.P02.S72` - add real-behavior test asserting importing `aeat.adapters.outbound.llm` produces no stdout output; `src/aeat/adapters/outbound/llm/test_init.py`.
- [ ] `W01.P02.S73` - add `pikepdf._core` to `configure_logging()` `loggers` block; `remove the bootstrap-time mutation; `src/aeat/__init__.py`.
- [ ] `W01.P02.S74` - add real-behavior test asserting `pikepdf._core` level survives a `configure_logging()` re-call; `src/aeat/core/test_logging.py`.
- [ ] `W01.P02.S75` - attach `SecretScrubbingFilter` to the `root_logger.getLogger()` sink path; `src/aeat/core/observability/_context.py`.
- [ ] `W01.P02.S76` - add real-behavior test asserting run-scoped records pass through scrubbing before reaching the JSONL directory; `src/aeat/core/observability/test_sink_redaction.py`.

### Phase `W01.P03` - enroll the centralized locale surface

Route every operator-visible string through `tr()` / `Translatable`;
populate `translated_message=` on every `SedeError` raise that
reaches the CLI envelope; eliminate bare-string `typer.echo` /
f-string emits at the CLI boundary. Each fix Step is paired with a
verification Step that asserts the locale catalogue carries the key
and the operator surface emits the localized payload.

- [ ] `W01.P03.S77` - replace the bare `_bad(f"draft id ...")` with `tr("cli.common.errors.draft_id_not_found", draft_id=draft_id)`; `src/aeat/entrypoints/cli/_common.py`.
- [ ] `W01.P03.S78` - add real-behavior test asserting the draft-id-not-found surface emits the localized payload; `src/aeat/entrypoints/cli/test_common.py`.
- [ ] `W01.P03.S79` - route the no-active-profile dict / text emit through `_no_active_profile_refusal()` and `tr()` keys; `src/aeat/entrypoints/cli/_common.py`.
- [ ] `W01.P03.S80` - add real-behavior test asserting no-active-profile output is localized in text and JSON channels; `src/aeat/entrypoints/cli/test_common.py`.
- [ ] `W01.P03.S81` - add `cli.ledger.errors.id_prefix_unknown` catch-all and route the raw-message passthrough through `tr()`; `src/aeat/entrypoints/cli/_ledger.py`.
- [ ] `W01.P03.S82` - add real-behavior test asserting ledger id-prefix fallthrough emits the localized payload; `src/aeat/entrypoints/cli/test_ledger.py`.
- [ ] `W01.P03.S83` - wrap the eight `describe` label rows in `tr("cli.app.modelo.describe.label_*")` keys; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W01.P03.S84` - add real-behavior test asserting `aeat app modelo describe` labels are localized per output language; `src/aeat/entrypoints/cli/test_modelo.py`.
- [ ] `W01.P03.S85` - route the cross-casilla-invariant finding `message=` through `tr("application.modelo.findings.cross_casilla_invariant_violated", ...)`; `src/aeat/application/modelo/_actions.py`.
- [ ] `W01.P03.S86` - add real-behavior test asserting verification-report cross-casilla finding is localized in text and JSON; `src/aeat/application/modelo/test_actions.py`.
- [ ] `W01.P03.S87` - route the cross-casilla `next_action=` through `tr("application.modelo.findings.cross_casilla_invariant_next_action", predicate_id=...)`; `src/aeat/application/modelo/_actions.py`.
- [ ] `W01.P03.S88` - extend the verification-report test to confirm cross-casilla `next_action` localization; `src/aeat/application/modelo/test_actions.py`.
- [ ] `W01.P03.S89` - route the registry-snapshot-unresolved finding through `tr("application.modelo.findings.registry_snapshot_unresolved", ...)`; `src/aeat/application/modelo/_actions.py`.
- [ ] `W01.P03.S90` - add real-behavior test asserting registry-snapshot-unresolved is localized in verification output; `src/aeat/application/modelo/test_actions.py`.
- [ ] `W01.P03.S91` - route the DT12-reducción advisory `message=` through `tr("application.modelo.findings.dt12a_reduccion_possible", ...)`; `src/aeat/application/modelo/_actions.py`.
- [ ] `W01.P03.S92` - add real-behavior test asserting DT12-reducción advisory is localized; `src/aeat/application/modelo/test_actions.py`.
- [ ] `W01.P03.S93` - route the IVA-wallet `next_action=` through `tr("application.modelo.findings.iva_wallet_next_action")`; `src/aeat/application/modelo/_actions.py`.
- [ ] `W01.P03.S94` - add real-behavior test asserting IVA-wallet finding next-action is localized; `src/aeat/application/modelo/test_actions.py`.
- [ ] `W01.P03.S95` - replace `_iva_wallet_blocked_message` body with `tr("application.modelo.errors.iva_wallet_blocked", ...)`; `src/aeat/application/modelo/_actions.py`.
- [ ] `W01.P03.S96` - add real-behavior test asserting the IVA-wallet-blocked envelope carries the localized message in `translated_message`; `src/aeat/application/modelo/test_actions.py`.
- [ ] `W01.P03.S97` - route the missing-required-casilla finding `message=` through `tr("application.modelo.findings.missing_required_casilla", casilla_id=...)`; `src/aeat/application/modelo/_actions.py`.
- [ ] `W01.P03.S98` - add real-behavior test asserting missing-required-casilla output is localized; `src/aeat/application/modelo/test_actions.py`.
- [ ] `W01.P03.S99` - thread `translated_message="adapters.sede.errors.no_auth_session"` on every `SedeNavigationError` raise across `_auth_state.py`, `_walker.py`, `_iva_compensation_wallet.py`, `_notifications.py`, `_declarations.py`; `src/aeat/adapters/outbound/aeat/sede/_auth_state.py`.
- [ ] `W01.P03.S100` - add real-behavior test asserting every SedeNavigationError raise surfaces the localized translated_message at the CLI boundary; `src/aeat/adapters/outbound/aeat/sede/test_auth_state.py`.
- [ ] `W01.P03.S101` - thread `translated_message="adapters.sede.errors.empty_identity_nif"` on the empty-NIF raise; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [ ] `W01.P03.S102` - add real-behavior test asserting empty-NIF localized envelope at the live-filing observation boundary; `src/aeat/adapters/outbound/aeat/sede/test_declarations.py`.
- [ ] `W01.P03.S103` - wrap the wizard `typer.echo("status\t...")` English verbs in `tr("wizard.commands.status.created")` / `tr("wizard.commands.status.updated")`; `src/aeat/application/wizard/_commands.py`.
- [ ] `W01.P03.S104` - add real-behavior test asserting wizard status verbs are localized; `src/aeat/application/wizard/test_commands.py`.
- [ ] `W01.P03.S105` - replace `<unset>` literal in profile diagnostics emit with `tr("cli.diagnostics.profile.unset_placeholder")`; `src/aeat/diagnostics/profile.py`.
- [ ] `W01.P03.S106` - add real-behavior test asserting profile-diagnostics unset placeholder is localized; `src/aeat/diagnostics/test_profile.py`.
- [ ] `W01.P03.S107` - replace `raise typer.BadParameter(message)` with a `tr()`-mediated lookup for the registry-snapshot describe path; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W01.P03.S108` - extend the modelo describe test to confirm BadParameter messages are localized; `src/aeat/entrypoints/cli/test_modelo.py`.
- [ ] `W01.P03.S109` - replace the two `raise typer.BadParameter(str(exc))` sites for DT12 / SAL computation with `tr("cli.app.modelo.work.dt12_computation_error", ...)` / `tr("cli.app.modelo.work.sal_computation_error", ...)`; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `W01.P03.S110` - add real-behavior test asserting DT12 / SAL computation error surfaces are localized; `src/aeat/entrypoints/cli/test_modelo.py`.
- [ ] `W01.P03.S111` - thread `translated_message=` keys on the two `SedeParseError` raises for empty IVA wallet period / amount cells; `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`.
- [ ] `W01.P03.S112` - add real-behavior test asserting localized IVA-wallet empty-cell envelopes at the CLI boundary; `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`.
- [ ] `W01.P03.S113` - replace the DT12 advisory `next_action=` with `tr("application.modelo.findings.dt12a_reduccion_next_action")`; `src/aeat/application/modelo/_actions.py`.
- [ ] `W01.P03.S114` - add real-behavior test asserting DT12 advisory next-action is localized; `src/aeat/application/modelo/test_actions.py`.
- [ ] `W01.P03.S115` - wrap the locales-CLI `typer.echo` messages in `tr("locales.cli.*")` for developer-tooling consistency; `src/aeat/locales/cli.py`.
- [ ] `W01.P03.S116` - add real-behavior test asserting locales-CLI emits use the catalogue under each supported output language; `src/aeat/locales/test_cli.py`.
- [ ] `W01.P03.S117` - introduce `DEFAULT_OUTPUT_LANGUAGE: Final[str] = "es"` in `aeat.core.i18n._render` and route every `"es"` fallback through it; `src/aeat/core/i18n/_render.py`.
- [ ] `W01.P03.S118` - add real-behavior test asserting every `"es"` fallback now reads from `DEFAULT_OUTPUT_LANGUAGE`; `src/aeat/core/i18n/test_render_override.py`.

### Phase `W01.P04` - enroll typed pydantic models at boundaries

Replace `dict[str, Any]` returns at oracle-replay and LLM-cache
boundaries with strict pydantic v2 envelopes; verify Google /
Playwright dict returns retain their documented boundary rationale.
Each fix Step is paired with a verification Step that asserts the
envelope round-trips through `model_validate` and rejects partial
payloads.

- [x] `W01.P04.S119` - introduce `ReplayPayload(BaseModel)` base + per-oracle subclasses; `replace `dict[str, Any]` return from `decode_replay_json_payload`; `src/aeat/domain/calculations/registry/_live_parity.py`.
- [x] `W01.P04.S120` - add roundtrip test asserting `ReplayPayload.model_validate` rejects partial / mistyped payloads; `src/aeat/domain/calculations/registry/test_live_parity.py`.
- [x] `W01.P04.S121` - replace manual dict unpacking with `AeatNifIvaReplayPayload.model_validate`; `src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py`.
- [x] `W01.P04.S122` - add roundtrip test asserting NIF-IVA replay payload validates and round-trips strictly; `src/aeat/domain/calculations/registry/test_aeat_nif_iva_oracle.py`.
- [x] `W01.P04.S123` - replace manual dict unpacking with `GroiReplayPayload.model_validate`; `src/aeat/domain/calculations/registry/_groi_oracle.py`.
- [x] `W01.P04.S124` - add roundtrip test asserting GROI replay payload validates strictly; `src/aeat/domain/calculations/registry/test_groi_oracle.py`.
- [x] `W01.P04.S125` - replace manual dict unpacking with `RentaWebOpenReplayPayload.model_validate`; `src/aeat/domain/calculations/registry/_renta_web_open_oracle.py`.
- [x] `W01.P04.S126` - add roundtrip test asserting Renta WEB Open replay payload validates strictly; `src/aeat/domain/calculations/registry/test_renta_web_open_oracle.py`.
- [ ] `W01.P04.S127` - verify `_entry_from_payload` enforces `CachedEntry.model_validate` before consuming fields; `src/aeat/adapters/outbound/llm/_cache.py`.
- [ ] `W01.P04.S128` - add roundtrip test asserting LLM cache entries reject malformed persisted payloads; `src/aeat/adapters/outbound/llm/test_cache.py`.
- [ ] `W01.P04.S129` - confirm Google Sheets / Drive `dict[str, Any]` returns retain their inline rationale; `add audit-note assertion test that the rationale comment survives refactors; `src/aeat/adapters/outbound/google/_calc_sheets_apply.py`.
- [ ] `W01.P04.S130` - add real-behavior test asserting Google Sheets / Drive boundary comments remain present per the third-party-rationale policy; `src/aeat/adapters/outbound/google/test_calc_sheets_apply.py`.
- [ ] `W01.P04.S131` - confirm Playwright `_build_context_kwargs` / `storage_state` retain their boundary rationale; `src/aeat/adapters/outbound/aeat/browser/session.py`.
- [ ] `W01.P04.S132` - add real-behavior test asserting Playwright kwargs boundary annotation remains present; `src/aeat/adapters/outbound/aeat/browser/test_session.py`.
- [ ] `W01.P04.S133` - wrap the auth-diagnostics raw JSON payload return in `DiagnosticPayload(BaseModel)`; `src/aeat/application/auth/_diagnostics.py`.
- [ ] `W01.P04.S134` - add roundtrip test asserting diagnostic payload validates and round-trips; `src/aeat/application/auth/test_diagnostics.py`.
- [ ] `W01.P04.S135` - audit every `dict[str, Any]` return signature under `src/aeat/adapters/` for missing boundary rationale; `flag each unannotated case as a follow-up Step in Wave 2; `src/aeat/adapters`.
- [ ] `W01.P04.S136` - add real-behavior test asserting the boundary rationale assertion runs across the adapter inventory; `src/aeat/adapters/test_boundary_rationale.py`.

### Phase `W01.P05` - consolidate duplicated helpers under canonical modules

Eliminate helper duplication identified in the A5 audit by moving
canonical implementations to existing or new core modules and
deleting peer copies. The `_ensure_utc` conflicting-semantics
finding takes priority because it is a correctness hazard, not just
duplication. Each fix Step is paired with a verification Step that
asserts every caller now imports from the canonical home.

- [x] `W01.P05.S137` - split `_ensure_utc` into `_coerce_utc_aware` and `_validate_utc_aware`; `move both to a canonical module under `aeat.core.time`; `src/aeat/core/time/_utc.py`.
- [x] `W01.P05.S138` - add real-behavior test asserting the coercion and the validation variants behave per their documented contracts on naive / aware / mixed inputs; `src/aeat/core/time/test_utc.py`.
- [x] `W01.P05.S139` - migrate the four `_ensure_utc` call-sites (`auth/certificate.py`, `storage/bucket/_manifest.py`, `storage/master_key/_recovery_record.py`, `user_profile/_aggregate.py`) to the explicit variants; `delete the four local copies; `src/aeat/adapters/outbound/aeat/auth/certificate.py`.
- [x] `W01.P05.S140` - extend the test surface to cover every migrated call-site under its real boundary; `src/aeat/adapters/persistence/storage/bucket/test_manifest.py`.
- [x] `W01.P05.S141` - move `_now` / `_utcnow` to `aeat.core.time._clock`; `delete the six local copies; `src/aeat/core/time/_clock.py`.
- [x] `W01.P05.S142` - add real-behavior test asserting every former call-site reads the canonical clock; `src/aeat/core/time/test_clock.py`.
- [ ] `W01.P05.S143` - parametrize `_storage_path` into one shared helper under `aeat.application._storage_paths`; `delete the seven local copies; `src/aeat/application/_storage_paths.py`.
- [ ] `W01.P05.S144` - add real-behavior test asserting the helper produces the historical path layout for every former caller's root; `src/aeat/application/test_storage_paths.py`.
- [x] `W01.P05.S145` - move `_round_to_cents` to `aeat.domain.fincas._rounding`; `delete the two peer copies in `_amortization_ledger.py` and `_expense_rollup.py`; `src/aeat/domain/fincas/_rounding.py`.
- [x] `W01.P05.S146` - add real-behavior test asserting fincas rounding behaves under representative Decimal inputs; `src/aeat/domain/fincas/test_rounding.py`.
- [ ] `W01.P05.S147` - reconcile `_parse_bool` signatures (`bool` vs `bool | None`); `move canonical version to `aeat.core.parsing._utils`; `src/aeat/core/parsing/_utils.py`.
- [ ] `W01.P05.S148` - add real-behavior test asserting `_parse_bool` rejects unknown tokens and round-trips truthy / falsy inputs per call-site contract; `src/aeat/core/parsing/test_utils.py`.
- [ ] `W01.P05.S149` - keep `_parse_date` variants distinct as `_parse_iso8601_date` and `_parse_ddmmyyyy_date`; `co-locate under `aeat.core.parsing._dates`; `src/aeat/core/parsing/_dates.py`.
- [ ] `W01.P05.S150` - add real-behavior test asserting each date variant rejects the foreign format; `src/aeat/core/parsing/test_dates.py`.
- [ ] `W01.P05.S151` - consolidate `_format_decimal` into `aeat.core.decimal._format`; `delete the four peer copies; `src/aeat/core/decimal/_format.py`.
- [ ] `W01.P05.S152` - add real-behavior test asserting decimal-format produces stable output for representative values; `src/aeat/core/decimal/test_format.py`.
- [ ] `W01.P05.S153` - reconcile `_coerce_decimal` signatures; `canonicalize under `aeat.core.decimal._coerce`; delete the three peer copies; `src/aeat/core/decimal/_coerce.py`.
- [ ] `W01.P05.S154` - add real-behavior test asserting coerce-decimal handles None / int / str / Decimal / malformed inputs per the canonical signature; `src/aeat/core/decimal/test_coerce.py`.

### Phase `W01.P06` - eliminate stubs and dead branches

Close the single confirmed stub finding from the A6 audit. Track
the legacy IVA-wallet decision-key migration bridge for deferred
removal. Each fix Step is paired with a verification Step that
either deletes the dead path or asserts it survives only because
real callers still rely on it.

- [ ] `W01.P06.S155` - delete the empty `if TYPE_CHECKING: pass` block; `src/aeat/application/modelo/_taxation_comparison.py`.
- [ ] `W01.P06.S156` - add real-behavior test asserting the module still type-checks and imports cleanly under the production interpreter; `src/aeat/application/modelo/test_taxation_comparison.py`.
- [ ] `W01.P06.S157` - audit the `_legacy_iva_wallet_decision_key` migration bridge for callable references in persisted records; `if zero hits, delete; otherwise schedule the migration close-out as a Wave 2 Step; `src/aeat/application/calculations/_observations_repository.py`.
- [ ] `W01.P06.S158` - add real-behavior test asserting the legacy decision-key fallback path is reached only by pre-hardening records and is a no-op for hashed records; `src/aeat/application/calculations/test_observations_repository.py`.

### Phase `W01.P07` - eliminate hardcoded values and enum bypass

Promote existing Literals to StrEnum where the audit identified
27+ bare-string comparison sites; route every enum-bypass call-site
through the StrEnum member; add missing project constants for
repeated magic strings. Each fix Step is paired with a verification
Step that asserts the bare-string form is rejected at type-check
time and at runtime.

- [ ] `W01.P07.S159` - promote `InputKind` Literal to `StrEnum`; `place it alongside the Casilla model in the registry schema; `src/aeat/domain/calculations/registry/_schema.py`.
- [ ] `W01.P07.S160` - add real-behavior test asserting `InputKind` rejects unknown tokens and round-trips through the registry; `src/aeat/domain/calculations/registry/test_schema.py`.
- [ ] `W01.P07.S161` - replace the 27 bare-string `input_kind == "..."` comparisons across 12 files with `InputKind.<MEMBER>`; `src/aeat/application/filing/__init__.py`.
- [ ] `W01.P07.S162` - add real-behavior test asserting every former bare-string comparison still produces its historical truth value under the enum surface; `src/aeat/application/filing/test_init.py`.
- [ ] `W01.P07.S163` - replace the 53 raw `"ledger_transaction"` / `"purchase_invoice_evidence"` / `"payable_invoice"` / `"collectible_invoice"` literals with `AggregationSourceKind` members across 8 files; `src/aeat/application/aggregation/_counterpart.py`.
- [ ] `W01.P07.S164` - add real-behavior test asserting every aggregation source-kind tuple matches the StrEnum surface; `src/aeat/application/aggregation/test_service.py`.
- [ ] `W01.P07.S165` - replace the 4 raw `"pending"` / `"reviewed"` / `"skipped"` returns with `ReviewStatusFilter` members; `src/aeat/application/invoices/_projection.py`.
- [ ] `W01.P07.S166` - add real-behavior test asserting review-status returns are the StrEnum members at every former bare-string site; `src/aeat/application/invoices/test_projection.py`.
- [ ] `W01.P07.S167` - replace the IVA-regime bare-string `frozenset({"SIMPLIFICADO"})` and `click.Choice(["GENERAL", "SIMPLIFICADO", "RECARGO_EQUIVALENCIA", "EXENTO"])` with `IVARegime` enum members; `src/aeat/application/modelo/_actions.py`.
- [ ] `W01.P07.S168` - add real-behavior test asserting IVA-regime branching uses the enum surface; `src/aeat/application/modelo/test_actions.py`.
- [ ] `W01.P07.S169` - promote the registry-schema `"draft" | "casilla" | "binding" | ...` Literal to `CasillaFieldKind(StrEnum)`; `src/aeat/domain/calculations/registry/_schema.py`.
- [ ] `W01.P07.S170` - add real-behavior test asserting CasillaFieldKind rejects unknown tokens; `src/aeat/domain/calculations/registry/test_schema.py`.
- [ ] `W01.P07.S171` - introduce `CLASSIFIED_BY_MANUAL: Final[str] = "manual"` in `aeat.application.ledger._models`; `replace the three bare-string sites; `src/aeat/application/ledger/_models.py`.
- [ ] `W01.P07.S172` - add real-behavior test asserting ledger classification reads through the constant; `src/aeat/application/ledger/test_models.py`.
- [ ] `W01.P07.S173` - promote `OracleEnvironment` Literal to `StrEnum`; `replace the six default-value sites; `src/aeat/domain/calculations/registry/_live_parity.py`.
- [ ] `W01.P07.S174` - add real-behavior test asserting OracleEnvironment members round-trip through every replaced default; `src/aeat/domain/calculations/registry/test_live_parity.py`.
- [ ] `W01.P07.S175` - introduce `DEFAULT_CURRENCY: Final[str] = "EUR"` in `aeat.core.external_constants`; `replace the 20 `"EUR"` sites across 8 files; `src/aeat/core/external_constants.py`.
- [ ] `W01.P07.S176` - add real-behavior test asserting every former currency literal now reads from the constant; `src/aeat/core/test_external_constants.py`.
- [ ] `W01.P07.S177` - introduce `BINARY_MIME_TYPE: Final[str] = "application/octet-stream"` in `aeat.core.external_constants`; `replace the three sites including the already-extracted `_BINARY_MIME`; `src/aeat/core/external_constants.py`.
- [ ] `W01.P07.S178` - add real-behavior test asserting every former MIME literal reads from the constant; `src/aeat/core/test_external_constants.py`.
- [ ] `W01.P07.S179` - introduce `CSV_ENCODING_FALLBACK_CHAIN: tuple[str, ...]` in `aeat.core.external_constants`; `replace the inline tuple; `src/aeat/adapters/inbound/financial/providers/_csv.py`.
- [ ] `W01.P07.S180` - add real-behavior test asserting the CSV provider iterates the canonical fallback chain; `src/aeat/adapters/inbound/financial/providers/test_csv.py`.
- [ ] `W01.P07.S181` - introduce shared file-extension sets (`CSV_EXTENSIONS`, `PDF_EXTENSION`, `XLSX_EXTENSION`) under `src/aeat/adapters/inbound/financial/providers/_constants.py`; `src/aeat/adapters/inbound/financial/providers/_constants.py`.
- [ ] `W01.P07.S182` - add real-behavior test asserting financial-provider detection reads from the shared constants; `src/aeat/adapters/inbound/financial/providers/test_detection.py`.
- [ ] `W01.P07.S183` - centralize the `latin-1` / `iso-8859-1` alias normalization dict in `aeat.domain.calculations.registry._record_spec`; `src/aeat/domain/calculations/registry/_record_spec.py`.
- [ ] `W01.P07.S184` - add real-behavior test asserting the alias map is the single source of truth at every decode call-site; `src/aeat/domain/calculations/registry/test_record_spec.py`.
- [ ] `W01.P07.S185` - introduce `FilingStatus.FILED` (or equivalent) and replace the bare `"filed"` literals across `_app_live.py` and `_contract.py`; `src/aeat/application/operator_surface/_contract.py`.
- [ ] `W01.P07.S186` - add real-behavior test asserting the FilingStatus surface is the only source for `"filed"`; `src/aeat/application/operator_surface/test_contract.py`.
- [ ] `W01.P07.S187` - extract the `"COLUMNS"` env-key literal to a module-level `_COLUMNS_ENV_VAR: Final[str]`; `src/aeat/entrypoints/cli/_stdio.py`.
- [ ] `W01.P07.S188` - add real-behavior test asserting CLI stdio reads the env-var via the constant; `src/aeat/entrypoints/cli/test_stdio.py`.

### Phase `W01.P08` - tighten typecheck escape hatches

Address production-side `cast()` calls and `-> Any` returns
identified in the A8 audit. Documented third-party API boundaries
stay; undocumented escapes get justified inline or replaced with
typed structures. Each fix Step is paired with a verification Step
that asserts the new typed contract holds under representative
inputs.

- [ ] `W01.P08.S189` - replace `cast(T, envelope.payload)` with envelope-generic refinement or add inline rationale; `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`.
- [ ] `W01.P08.S190` - add real-behavior test asserting envelope payload type is preserved across the generic boundary; `src/aeat/adapters/persistence/storage/envelope/test_secure_repository.py`.
- [ ] `W01.P08.S191` - replace `cast(Any, Envelope).__class_getitem__(...)` with a typed factory method; `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`.
- [ ] `W01.P08.S192` - add real-behavior test asserting the typed factory yields the correct envelope subtype per payload; `src/aeat/adapters/persistence/storage/envelope/test_secure_repository.py`.
- [ ] `W01.P08.S193` - replace `cast(Callable[P, R], existing)` with a `TypeGuard` or runtime-protocol check; `src/aeat/entrypoints/cli/_errors.py`.
- [ ] `W01.P08.S194` - add real-behavior test asserting the type-guard narrows correctly for valid / invalid callables; `src/aeat/entrypoints/cli/test_errors.py`.
- [ ] `W01.P08.S195` - add inline rationale to every remaining production `cast()` call or refactor to remove the cast; `track each remaining cast as a Wave 2 follow-up Step; `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`.
- [ ] `W01.P08.S196` - add real-behavior test asserting the inline-rationale comment survives a refactor and the cast contract still holds; `src/aeat/adapters/persistence/storage/envelope/test_secure_repository.py`.
- [ ] `W01.P08.S197` - refine the Google adapter `-> Any` returns using `google-api-python-client-stubs` if present; `otherwise wrap the response in a `TypedDict`; `src/aeat/adapters/outbound/google/_api.py`.
- [ ] `W01.P08.S198` - add real-behavior test asserting Google API responses validate against the typed shape; `src/aeat/adapters/outbound/google/test_api.py`.
- [ ] `W01.P08.S199` - refine the calc-sheets-pull `-> Any` returns using TypedDict or pydantic; `src/aeat/adapters/outbound/google/_calc_sheets_pull.py`.
- [ ] `W01.P08.S200` - add real-behavior test asserting calc-sheets pull response typing; `src/aeat/adapters/outbound/google/test_calc_sheets_pull.py`.
- [ ] `W01.P08.S201` - replace `**kwargs: Any` on `invoke_cached_cli` with a TypedDict covering the Click invoke surface; `src/aeat/tests/cli_runner.py`.
- [ ] `W01.P08.S202` - add real-behavior test asserting CLI test runner rejects unknown kwargs at type-check; `src/aeat/tests/test_cli_runner.py`.
- [ ] `W01.P08.S203` - add overload signatures to `_scrub_value` so the recursive heterogeneous payload contract is typed precisely; `src/aeat/core/logging.py`.
- [ ] `W01.P08.S204` - add real-behavior test asserting the overload contract preserves type for str / Mapping / tuple / list / set inputs; `src/aeat/core/test_logging.py`.

### Phase `W01.P09` - audit test-suite semantic intent and actual coverage

Sweep the test surface for tautological assertions, mock / patch /
skip / xfail usage outside legitimate boundary-test fixtures, real-
behavior test absence at any persistence boundary touched by an
A1..A8 fix Step, and `pytest` collection coverage versus production
module inventory. Each finding becomes its own Step; remediation
strengthens the test, never weakens or skips it.

- [ ] `W01.P09.S205` - enumerate every `pytest.mark.skip` / `pytest.mark.xfail` under `src/aeat/`; `record each as a Wave 1 follow-up Step requiring removal or replacement with a real-behavior test; `src/aeat`.
- [ ] `W01.P09.S206` - add real-behavior test asserting the enumeration result is zero (a `git grep`-style assertion that survives in CI); `src/aeat/test_no_skip_xfail.py`.
- [ ] `W01.P09.S207` - enumerate every `unittest.mock` / `pytest-mock` import under `src/aeat/`; `classify each as legitimate boundary mock or drift; record drift sites as follow-up Steps; `src/aeat`.
- [ ] `W01.P09.S208` - add real-behavior test asserting the classification result holds across the test inventory; `src/aeat/test_mock_inventory.py`.
- [ ] `W01.P09.S209` - enumerate every `monkeypatch` use under `src/aeat/`; `classify each as test-isolation fixture or production-state mutation; record drift as follow-up Steps; `src/aeat`.
- [ ] `W01.P09.S210` - add real-behavior test asserting monkeypatch inventory matches the classification; `src/aeat/test_monkeypatch_inventory.py`.
- [ ] `W01.P09.S211` - enumerate every `assert True` / `assert 1 == 1` / `assert var == var` shape under `src/aeat/`; `remove or replace each with a real assertion; `src/aeat`.
- [ ] `W01.P09.S212` - add real-behavior test asserting zero tautological assertion shapes survive in the test surface; `src/aeat/test_no_tautology.py`.
- [ ] `W01.P09.S213` - enumerate every calculation test that hand-computes an expected value from the registry formula under test; `record each as a follow-up Step to re-ground against an external authority; `src/aeat/domain/calculations`.
- [ ] `W01.P09.S214` - add real-behavior test asserting calculation-test expected values are sourced from registry fixtures, AEAT workbooks, BOE worked examples, or live oracle replay (per `no-tautological-calculation-tests.md`); `src/aeat/domain/calculations/test_calculation_grounding.py`.
- [ ] `W01.P09.S215` - diff `pytest` collection inventory against the production module inventory under `src/aeat/`; `record every module without a paired `test_*.py` as a Wave 2 follow-up Step; `src/aeat`.
- [ ] `W01.P09.S216` - add real-behavior test asserting every production module under `src/aeat/.../` has at least one paired test file (excluding legitimate test-only modules); `src/aeat/test_coverage_inventory.py`.
- [ ] `W01.P09.S217` - enumerate every persistence boundary touched by a W01.P01..P08 fix Step and confirm a roundtrip test exists per `aeat-roundtrip-discipline.md`; `src/aeat`.
- [ ] `W01.P09.S218` - add real-behavior test asserting persistence boundary inventory matches roundtrip-test inventory; `src/aeat/test_roundtrip_coverage.py`.
- [ ] `W01.P09.S219` - sample 20 random production-test pairings for semantic-intent drift (test asserts incidental shape rather than behaviour); `record each as a follow-up Step; `src/aeat`.
- [ ] `W01.P09.S220` - add real-behavior test asserting the sample-review process runs against a deterministic seed and produces reproducible output; `src/aeat/test_semantic_intent_sampler.py`.
- [ ] `W01.P09.S221` - enumerate every `try: ... except: pass` shape in test files; `replace each with a specific exception assertion; `src/aeat`.
- [ ] `W01.P09.S222` - add real-behavior test asserting zero bare-except shapes survive in the test surface; `src/aeat/test_no_bare_except.py`.
- [ ] `W01.P09.S223` - enumerate every test that constructs a pydantic model with only the required fields populated (per `aeat-roundtrip-discipline.md`'s "populate every defaultable field" rule); `record each as a follow-up Step; `src/aeat`.
- [ ] `W01.P09.S224` - add real-behavior test asserting roundtrip-fixture builders saturate every defaultable field; `src/aeat/test_roundtrip_fixture_saturation.py`.
