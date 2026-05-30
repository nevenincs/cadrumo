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
- [x] `W01.P01.S09` - introduce `WorkflowInputMismatchError(CoreError)` or reuse `CoreValidationError`; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P01.S10` - add real-behavior test asserting workflow-input-mismatch envelope and registry binding; `src/aeat/application/modelo/test_actions.py`.
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
- [x] `W01.P01.S23` - introduce `PensionReduccionError(CoreValidationError)`; `replace the six `ValueError` raises at pension reducción computation; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W01.P01.S24` - add real-behavior test asserting pension-reducción error envelope at every replaced raise; `src/aeat/entrypoints/cli/test_modelo.py`.
- [x] `W01.P01.S25` - introduce `BindingPrefillTypeError(CoreValidationError)`; `replace the `TypeError`; `src/aeat/application/calculations/_binding_prefill.py`.
- [x] `W01.P01.S26` - add real-behavior test asserting binding-prefill-type-error envelope; `src/aeat/application/calculations/test_binding_prefill.py`.
- [x] `W01.P01.S27` - introduce `WizardAnswerTypeError(CoreValidationError)`; `replace every coercion `TypeError` / `ValueError` raise (15+ sites); `src/aeat/application/wizard/_setup_answers.py`.
- [x] `W01.P01.S28` - add real-behavior test asserting wizard-answer-type-error envelope at every replaced raise; `src/aeat/application/wizard/test_setup_answers.py`.
- [x] `W01.P01.S29` - confirm `RecoveryVerificationError` subclasses `AeatError`; `narrow the `except Exception` and reraise typed; `src/aeat/adapters/persistence/storage/master_key/_recovery_facade.py`.
- [x] `W01.P01.S30` - add real-behavior test asserting recovery-facade envelope under each upstream exception class; `src/aeat/adapters/persistence/storage/master_key/test_recovery_facade.py`.
- [x] `W01.P01.S31` - narrow the `except Exception` to specific `AeatError` subtypes; `remove the no-active-profile reclassification; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P01.S32` - add real-behavior test asserting non-NoActiveProfileError exceptions propagate with their original envelope; `src/aeat/entrypoints/cli/test_ledger.py`.
- [x] `W01.P01.S33` - narrow the autocomplete `except Exception` to specific `AeatError` subtypes; `log others at DEBUG via observability sink; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W01.P01.S34` - add real-behavior test asserting autocomplete propagates AeatError envelope and observability records non-AeatError; `src/aeat/entrypoints/cli/test_modelo.py`.
- [x] `W01.P01.S35` - wrap each of the seven `except Exception` clauses in `_record_unhandled` with `build_error_envelope`; `assign a synthetic `UNHANDLED_INTERNAL` `ErrorCode`; `src/aeat/application/workflow/_engine.py`.
- [x] `W01.P01.S36` - add real-behavior test asserting `_record_unhandled` envelopes carry an `ErrorCode` for every original exception class; `src/aeat/application/workflow/test_engine.py`.
- [x] `W01.P01.S37` - narrow the four config-CLI `except Exception` catches to `AeatError`; `wrap unexpected exceptions in `ConfigBoundaryError(CoreError)`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W01.P01.S38` - add real-behavior test asserting config-CLI envelope on AeatError and ConfigBoundaryError on unexpected; `src/aeat/entrypoints/cli/_config/test_config.py`.
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

- [x] `W01.P02.S49` - replace module-level `_LOGGER = logging.getLogger(__name__)` with `get_logger(__name__)`; `src/aeat/entrypoints/cli/_stdio.py`.
- [x] `W01.P02.S50` - add real-behavior test asserting CLI stdio logger applies `SecretScrubbingFilter` to NIF-shaped records; `src/aeat/entrypoints/cli/test_stdio.py`.
- [x] `W01.P02.S51` - hoist the function-body `_log = logging.getLogger(__name__)` to module-level `get_logger(__name__)`; `src/aeat/entrypoints/cli/_overview.py`.
- [x] `W01.P02.S52` - add real-behavior test asserting overview logger scrubs taxpayer data; `src/aeat/entrypoints/cli/test_overview.py`.
- [x] `W01.P02.S53` - replace the inline `_logging.getLogger(__name__)` with module-level `get_logger`; `src/aeat/core/errors/_registry.py`.
- [x] `W01.P02.S54` - add real-behavior test asserting error-registry resolution-failure debug log scrubs sensitive context; `src/aeat/core/errors/test_registry.py`.
- [x] `W01.P02.S55` - replace the inline `logging.getLogger(__name__).warning` with module-level `get_logger`; `src/aeat/core/observability/_sink.py`.
- [x] `W01.P02.S56` - add real-behavior test asserting sink-failure warning carries scrubbed exception traceback; `src/aeat/core/observability/test_sink.py`.
- [x] `W01.P02.S57` - add `pdfminer` to the `loggers` block of `configure_logging()` dictConfig; `delete the in-place mutation; `src/aeat/adapters/inbound/pdf/_pdfplumber.py`.
- [x] `W01.P02.S58` - add real-behavior test asserting `pdfminer` logger level is governed by `aeat.core.logging` dictConfig; `src/aeat/core/test_logging.py`.
- [x] `W01.P02.S59` - delete the duplicated `pdfminer` mutation; `rely on the centralized `loggers` block; `src/aeat/domain/calculations/registry/_record_design.py`.
- [x] `W01.P02.S60` - extend the dictConfig test to confirm both `_pdfplumber.py` and `_record_design.py` paths defer to centralized config; `src/aeat/core/test_logging.py`.
- [x] `W01.P02.S61` - replace the root-logger level-patch traversal with a `set_log_level(level)` helper exposed by `aeat.core.logging`; `src/aeat/entrypoints/cli/_log_levels.py`.
- [x] `W01.P02.S62` - add real-behavior test asserting the helper updates root + every attached handler under every dictConfig variant; `src/aeat/entrypoints/cli/test_log_levels.py`.
- [x] `W01.P02.S63` - install `SecretScrubbingFilter` on the sink before `root_logger.addHandler(sink)`; `expose `attach_run_sink(sink)` helper in `aeat.core.logging`; `src/aeat/core/observability/_context.py`.
- [x] `W01.P02.S64` - add real-behavior test asserting JSONL run sink records are scrubbed before persistence; `src/aeat/core/observability/test_context_propagation.py`.
- [x] `W01.P02.S65` - replace the auth-waiting `print(line, file=stream, flush=True)` with a typed CLI renderer routed through a structured logger; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.
- [x] `W01.P02.S66` - add real-behavior test asserting auth waiting messages never carry unmasked verification codes through stderr; `src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py`.
- [x] `W01.P02.S67` - replace `sys.stdout.write` with an injected render primitive; `src/aeat/application/wizard/_prompter.py`.
- [x] `W01.P02.S68` - add real-behavior test asserting wizard prompter routes through the structured render path; `src/aeat/application/wizard/test_prompter.py`.
- [x] `W01.P02.S69` - guard the module-level `print(...)` in the normatives docstring example behind `if __name__ == "__main__":` or convert to a proper doctest block; `src/aeat/domain/normatives/__init__.py`.
- [x] `W01.P02.S70` - add real-behavior test asserting importing `aeat.domain.normatives` produces no stdout output; `src/aeat/domain/normatives/test_init.py`.
- [x] `W01.P02.S71` - guard the LLM-adapter docstring example `print(response.text)` behind `if __name__ == "__main__":`; `src/aeat/adapters/outbound/llm/__init__.py`.
- [x] `W01.P02.S72` - add real-behavior test asserting importing `aeat.adapters.outbound.llm` produces no stdout output; `src/aeat/adapters/outbound/llm/test_init.py`.
- [x] `W01.P02.S73` - add `pikepdf._core` to `configure_logging()` `loggers` block; `remove the bootstrap-time mutation; `src/aeat/__init__.py`.
- [x] `W01.P02.S74` - add real-behavior test asserting `pikepdf._core` level survives a `configure_logging()` re-call; `src/aeat/core/test_logging.py`.
- [x] `W01.P02.S75` - attach `SecretScrubbingFilter` to the `root_logger.getLogger()` sink path; `src/aeat/core/observability/_context.py`.
- [x] `W01.P02.S76` - add real-behavior test asserting run-scoped records pass through scrubbing before reaching the JSONL directory; `src/aeat/core/observability/test_sink_redaction.py`.

### Phase `W01.P03` - enroll the centralized locale surface

Route every operator-visible string through `tr()` / `Translatable`;
populate `translated_message=` on every `SedeError` raise that
reaches the CLI envelope; eliminate bare-string `typer.echo` /
f-string emits at the CLI boundary. Each fix Step is paired with a
verification Step that asserts the locale catalogue carries the key
and the operator surface emits the localized payload.

- [x] `W01.P03.S77` - replace the bare `_bad(f"draft id ...")` with `tr("cli.common.errors.draft_id_not_found", draft_id=draft_id)`; `src/aeat/entrypoints/cli/_common.py`.
- [x] `W01.P03.S78` - add real-behavior test asserting the draft-id-not-found surface emits the localized payload; `src/aeat/entrypoints/cli/test_common.py`.
- [x] `W01.P03.S79` - route the no-active-profile dict / text emit through `_no_active_profile_refusal()` and `tr()` keys; `src/aeat/entrypoints/cli/_common.py`.
- [x] `W01.P03.S80` - add real-behavior test asserting no-active-profile output is localized in text and JSON channels; `src/aeat/entrypoints/cli/test_common.py`.
- [x] `W01.P03.S81` - add `cli.ledger.errors.id_prefix_unknown` catch-all and route the raw-message passthrough through `tr()`; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P03.S82` - add real-behavior test asserting ledger id-prefix fallthrough emits the localized payload; `src/aeat/entrypoints/cli/test_ledger.py`.
- [x] `W01.P03.S83` - wrap the eight `describe` label rows in `tr("cli.app.modelo.describe.label_*")` keys; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W01.P03.S84` - add real-behavior test asserting `aeat app modelo describe` labels are localized per output language; `src/aeat/entrypoints/cli/test_modelo.py`.
- [x] `W01.P03.S85` - route the cross-casilla-invariant finding `message=` through `tr("application.modelo.findings.cross_casilla_invariant_violated", ...)`; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P03.S86` - add real-behavior test asserting verification-report cross-casilla finding is localized in text and JSON; `src/aeat/application/modelo/test_actions.py`.
- [x] `W01.P03.S87` - route the cross-casilla `next_action=` through `tr("application.modelo.findings.cross_casilla_invariant_next_action", predicate_id=...)`; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P03.S88` - extend the verification-report test to confirm cross-casilla `next_action` localization; `src/aeat/application/modelo/test_actions.py`.
- [x] `W01.P03.S89` - route the registry-snapshot-unresolved finding through `tr("application.modelo.findings.registry_snapshot_unresolved", ...)`; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P03.S90` - add real-behavior test asserting registry-snapshot-unresolved is localized in verification output; `src/aeat/application/modelo/test_actions.py`.
- [x] `W01.P03.S91` - route the DT12-reducción advisory `message=` through `tr("application.modelo.findings.dt12a_reduccion_possible", ...)`; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P03.S92` - add real-behavior test asserting DT12-reducción advisory is localized; `src/aeat/application/modelo/test_actions.py`.
- [x] `W01.P03.S93` - route the IVA-wallet `next_action=` through `tr("application.modelo.findings.iva_wallet_next_action")`; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P03.S94` - add real-behavior test asserting IVA-wallet finding next-action is localized; `src/aeat/application/modelo/test_actions.py`.
- [x] `W01.P03.S95` - replace `_iva_wallet_blocked_message` body with `tr("application.modelo.errors.iva_wallet_blocked", ...)`; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P03.S96` - add real-behavior test asserting the IVA-wallet-blocked envelope carries the localized message in `translated_message`; `src/aeat/application/modelo/test_actions.py`.
- [x] `W01.P03.S97` - route the missing-required-casilla finding `message=` through `tr("application.modelo.findings.missing_required_casilla", casilla_id=...)`; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P03.S98` - add real-behavior test asserting missing-required-casilla output is localized; `src/aeat/application/modelo/test_actions.py`.
- [x] `W01.P03.S99` - thread `translated_message="adapters.sede.errors.no_auth_session"` on every `SedeNavigationError` raise across `_auth_state.py`, `_walker.py`, `_iva_compensation_wallet.py`, `_notifications.py`, `_declarations.py`; `src/aeat/adapters/outbound/aeat/sede/_auth_state.py`.
- [x] `W01.P03.S100` - add real-behavior test asserting every SedeNavigationError raise surfaces the localized translated_message at the CLI boundary; `src/aeat/adapters/outbound/aeat/sede/test_auth_state.py`.
- [x] `W01.P03.S101` - thread `translated_message="adapters.sede.errors.empty_identity_nif"` on the empty-NIF raise; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W01.P03.S102` - add real-behavior test asserting empty-NIF localized envelope at the live-filing observation boundary; `src/aeat/adapters/outbound/aeat/sede/test_declarations.py`.
- [x] `W01.P03.S103` - wrap the wizard `typer.echo("status\t...")` English verbs in `tr("wizard.commands.status.created")` / `tr("wizard.commands.status.updated")`; `src/aeat/application/wizard/_commands.py`.
- [x] `W01.P03.S104` - add real-behavior test asserting wizard status verbs are localized; `src/aeat/application/wizard/test_commands.py`.
- [x] `W01.P03.S105` - replace `<unset>` literal in profile diagnostics emit with `tr("cli.diagnostics.profile.unset_placeholder")`; `src/aeat/diagnostics/profile.py`.
- [x] `W01.P03.S106` - add real-behavior test asserting profile-diagnostics unset placeholder is localized; `src/aeat/diagnostics/test_profile.py`.
- [x] `W01.P03.S107` - replace `raise typer.BadParameter(message)` with a `tr()`-mediated lookup for the registry-snapshot describe path; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W01.P03.S108` - extend the modelo describe test to confirm BadParameter messages are localized; `src/aeat/entrypoints/cli/test_modelo.py`.
- [x] `W01.P03.S109` - replace the two `raise typer.BadParameter(str(exc))` sites for DT12 / SAL computation with `tr("cli.app.modelo.work.dt12_computation_error", ...)` / `tr("cli.app.modelo.work.sal_computation_error", ...)`; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W01.P03.S110` - add real-behavior test asserting DT12 / SAL computation error surfaces are localized; `src/aeat/entrypoints/cli/test_modelo.py`.
- [x] `W01.P03.S111` - thread `translated_message=` keys on the two `SedeParseError` raises for empty IVA wallet period / amount cells; `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`.
- [x] `W01.P03.S112` - add real-behavior test asserting localized IVA-wallet empty-cell envelopes at the CLI boundary; `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`.
- [x] `W01.P03.S113` - replace the DT12 advisory `next_action=` with `tr("application.modelo.findings.dt12a_reduccion_next_action")`; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P03.S114` - add real-behavior test asserting DT12 advisory next-action is localized; `src/aeat/application/modelo/test_actions.py`.
- [x] `W01.P03.S115` - wrap the locales-CLI `typer.echo` messages in `tr("locales.cli.*")` for developer-tooling consistency; `src/aeat/locales/cli.py`.
- [x] `W01.P03.S116` - add real-behavior test asserting locales-CLI emits use the catalogue under each supported output language; `src/aeat/locales/test_cli.py`.
- [x] `W01.P03.S117` - introduce `DEFAULT_OUTPUT_LANGUAGE: Final[str] = "es"` in `aeat.core.i18n._render` and route every `"es"` fallback through it; `src/aeat/core/i18n/_render.py`.
- [x] `W01.P03.S118` - add real-behavior test asserting every `"es"` fallback now reads from `DEFAULT_OUTPUT_LANGUAGE`; `src/aeat/core/i18n/test_render_override.py`.

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
- [x] `W01.P04.S127` - verify `_entry_from_payload` enforces `CachedEntry.model_validate` before consuming fields; `src/aeat/adapters/outbound/llm/_cache.py`.
- [x] `W01.P04.S128` - add roundtrip test asserting LLM cache entries reject malformed persisted payloads; `src/aeat/adapters/outbound/llm/test_cache.py`.
- [x] `W01.P04.S129` - confirm Google Sheets / Drive `dict[str, Any]` returns retain their inline rationale; `add audit-note assertion test that the rationale comment survives refactors; `src/aeat/adapters/outbound/google/_calc_sheets_apply.py`.
- [x] `W01.P04.S130` - add real-behavior test asserting Google Sheets / Drive boundary comments remain present per the third-party-rationale policy; `src/aeat/adapters/outbound/google/test_calc_sheets_apply.py`.
- [x] `W01.P04.S131` - confirm Playwright `_build_context_kwargs` / `storage_state` retain their boundary rationale; `src/aeat/adapters/outbound/aeat/browser/session.py`.
- [x] `W01.P04.S132` - add real-behavior test asserting Playwright kwargs boundary annotation remains present; `src/aeat/adapters/outbound/aeat/browser/test_session.py`.
- [x] `W01.P04.S133` - wrap the auth-diagnostics raw JSON payload return in `DiagnosticPayload(BaseModel)`; `src/aeat/application/auth/_diagnostics.py`.
- [x] `W01.P04.S134` - add roundtrip test asserting diagnostic payload validates and round-trips; `src/aeat/application/auth/test_diagnostics.py`.
- [x] `W01.P04.S135` - audit every `dict[str, Any]` return signature under `src/aeat/adapters/` for missing boundary rationale; `flag each unannotated case as a follow-up Step in Wave 2; `src/aeat/adapters`.
- [x] `W01.P04.S136` - add real-behavior test asserting the boundary rationale assertion runs across the adapter inventory; `src/aeat/adapters/test_boundary_rationale.py`.

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
- [x] `W01.P05.S143` - parametrize `_storage_path` into one shared helper under `aeat.application._storage_paths`; `delete the seven local copies; `src/aeat/application/_storage_paths.py`.
- [x] `W01.P05.S144` - add real-behavior test asserting the helper produces the historical path layout for every former caller's root; `src/aeat/application/test_storage_paths.py`.
- [x] `W01.P05.S145` - move `_round_to_cents` to `aeat.domain.fincas._rounding`; `delete the two peer copies in `_amortization_ledger.py` and `_expense_rollup.py`; `src/aeat/domain/fincas/_rounding.py`.
- [x] `W01.P05.S146` - add real-behavior test asserting fincas rounding behaves under representative Decimal inputs; `src/aeat/domain/fincas/test_rounding.py`.
- [x] `W01.P05.S147` - reconcile `_parse_bool` signatures (`bool` vs `bool | None`); `move canonical version to `aeat.core.parsing._utils`; `src/aeat/core/parsing/_utils.py`.
- [x] `W01.P05.S148` - add real-behavior test asserting `_parse_bool` rejects unknown tokens and round-trips truthy / falsy inputs per call-site contract; `src/aeat/core/parsing/test_utils.py`.
- [x] `W01.P05.S149` - keep `_parse_date` variants distinct as `_parse_iso8601_date` and `_parse_ddmmyyyy_date`; `co-locate under `aeat.core.parsing._dates`; `src/aeat/core/parsing/_dates.py`.
- [x] `W01.P05.S150` - add real-behavior test asserting each date variant rejects the foreign format; `src/aeat/core/parsing/test_dates.py`.
- [x] `W01.P05.S151` - consolidate `_format_decimal` into `aeat.core.decimal._format`; `delete the four peer copies; `src/aeat/core/decimal/_format.py`.
- [x] `W01.P05.S152` - add real-behavior test asserting decimal-format produces stable output for representative values; `src/aeat/core/decimal/test_format.py`.
- [x] `W01.P05.S153` - reconcile `_coerce_decimal` signatures; `canonicalize under `aeat.core.decimal._coerce`; delete the three peer copies; `src/aeat/core/decimal/_coerce.py`.
- [x] `W01.P05.S154` - add real-behavior test asserting coerce-decimal handles None / int / str / Decimal / malformed inputs per the canonical signature; `src/aeat/core/decimal/test_coerce.py`.

### Phase `W01.P06` - eliminate stubs and dead branches

Close the single confirmed stub finding from the A6 audit. Track
the legacy IVA-wallet decision-key migration bridge for deferred
removal. Each fix Step is paired with a verification Step that
either deletes the dead path or asserts it survives only because
real callers still rely on it.

- [x] `W01.P06.S155` - delete the empty `if TYPE_CHECKING: pass` block; `src/aeat/application/modelo/_taxation_comparison.py`.
- [x] `W01.P06.S156` - add real-behavior test asserting the module still type-checks and imports cleanly under the production interpreter; `src/aeat/application/modelo/test_taxation_comparison.py`.
- [x] `W01.P06.S157` - audit the `_legacy_iva_wallet_decision_key` migration bridge for callable references in persisted records; `if zero hits, delete; otherwise schedule the migration close-out as a Wave 2 Step; `src/aeat/application/calculations/_observations_repository.py`.
- [x] `W01.P06.S158` - add real-behavior test asserting the legacy decision-key fallback path is reached only by pre-hardening records and is a no-op for hashed records; `src/aeat/application/calculations/test_observations_repository.py`.

### Phase `W01.P07` - eliminate hardcoded values and enum bypass

Promote existing Literals to StrEnum where the audit identified
27+ bare-string comparison sites; route every enum-bypass call-site
through the StrEnum member; add missing project constants for
repeated magic strings. Each fix Step is paired with a verification
Step that asserts the bare-string form is rejected at type-check
time and at runtime.

- [x] `W01.P07.S159` - promote `InputKind` Literal to `StrEnum`; `place it alongside the Casilla model in the registry schema; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W01.P07.S160` - add real-behavior test asserting `InputKind` rejects unknown tokens and round-trips through the registry; `src/aeat/domain/calculations/registry/test_schema.py`.
- [x] `W01.P07.S161` - replace the 27 bare-string `input_kind == "..."` comparisons across 12 files with `InputKind.<MEMBER>`; `src/aeat/application/filing/__init__.py`.
- [x] `W01.P07.S162` - add real-behavior test asserting every former bare-string comparison still produces its historical truth value under the enum surface; `src/aeat/application/filing/test_init.py`.
- [x] `W01.P07.S163` - replace the 53 raw `"ledger_transaction"` / `"purchase_invoice_evidence"` / `"payable_invoice"` / `"collectible_invoice"` literals with `AggregationSourceKind` members across 8 files; `src/aeat/application/aggregation/_counterpart.py`.
- [x] `W01.P07.S164` - add real-behavior test asserting every aggregation source-kind tuple matches the StrEnum surface; `src/aeat/application/aggregation/test_service.py`.
- [x] `W01.P07.S165` - replace the 4 raw `"pending"` / `"reviewed"` / `"skipped"` returns with `ReviewStatusFilter` members; `src/aeat/application/invoices/_projection.py`.
- [x] `W01.P07.S166` - add real-behavior test asserting review-status returns are the StrEnum members at every former bare-string site; `src/aeat/application/invoices/test_projection.py`.
- [x] `W01.P07.S167` - replace the IVA-regime bare-string `frozenset({"SIMPLIFICADO"})` and `click.Choice(["GENERAL", "SIMPLIFICADO", "RECARGO_EQUIVALENCIA", "EXENTO"])` with `IVARegime` enum members; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P07.S168` - add real-behavior test asserting IVA-regime branching uses the enum surface; `src/aeat/application/modelo/test_actions.py`.
- [x] `W01.P07.S169` - promote the registry-schema `"draft" | "casilla" | "binding" | ...` Literal to `CasillaFieldKind(StrEnum)`; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W01.P07.S170` - add real-behavior test asserting CasillaFieldKind rejects unknown tokens; `src/aeat/domain/calculations/registry/test_schema.py`.
- [x] `W01.P07.S171` - introduce `CLASSIFIED_BY_MANUAL: Final[str] = "manual"` in `aeat.application.ledger._models`; `replace the three bare-string sites; `src/aeat/application/ledger/_models.py`.
- [x] `W01.P07.S172` - add real-behavior test asserting ledger classification reads through the constant; `src/aeat/application/ledger/test_models.py`.
- [x] `W01.P07.S173` - promote `OracleEnvironment` Literal to `StrEnum`; `replace the six default-value sites; `src/aeat/domain/calculations/registry/_live_parity.py`.
- [x] `W01.P07.S174` - add real-behavior test asserting OracleEnvironment members round-trip through every replaced default; `src/aeat/domain/calculations/registry/test_live_parity.py`.
- [x] `W01.P07.S175` - introduce `DEFAULT_CURRENCY: Final[str] = "EUR"` in `aeat.core.external_constants`; `replace the 20 `"EUR"` sites across 8 files; `src/aeat/core/external_constants.py`.
- [x] `W01.P07.S176` - add real-behavior test asserting every former currency literal now reads from the constant; `src/aeat/core/test_external_constants.py`.
- [x] `W01.P07.S177` - introduce `BINARY_MIME_TYPE: Final[str] = "application/octet-stream"` in `aeat.core.external_constants`; `replace the three sites including the already-extracted `_BINARY_MIME`; `src/aeat/core/external_constants.py`.
- [x] `W01.P07.S178` - add real-behavior test asserting every former MIME literal reads from the constant; `src/aeat/core/test_external_constants.py`.
- [x] `W01.P07.S179` - introduce `CSV_ENCODING_FALLBACK_CHAIN: tuple[str, ...]` in `aeat.core.external_constants`; `replace the inline tuple; `src/aeat/adapters/inbound/financial/providers/_csv.py`.
- [x] `W01.P07.S180` - add real-behavior test asserting the CSV provider iterates the canonical fallback chain; `src/aeat/adapters/inbound/financial/providers/test_csv.py`.
- [x] `W01.P07.S181` - introduce shared file-extension sets (`CSV_EXTENSIONS`, `PDF_EXTENSION`, `XLSX_EXTENSION`) under `src/aeat/adapters/inbound/financial/providers/_constants.py`; `src/aeat/adapters/inbound/financial/providers/_constants.py`.
- [x] `W01.P07.S182` - add real-behavior test asserting financial-provider detection reads from the shared constants; `src/aeat/adapters/inbound/financial/providers/test_detection.py`.
- [x] `W01.P07.S183` - centralize the `latin-1` / `iso-8859-1` alias normalization dict in `aeat.domain.calculations.registry._record_spec`; `src/aeat/domain/calculations/registry/_record_spec.py`.
- [x] `W01.P07.S184` - add real-behavior test asserting the alias map is the single source of truth at every decode call-site; `src/aeat/domain/calculations/registry/test_record_spec.py`.
- [x] `W01.P07.S185` - introduce `FilingStatus.FILED` (or equivalent) and replace the bare `"filed"` literals across `_app_live.py` and `_contract.py`; `src/aeat/application/operator_surface/_contract.py`.
- [x] `W01.P07.S186` - add real-behavior test asserting the FilingStatus surface is the only source for `"filed"`; `src/aeat/application/operator_surface/test_contract.py`.
- [x] `W01.P07.S187` - extract the `"COLUMNS"` env-key literal to a module-level `_COLUMNS_ENV_VAR: Final[str]`; `src/aeat/entrypoints/cli/_stdio.py`.
- [x] `W01.P07.S188` - add real-behavior test asserting CLI stdio reads the env-var via the constant; `src/aeat/entrypoints/cli/test_stdio.py`.

### Phase `W01.P08` - tighten typecheck escape hatches

Address production-side `cast()` calls and `-> Any` returns
identified in the A8 audit. Documented third-party API boundaries
stay; undocumented escapes get justified inline or replaced with
typed structures. Each fix Step is paired with a verification Step
that asserts the new typed contract holds under representative
inputs.

- [x] `W01.P08.S189` - replace `cast(T, envelope.payload)` with envelope-generic refinement or add inline rationale; `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`.
- [x] `W01.P08.S190` - add real-behavior test asserting envelope payload type is preserved across the generic boundary; `src/aeat/adapters/persistence/storage/envelope/test_secure_repository.py`.
- [x] `W01.P08.S191` - replace `cast(Any, Envelope).__class_getitem__(...)` with a typed factory method; `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`.
- [x] `W01.P08.S192` - add real-behavior test asserting the typed factory yields the correct envelope subtype per payload; `src/aeat/adapters/persistence/storage/envelope/test_secure_repository.py`.
- [x] `W01.P08.S193` - replace `cast(Callable[P, R], existing)` with a `TypeGuard` or runtime-protocol check; `src/aeat/entrypoints/cli/_errors.py`.
- [x] `W01.P08.S194` - add real-behavior test asserting the type-guard narrows correctly for valid / invalid callables; `src/aeat/entrypoints/cli/test_errors.py`.
- [x] `W01.P08.S195` - add inline rationale to every remaining production `cast()` call or refactor to remove the cast; `track each remaining cast as a Wave 2 follow-up Step; `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`.
- [x] `W01.P08.S196` - add real-behavior test asserting the inline-rationale comment survives a refactor and the cast contract still holds; `src/aeat/adapters/persistence/storage/envelope/test_secure_repository.py`.
- [x] `W01.P08.S197` - refine the Google adapter `-> Any` returns using `google-api-python-client-stubs` if present; `otherwise wrap the response in a `TypedDict`; `src/aeat/adapters/outbound/google/_api.py`.
- [x] `W01.P08.S198` - add real-behavior test asserting Google API responses validate against the typed shape; `src/aeat/adapters/outbound/google/test_api.py`.
- [x] `W01.P08.S199` - refine the calc-sheets-pull `-> Any` returns using TypedDict or pydantic; `src/aeat/adapters/outbound/google/_calc_sheets_pull.py`.
- [x] `W01.P08.S200` - add real-behavior test asserting calc-sheets pull response typing; `src/aeat/adapters/outbound/google/test_calc_sheets_pull.py`.
- [x] `W01.P08.S201` - replace `**kwargs: Any` on `invoke_cached_cli` with a TypedDict covering the Click invoke surface; `src/aeat/tests/cli_runner.py`.
- [x] `W01.P08.S202` - add real-behavior test asserting CLI test runner rejects unknown kwargs at type-check; `src/aeat/tests/test_cli_runner.py`.
- [x] `W01.P08.S203` - add overload signatures to `_scrub_value` so the recursive heterogeneous payload contract is typed precisely; `src/aeat/core/logging.py`.
- [x] `W01.P08.S204` - add real-behavior test asserting the overload contract preserves type for str / Mapping / tuple / list / set inputs; `src/aeat/core/test_logging.py`.

### Phase `W01.P09` - audit test-suite semantic intent and actual coverage

Sweep the test surface for tautological assertions, mock / patch /
skip / xfail usage outside legitimate boundary-test fixtures, real-
behavior test absence at any persistence boundary touched by an
A1..A8 fix Step, and `pytest` collection coverage versus production
module inventory. Each finding becomes its own Step; remediation
strengthens the test, never weakens or skips it.

- [x] `W01.P09.S205` - enumerate every `pytest.mark.skip` / `pytest.mark.xfail` under `src/aeat/`; `record each as a Wave 1 follow-up Step requiring removal or replacement with a real-behavior test; `src/aeat`.
- [x] `W01.P09.S206` - add real-behavior test asserting the enumeration result is zero (a `git grep`-style assertion that survives in CI); `src/aeat/test_no_skip_xfail.py`.
- [x] `W01.P09.S207` - enumerate every `unittest.mock` / `pytest-mock` import under `src/aeat/`; `classify each as legitimate boundary mock or drift; record drift sites as follow-up Steps; `src/aeat`.
- [x] `W01.P09.S208` - add real-behavior test asserting the classification result holds across the test inventory; `src/aeat/test_mock_inventory.py`.
- [x] `W01.P09.S209` - enumerate every `monkeypatch` use under `src/aeat/`; `classify each as test-isolation fixture or production-state mutation; record drift as follow-up Steps; `src/aeat`.
- [x] `W01.P09.S210` - add real-behavior test asserting monkeypatch inventory matches the classification; `src/aeat/test_monkeypatch_inventory.py`.
- [x] `W01.P09.S211` - enumerate every `assert True` / `assert 1 == 1` / `assert var == var` shape under `src/aeat/`; `remove or replace each with a real assertion; `src/aeat`.
- [x] `W01.P09.S212` - add real-behavior test asserting zero tautological assertion shapes survive in the test surface; `src/aeat/test_no_tautology.py`.
- [x] `W01.P09.S213` - enumerate every calculation test that hand-computes an expected value from the registry formula under test; `record each as a follow-up Step to re-ground against an external authority; `src/aeat/domain/calculations`.
- [x] `W01.P09.S214` - add real-behavior test asserting calculation-test expected values are sourced from registry fixtures, AEAT workbooks, BOE worked examples, or live oracle replay (per `no-tautological-calculation-tests.md`); `src/aeat/domain/calculations/test_calculation_grounding.py`.
- [x] `W01.P09.S215` - diff `pytest` collection inventory against the production module inventory under `src/aeat/`; `record every module without a paired `test_*.py` as a Wave 2 follow-up Step; `src/aeat`.
- [x] `W01.P09.S216` - add real-behavior test asserting every production module under `src/aeat/.../` has at least one paired test file (excluding legitimate test-only modules); `src/aeat/test_coverage_inventory.py`.
- [x] `W01.P09.S217` - enumerate every persistence boundary touched by a W01.P01..P08 fix Step and confirm a roundtrip test exists per `aeat-roundtrip-discipline.md`; `src/aeat`.
- [x] `W01.P09.S218` - add real-behavior test asserting persistence boundary inventory matches roundtrip-test inventory; `src/aeat/test_roundtrip_coverage.py`.
- [x] `W01.P09.S219` - sample 20 random production-test pairings for semantic-intent drift (test asserts incidental shape rather than behaviour); `record each as a follow-up Step; `src/aeat`.
- [x] `W01.P09.S220` - add real-behavior test asserting the sample-review process runs against a deterministic seed and produces reproducible output; `src/aeat/test_semantic_intent_sampler.py`.
- [x] `W01.P09.S221` - enumerate every `try: ... except: pass` shape in test files; `replace each with a specific exception assertion; `src/aeat`.
- [x] `W01.P09.S222` - add real-behavior test asserting zero bare-except shapes survive in the test surface; `src/aeat/test_no_bare_except.py`.
- [x] `W01.P09.S223` - enumerate every test that constructs a pydantic model with only the required fields populated (per `aeat-roundtrip-discipline.md`'s "populate every defaultable field" rule); `record each as a follow-up Step; `src/aeat`.
- [x] `W01.P09.S224` - add real-behavior test asserting roundtrip-fixture builders saturate every defaultable field; `src/aeat/test_roundtrip_fixture_saturation.py`.

## Wave `W02` - close Wave 2 swarm re-audit findings

Wave 2 closes the 8 regressions, 10 new drifts, and 54 survivor-missed findings surfaced by the 2026-05-30 swarm re-audit. Regressions land in P10 first (highest diagnostic priority). Survivor sweeps follow per-axis. Cross-layer constants relocate to aeat.core to prevent the application-vs-domain shadowing pattern. Authorising audit: 2026-05-30-codebase-solidification-audit.

### Phase `W02.P10` - regression fixes

Close the 8 regressions surfaced by Wave 2. These prove the enrollment habit leaked despite Wave 1 closure; highest diagnostic priority.

- [x] `W02.P10.S225` - expose detach_run_sink(sink) in aeat.core.logging and route _context.py detach through it; `src/aeat/core/logging.py`.
- [x] `W02.P10.S226` - add real-behavior test asserting attach_run_sink and detach_run_sink are symmetric and both apply SecretScrubbingFilter teardown; `src/aeat/core/test_logging.py`.
- [x] `W02.P10.S227` - delete local _now_utc helper at inventory/_service.py:97; `import canonical _now from aeat.core.time; `src/aeat/application/inventory/_service.py`.
- [x] `W02.P10.S228` - add real-behavior test asserting inventory service uses canonical _now; `src/aeat/application/inventory/test_service.py`.
- [x] `W02.P10.S229` - delete local _utc_now helper at calc_sheets/_records.py:471; `import canonical _now from aeat.core.time; `src/aeat/application/storage/calc_sheets/_records.py`.
- [x] `W02.P10.S230` - add real-behavior test asserting calc_sheets records use canonical _now; `src/aeat/application/storage/calc_sheets/test_records.py`.
- [x] `W02.P10.S231` - delete _parse_boolean helper at registry/_export_parse.py:409; `import canonical _parse_bool and wrap with registry truthy/falsy sets; `src/aeat/domain/calculations/registry/_export_parse.py`.
- [x] `W02.P10.S232` - add real-behavior test asserting registry export parser delegates to canonical _parse_bool; `src/aeat/domain/calculations/registry/test_export_parse.py`.
- [x] `W02.P10.S233` - replace bare draft string with CasillaFieldKind.DRAFT at _declarations.py:1471; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W02.P10.S234` - replace bare draft string with CasillaFieldKind.DRAFT at user_profile/_registry_contract.py:255; `src/aeat/domain/user_profile/_registry_contract.py`.
- [x] `W02.P10.S235` - replace bare draft string with CasillaFieldKind.DRAFT and convert match arm to enum case at _export.py:472; `src/aeat/application/filing/_export.py`.
- [x] `W02.P10.S236` - replace bare binding/casilla strings with CasillaFieldKind members at registry/_export.py lines 151,156,167,186; `src/aeat/domain/calculations/registry/_export.py`.
- [x] `W02.P10.S237` - add real-behavior test asserting CasillaFieldKind enum-bypass survivors are closed across all 5 sites; `src/aeat/domain/calculations/registry/test_casilla_field_kind_enrollment.py`.
- [x] `W02.P10.S238` - relocate CLASSIFIED_BY_MANUAL from application/ledger/_models.py to aeat.core.external_constants so domain layer can import it; `src/aeat/core/external_constants.py`.
- [x] `W02.P10.S239` - delete _MANUAL_CLASSIFIED_BY shadow in domain/transactions/_service.py:24 and import CLASSIFIED_BY_MANUAL from aeat.core.external_constants; `src/aeat/domain/transactions/_service.py`.
- [x] `W02.P10.S240` - add real-behavior test asserting CLASSIFIED_BY_MANUAL is the single source of truth across application and domain layers; `src/aeat/core/test_external_constants.py`.
- [x] `W02.P10.S241` - import REPLAY_ACTIVE_ENV_VAR from observability._replay in observability/_context.py:51; `delete the private _REPLAY_ACTIVE_ENV_VAR literal; `src/aeat/core/observability/_context.py`.
- [x] `W02.P10.S242` - add real-behavior test asserting REPLAY_ACTIVE_ENV_VAR has exactly one canonical definition site across observability package; `src/aeat/core/observability/test_replay.py`.

### Phase `W02.P11` - A1 exception survivor sweep

Establish master_key/_errors.py with MasterKeyReentrantError / MasterKeyTypeError / KeyDerivationError enrollment. Enroll bucket/ validators into BucketError. Close 6 application-layer enrolled-error survivors.

- [x] `W02.P11.S243` - establish src/aeat/adapters/persistence/storage/master_key/_errors.py with MasterKeyReentrantError(SecretStoreError), MasterKeyTypeError(StorageError); `src/aeat/adapters/persistence/storage/master_key/_errors.py`.
- [x] `W02.P11.S244` - migrate RuntimeError to MasterKeyReentrantError at _master_key.py:974 and :1294; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [x] `W02.P11.S245` - add real-behavior test asserting MasterKeyReentrantError envelope round-trip; `src/aeat/adapters/persistence/storage/master_key/test_master_key.py`.
- [x] `W02.P11.S246` - migrate ValueError raises in _kdf.py:44,48 and _kdf_params.py:68 to KeyDerivationError; `src/aeat/adapters/persistence/storage/master_key/_kdf.py`.
- [x] `W02.P11.S247` - migrate TypeError in _kdf_params.py:82 to KeyDerivationError; `src/aeat/adapters/persistence/storage/master_key/_kdf_params.py`.
- [x] `W02.P11.S248` - add real-behavior test asserting KeyDerivationError envelope at every migrated raise; `src/aeat/adapters/persistence/storage/master_key/test_kdf.py`.
- [x] `W02.P11.S249` - migrate ValueError raises in _dek_wrap.py:49,74,76,105 to EncryptionError (or new KeyWrapError); `src/aeat/adapters/persistence/storage/master_key/_dek_wrap.py`.
- [x] `W02.P11.S250` - add real-behavior test asserting EncryptionError envelope at every dek_wrap raise; `src/aeat/adapters/persistence/storage/master_key/test_dek_wrap.py`.
- [x] `W02.P11.S251` - migrate ValueError raises in _bucket_session.py:97-103 and _idle_timeout.py:69 to StorageValidationError or KeyDerivationError; `src/aeat/adapters/persistence/storage/master_key/_bucket_session.py`.
- [x] `W02.P11.S252` - migrate TypeError in _zeroise.py:46 to MasterKeyTypeError or StorageValidationError; `src/aeat/adapters/persistence/storage/master_key/_zeroise.py`.
- [x] `W02.P11.S253` - migrate ValueError in _recovery_record.py:34 to RecoveryVerificationError or RecoveryRecordParseError; `src/aeat/adapters/persistence/storage/master_key/_recovery_record.py`.
- [x] `W02.P11.S254` - add real-behavior test asserting master_key cluster errors all envelope-round-trip; `src/aeat/adapters/persistence/storage/master_key/test_cluster_envelopes.py`.
- [x] `W02.P11.S255` - migrate ValueError raises in bucket/_manifest.py:58,72,147 to BucketError or BucketValidationError; `src/aeat/adapters/persistence/storage/bucket/_manifest.py`.
- [x] `W02.P11.S256` - migrate ValueError raises in bucket/_export_header.py:24-53 to BucketError or BucketExportHeaderError; `src/aeat/adapters/persistence/storage/bucket/_export_header.py`.
- [x] `W02.P11.S257` - migrate TypeError in bucket/_manifest_io.py:45 to BucketError or StorageValidationError; `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`.
- [x] `W02.P11.S258` - migrate ValueError raises in bucket/_layout.py:60,62 and bucket/_keystore_paths.py:40,42 to BucketError; `src/aeat/adapters/persistence/storage/bucket/_layout.py`.
- [x] `W02.P11.S259` - add real-behavior test asserting bucket cluster errors envelope-round-trip; `src/aeat/adapters/persistence/storage/bucket/test_cluster_envelopes.py`.
- [x] `W02.P11.S260` - replace ValueError at _namespace_registry.py:119 with NamespaceRegistryError survivor; `src/aeat/adapters/persistence/storage/_namespace_registry.py`.
- [x] `W02.P11.S261` - replace ValueError at workflow/_engine.py:282 with WorkflowInputMismatchError survivor; `src/aeat/application/workflow/_engine.py`.
- [x] `W02.P11.S262` - replace ValueError at core/config.py:1249,1252 with ConfigBoundaryError survivor; `src/aeat/core/config.py`.
- [x] `W02.P11.S263` - replace ValueError at runtime.py:320 with StorageValidationError; `src/aeat/adapters/persistence/storage/runtime.py`.
- [x] `W02.P11.S264` - replace ValueError at application/modelo/_actions.py:2413 with ModeloApplicabilityFilterError(ModeloError); `src/aeat/application/modelo/_actions.py`.
- [x] `W02.P11.S265` - replace TypeError at application/diagnostics.py:416 with DiagnosticModelError survivor; `src/aeat/application/diagnostics.py`.
- [x] `W02.P11.S266` - replace TypeError at _secure_repository.py:105 with RepositorySetupError or StorageValidationError; `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`.
- [x] `W02.P11.S267` - introduce ProfileLabelAmbiguousError(WorkflowError) and replace ValueError at workflow/_profile_bucket_scan.py:103; `src/aeat/application/workflow/_errors.py`.
- [x] `W02.P11.S268` - introduce src/aeat/application/repair_integrity/_errors.py with RepairIntegrityError and RepairDecisionNotFoundError; `replace 3 ValueError raises at repair_integrity.py:230,392,415; `src/aeat/application/repair_integrity.py`.
- [x] `W02.P11.S269` - change SnapshotNotFoundError base from KeyError to (AeatError, KeyError) at _snapshot_base.py:49; `src/aeat/application/live/_snapshot_base.py`.
- [x] `W02.P11.S270` - narrow except Exception swallows at _orchestration.py:143 and _profile_health.py:146,163,298 to specific AeatError subtypes; `src/aeat/application/user_profile/_orchestration.py`.
- [x] `W02.P11.S271` - add real-behavior test asserting application-layer survivor envelopes all enrolled; `src/aeat/application/test_survivor_envelope_enrollment.py`.

### Phase `W02.P12` - A3 locale survivor sweep

Thread translated_message on every AeatLoginAssertionError raise across _authenticator.py and _clave_movil.py (9 sites). Close 9 SedeNavigationError navigation-flow raises in _declarations.py. Localize PortalNotFoundError.

- [x] `W02.P12.S272` - thread translated_message=adapters.auth.clave_movil.errors.no_persisted_session on AeatLoginAssertionError at _clave_movil.py:380 and :864; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.
- [x] `W02.P12.S273` - thread translated_message=adapters.auth.clave_movil.errors.session_expired on AeatLoginAssertionError at _clave_movil.py:385 and :1049; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.
- [x] `W02.P12.S274` - thread translated_message=adapters.auth.clave_movil.errors.storage_state_hash_mismatch on AeatLoginAssertionError at _clave_movil.py:1052; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.
- [x] `W02.P12.S275` - thread translated_message=adapters.auth.clave_movil.errors.page_missing_click on AeatLoginAssertionError at _clave_movil.py:1144; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.
- [x] `W02.P12.S276` - add real-behavior test asserting all Clave Movil AeatLoginAssertionError raises carry localized translated_message at CLI boundary; `src/aeat/adapters/outbound/aeat/auth/test_clave_movil_locale.py`.
- [x] `W02.P12.S277` - thread translated_message=adapters.auth.authenticator.errors.already_active at _authenticator.py:496; `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.
- [x] `W02.P12.S278` - thread translated_message=adapters.auth.authenticator.errors.assertion_failed at _authenticator.py:573; `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.
- [x] `W02.P12.S279` - thread translated_message=adapters.auth.authenticator.errors.resume_failed at _authenticator.py:1083; `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.
- [x] `W02.P12.S280` - thread translated_message=adapters.auth.authenticator.errors.metadata_parse_failed at _authenticator.py:1157; `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.
- [x] `W02.P12.S281` - add real-behavior test asserting authenticator AeatLoginAssertionError raises carry localized translated_message; `src/aeat/adapters/outbound/aeat/auth/test_authenticator_locale.py`.
- [x] `W02.P12.S282` - thread translated_message=adapters.sede.errors.session_expired_nav_failed on SedeNavigationError at _declarations.py:463; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W02.P12.S283` - thread translated_message=adapters.sede.errors.form_render_timeout on SedeNavigationError at _declarations.py:475; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W02.P12.S284` - thread translated_message=adapters.sede.errors.cotejo_nav_failed on SedeNavigationError at _declarations.py:841; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W02.P12.S285` - thread translated_message=adapters.sede.errors.ejercicio_unavailable on SedeNavigationError at _declarations.py:271 and :804; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W02.P12.S286` - thread translated_message on SedeParseError at _declarations.py:626,630,642 (listbox missing / justificante column); `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W02.P12.S287` - thread translated_message=adapters.sede.errors.listing_nav_failed on SedeNavigationError at _declarations.py:453; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W02.P12.S288` - thread translated_message=adapters.sede.errors.no_auth_session on SedeNavigationError at _censo_live.py:80; `src/aeat/adapters/outbound/aeat/sede/_censo_live.py`.
- [x] `W02.P12.S289` - add real-behavior test asserting all _declarations.py navigation-flow raises localize at CLI boundary; `src/aeat/adapters/outbound/aeat/sede/test_declarations_locale.py`.
- [x] `W02.P12.S290` - thread translated_message on PortalNotFoundError at application/portals/_service.py:97; `src/aeat/application/portals/_service.py`.
- [x] `W02.P12.S291` - add real-behavior test asserting PortalNotFoundError envelope localized; `src/aeat/application/portals/test_service.py`.

### Phase `W02.P13` - A4 + A7 + A8 new drift cleanup

Close A4 JSON-decode boundaries (crypto + master-key), A7 Playwright wait-state literals (15+ sites), browser timeout magic numbers, MIME constants, env-write doc comments, A8 missing CAST-RATIONALE markers.

- [x] `W02.P13.S292` - wrap json.loads at crypto/_encrypted_columns.py:185 in EncryptedPayload(BaseModel) or model_validate; `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py`.
- [x] `W02.P13.S293` - add roundtrip test asserting EncryptedPayload validates and rejects malformed; `src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py`.
- [x] `W02.P13.S294` - define EnvelopeDocument(BaseModel) and use model_validate_json at master_key/_master_key.py:1117; `src/aeat/adapters/persistence/storage/master_key/_master_key.py`.
- [x] `W02.P13.S295` - add roundtrip test asserting EnvelopeDocument validates and rejects malformed; `src/aeat/adapters/persistence/storage/master_key/test_envelope_document.py`.
- [x] `W02.P13.S296` - introduce src/aeat/adapters/outbound/aeat/sede/_browser_constants.py with PLAYWRIGHT_WAIT_DOMCONTENTLOADED and PLAYWRIGHT_WAIT_NETWORKIDLE; `src/aeat/adapters/outbound/aeat/sede/_browser_constants.py`.
- [x] `W02.P13.S297` - migrate 15+ domcontentloaded/networkidle literals across _declarations.py, _iva_compensation_wallet.py, _groi_check.py, _nif_iva_check.py, _censo_live.py, _walker.py to use the constants; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W02.P13.S298` - add real-behavior test asserting Playwright wait-state constants are the single source of truth across sede adapter; `src/aeat/adapters/outbound/aeat/sede/test_playwright_wait_constants.py`.
- [x] `W02.P13.S299` - extract browser timeout constants (_VISIBLE_PROBE_TIMEOUT_MS, _ELEMENT_WAIT_TIMEOUT_MS) at _renta_web_open.py:273,341 and _walker.py:301 or import _declarations.py canonicals if semantics match; `src/aeat/adapters/outbound/aeat/sede/_renta_web_open.py`.
- [x] `W02.P13.S300` - add real-behavior test asserting browser timeout literals are named constants; `src/aeat/adapters/outbound/aeat/sede/test_browser_timeouts.py`.
- [x] `W02.P13.S301` - introduce JSON_MIME_TYPE: Final[str] = application/json and CSV_MIME_TYPE: Final[str] = text/csv in aeat.core.external_constants; `src/aeat/core/external_constants.py`.
- [x] `W02.P13.S302` - migrate application/json literal at _declarations.py:1223 and text/csv literal at application/export/_tabular.py:69 to constants; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W02.P13.S303` - add real-behavior test asserting MIME-type constants are sole source; `src/aeat/core/test_external_constants.py`.
- [x] `W02.P13.S304` - document intentional env-write at _replay.py:172,179 with # env-write: intentional scoped context-manager comment; `src/aeat/core/observability/_replay.py`.
- [x] `W02.P13.S305` - wrap _stdio.py:89 os.environ COLUMNS write in a context-manager to scope the mutation; `src/aeat/entrypoints/cli/_stdio.py`.
- [x] `W02.P13.S306` - add real-behavior test asserting _stdio.py COLUMNS write is scoped and reverted; `src/aeat/entrypoints/cli/test_stdio.py`.
- [x] `W02.P13.S307` - swap raw logging.getLogger and replace print() at sede/test_renta_web_open_explore_dom.py:57,175,208 to use get_logger and _log.debug; `src/aeat/adapters/outbound/aeat/sede/test_renta_web_open_explore_dom.py`.
- [x] `W02.P13.S308` - swap raw logging.getLogger at storage/test_google_drive_live.py:42 to get_logger; `src/aeat/adapters/outbound/storage/test_google_drive_live.py`.
- [x] `W02.P13.S309` - add CAST-RATIONALE-SANITIZER-PIKEPDF-OPERANDS marker at sanitizer/_streams.py:152; `src/aeat/adapters/inbound/sanitizer/_streams.py`.
- [x] `W02.P13.S310` - add CAST-RATIONALE-LEDGER-RULE-REPO-INJECT marker at ledger/_actions.py:3503 and :3547; `src/aeat/application/ledger/_actions.py`.
- [x] `W02.P13.S311` - add CAST-RATIONALE-WIZARD-COMMAND-INJECT marker at wizard/_commands.py:928; `src/aeat/application/wizard/_commands.py`.
- [x] `W02.P13.S312` - add real-behavior test asserting all production cast() calls carry CAST-RATIONALE marker; `src/aeat/test_cast_rationale_inventory.py`.
- [x] `W02.P13.S313` - enroll _pdf_n26.py:287,288 to DEFAULT_CURRENCY (the 2 sites missed in Wave 1 currency sweep); `src/aeat/adapters/inbound/financial/providers/_pdf_n26.py`.
- [x] `W02.P13.S314` - add real-behavior test asserting financial provider DEFAULT_CURRENCY enrollment is complete; `src/aeat/adapters/inbound/financial/providers/test_pdf_n26.py`.

## Wave `W03` - aeat.core adoption: relocate cross-hexagonal canonicals + enroll bypass sites

Wave 3 closes the architectural pattern that produced Wave 2 regressions: every cross-hexagonal canonical relocates to aeat.core, and every production bypass site (datetime.now, fromisoformat, quantize, _ensure_utc, _coerce_decimal, etc.) enrolls into the canonical aeat.core symbol. Audit findings: 2 cross-hexagonal relocations (W3 task #11), ~54 enrollment bypasses (W3 task #13). The aeat.core surface itself is clean (zero hexagonal-direction violations per W3 task #12). Authorising audit findings tracked in W3 task list #10-#13.

### Phase `W03.P14` - cross-hexagonal canonical relocations

Relocate SETUP_FLOW/WIZARD_FLOWS and project_answers/SetupAnswers from aeat.application.wizard to aeat.core so domain modules stop reaching upward via deferred lazy imports. Same structural fix as the W02 CLASSIFIED_BY_MANUAL relocation. Plus proactive AggregationSourceKind relocation.

- [x] `W03.P14.S315` - introduce aeat.core.profile_catalogue with SETUP_FLOW and WIZARD_FLOWS Protocol or move the descriptors themselves; `src/aeat/core/profile_catalogue.py`.
- [x] `W03.P14.S316` - migrate aeat.application.wizard._catalogue to import canonical from aeat.core.profile_catalogue; `relocate SETUP_FLOW/WIZARD_FLOWS definitions; `src/aeat/application/wizard/_catalogue.py`.
- [x] `W03.P14.S317` - update aeat.domain.deadlines._profiles to import SETUP_FLOW/WIZARD_FLOWS from aeat.core.profile_catalogue and remove deferred lazy import; `src/aeat/domain/deadlines/_profiles.py`.
- [x] `W03.P14.S318` - update aeat.domain.profile._keys to import SETUP_FLOW/WIZARD_FLOWS from aeat.core.profile_catalogue and remove deferred lazy import; `src/aeat/domain/profile/_keys.py`.
- [x] `W03.P14.S319` - update aeat.entrypoints.cli._config to import SETUP_FLOW/WIZARD_FLOWS from aeat.core.profile_catalogue; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W03.P14.S320` - add real-behavior test asserting SETUP_FLOW/WIZARD_FLOWS canonical home is aeat.core and no deferred lazy upward imports survive; `src/aeat/core/test_profile_catalogue.py`.
- [x] `W03.P14.S321` - introduce SetupAnswers model in aeat.core (or a Protocol it satisfies) so domain can consume the typed projection without reaching into application.wizard; `src/aeat/core/profile.py`.
- [x] `W03.P14.S322` - relocate project_answers function to aeat.core.profile or expose its result type via Protocol; `aeat.application.wizard._persistence keeps the implementation but routes through the core interface; `src/aeat/core/profile.py`.
- [x] `W03.P14.S323` - update aeat.domain.deadlines._profiles to import project_answers/SetupAnswers from aeat.core.profile and remove deferred upward imports; `src/aeat/domain/deadlines/_profiles.py`.
- [x] `W03.P14.S324` - add real-behavior test asserting project_answers/SetupAnswers canonical home and domain importer purity; `src/aeat/core/test_profile.py`.
- [x] `W03.P14.S325` - proactively relocate AggregationSourceKind from aeat.application.aggregation._source_kinds to aeat.core (or a domain-reachable home) before a domain consumer materialises the deferred Wave 1 finding; `src/aeat/core/aggregation.py`.
- [x] `W03.P14.S326` - migrate 5 application-layer importers of AggregationSourceKind to the new canonical home; `src/aeat/application/aggregation/_service.py`.
- [x] `W03.P14.S327` - add real-behavior test asserting AggregationSourceKind canonical home and importer enrollment; `src/aeat/core/test_aggregation.py`.

### Phase `W03.P15` - _clock._now enrollment sweep

Replace 19+ inline datetime.now(UTC) sites across adapters, application, domain, and core/observability with _now from aeat.core.time._clock. Highest blast radius bypass cluster from W3 audit task #13.

- [x] `W03.P15.S328` - enroll datetime.now(UTC) sites in adapters/outbound/storage/_local.py:202,269,271,337,339 to _now from aeat.core.time._clock; `src/aeat/adapters/outbound/storage/_local.py`.
- [x] `W03.P15.S329` - enroll datetime.now(UTC) sites in adapters/outbound/aeat/sede/_declarations.py:919,1243,1692,1739 to _now; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W03.P15.S330` - enroll datetime.now(UTC) sites in adapters/outbound/aeat/auth/_authenticator.py:550,906,1000 to _now; `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.
- [x] `W03.P15.S331` - enroll datetime.now(UTC) sites in adapters/outbound/aeat/auth/_clave_movil.py:387,506,1002,1057,1454,1460,1488 to _now; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.
- [x] `W03.P15.S332` - enroll datetime.now(UTC) in adapters/outbound/aeat/browser/_site_health_parsers.py:66 to _now; `src/aeat/adapters/outbound/aeat/browser/_site_health_parsers.py`.
- [x] `W03.P15.S333` - enroll datetime.now(UTC) sites in adapters/persistence/storage/_rotation.py:333,349 to _now; `src/aeat/adapters/persistence/storage/_rotation.py`.
- [x] `W03.P15.S334` - enroll datetime.now(UTC) in domain/transactions/_service.py:115 to _now; `src/aeat/domain/transactions/_service.py`.
- [x] `W03.P15.S335` - enroll datetime.now(UTC) in domain/filing/_complementaria_repository.py:100 to _now; `src/aeat/domain/filing/_complementaria_repository.py`.
- [x] `W03.P15.S336` - enroll datetime.now(tz=UTC) in domain/filing/_validator.py:220 to _now; `src/aeat/domain/filing/_validator.py`.
- [x] `W03.P15.S337` - enroll datetime.now(UTC) sites in core/observability/_context.py:128,296 to _now (noting this is intra-core); `src/aeat/core/observability/_context.py`.
- [x] `W03.P15.S338` - add real-behavior test asserting zero datetime.now(UTC) inline calls survive in production code under src/aeat/ (excluding aeat.core.time._clock and documented escapes); `src/aeat/test_clock_enrollment_inventory.py`.

### Phase `W03.P16` - UTC validator enrollment sweep

Replace 9 inline 'if tzinfo is None or utcoffset is None' guards across persistence/storage, domain/transactions, application/review, core/corpus_manifest, core/observability with _validate_utc_aware from aeat.core.time._utc. Plus the _ensure_utc reimpl in bucket/_export_header.py and the _utc coerce variant in auth/_acquisition_lock.py.

- [x] `W03.P16.S339` - replace _ensure_utc full reimpl in bucket/_export_header.py:25 with _validate_utc_aware from aeat.core.time._utc; `src/aeat/adapters/persistence/storage/bucket/_export_header.py`.
- [x] `W03.P16.S340` - replace inline tzinfo guards in envelope/_envelope.py:138 and :342 with _validate_utc_aware; `src/aeat/adapters/persistence/storage/envelope/_envelope.py`.
- [x] `W03.P16.S341` - replace inline tzinfo guard in secret_store/_secret_store.py:99 with _validate_utc_aware; `src/aeat/adapters/persistence/storage/secret_store/_secret_store.py`.
- [x] `W03.P16.S342` - replace inline tzinfo guard in application/review/_models.py:65 with _validate_utc_aware (also migrate the bare ValueError to a typed error); `src/aeat/application/review/_models.py`.
- [x] `W03.P16.S343` - replace inline tzinfo guard in domain/transactions/_raw_transaction.py:88 with _validate_utc_aware (preserve TransactionValidationError raise via wrapper); `src/aeat/domain/transactions/_raw_transaction.py`.
- [x] `W03.P16.S344` - replace inline tzinfo guard in domain/transactions/_models.py:158 with _validate_utc_aware (preserve TransactionValidationError raise via wrapper); `src/aeat/domain/transactions/_models.py`.
- [x] `W03.P16.S345` - replace inline tzinfo guard in core/corpus_manifest/__init__.py:117 with _validate_utc_aware (preserve CorpusManifestError raise via wrapper); `src/aeat/core/corpus_manifest/__init__.py`.
- [x] `W03.P16.S346` - replace inline tzinfo guard in core/observability/_models.py:334 with _validate_utc_aware; `src/aeat/core/observability/_models.py`.
- [x] `W03.P16.S347` - replace _utc coerce variant in application/auth/_acquisition_lock.py:259 with _coerce_utc_aware (handle None separately at call-site); `src/aeat/application/auth/_acquisition_lock.py`.
- [x] `W03.P16.S348` - add real-behavior test asserting zero inline tzinfo guards survive in production code (canonical helpers carry the contract); `src/aeat/test_utc_validator_enrollment_inventory.py`.

### Phase `W03.P17` - parsing canonical enrollment

Replace 10+ date.fromisoformat() inline + _parse_date reimpl in _notifications.py + 3 inline bool-string parsing sites with the aeat.core.parsing canonicals (_parse_iso8601_date, _parse_ddmmyyyy_date, _parse_bool).

- [x] `W03.P17.S349` - replace _parse_date full reimpl in sede/_notifications.py:316 with _parse_ddmmyyyy_date from aeat.core.parsing._dates; `src/aeat/adapters/outbound/aeat/sede/_notifications.py`.
- [x] `W03.P17.S350` - replace bare date.fromisoformat in application/calculations/_row_set_assembly.py:187 with _parse_iso8601_date; `src/aeat/application/calculations/_row_set_assembly.py`.
- [x] `W03.P17.S351` - replace bare date.fromisoformat in domain/profile/_marriage_facts.py:88,99 with _parse_iso8601_date; `src/aeat/domain/profile/_marriage_facts.py`.
- [x] `W03.P17.S352` - replace bare date.fromisoformat in domain/profile/_descendant_facts.py:99,101,159,164 with _parse_iso8601_date; `src/aeat/domain/profile/_descendant_facts.py`.
- [x] `W03.P17.S353` - replace bare date.fromisoformat in domain/profile/family.py:83,181,211 with _parse_iso8601_date; `src/aeat/domain/profile/family.py`.
- [x] `W03.P17.S354` - replace shadow truthy frozenset in registry/_export_parse.py:414 with _parse_bool delegation (no shadow set); `src/aeat/domain/calculations/registry/_export_parse.py`.
- [x] `W03.P17.S355` - replace inline value.lower() truthy check in wizard/_setup_answers.py:242 with _parse_bool; `src/aeat/application/wizard/_setup_answers.py`.
- [x] `W03.P17.S356` - replace inline value.lower() truthy check in domain/user_profile/_values.py:82 with _parse_bool; `src/aeat/domain/user_profile/_values.py`.
- [x] `W03.P17.S357` - add real-behavior test asserting zero inline date.fromisoformat / bool-string-coerce survive in production; `src/aeat/test_parsing_enrollment_inventory.py`.

### Phase `W03.P18` - decimal canonical enrollment

Replace 5 inline value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) with _round_to_cents from aeat.domain.fincas._rounding. Replace 2 local _coerce_decimal reimpl + 2 bare Decimal(str(...)) with coerce_decimal. Replace 2 format_decimal bypasses.

- [x] `W03.P18.S358` - replace inline quantize at entrypoints/cli/_modelo.py:2527,2598,2604 with _round_to_cents from aeat.domain.fincas._rounding; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `W03.P18.S359` - replace inline quantize at application/invoices/_projection.py:124 with _round_to_cents; `src/aeat/application/invoices/_projection.py`.
- [x] `W03.P18.S360` - replace inline quantize at domain/calculations/registry/_formula_runtime.py:1206 with _round_to_cents; `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [x] `W03.P18.S361` - replace inline quantize at domain/iva/_prorrata.py:430 with _round_to_cents; `src/aeat/domain/iva/_prorrata.py`.
- [x] `W03.P18.S362` - replace inline quantize at adapters/outbound/aeat/export/_formats/_deserialise.py:100,110 with _round_to_cents; `src/aeat/adapters/outbound/aeat/export/_formats/_deserialise.py`.
- [x] `W03.P18.S363` - replace inline quantize at adapters/outbound/aeat/export/_formats/_record_spec.py:316 with _round_to_cents and route format_decimal through aeat.core.decimal._format; `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py`.
- [x] `W03.P18.S364` - replace local _coerce_decimal reimpl in application/review/_edit.py:126 with coerce_decimal from aeat.core.decimal._coerce; `src/aeat/application/review/_edit.py`.
- [x] `W03.P18.S365` - replace local _coerce_decimal reimpl in domain/calculations/registry/_schema.py:48 with coerce_decimal; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W03.P18.S366` - replace bare Decimal(str(...)) in adapters/inbound/financial/providers/_base.py:393 with coerce_decimal; `src/aeat/adapters/inbound/financial/providers/_base.py`.
- [x] `W03.P18.S367` - replace bare Decimal(str(...)) in application/overview/__init__.py:795 with coerce_decimal; `src/aeat/application/overview/__init__.py`.
- [x] `W03.P18.S368` - add real-behavior test asserting zero inline value.quantize(Decimal(0.01),ROUND_HALF_UP) and bare Decimal(str()) coercion survive in production; `src/aeat/test_decimal_enrollment_inventory.py`.

## Wave `W04` - close Wave 4 audit findings + tighten W2/W3 scope gaps

Wave 4 closes the 53 findings from the 2026-05-30 re-audit: 5 W2 locale-Step scope gaps in clave_movil/authenticator/declarations (sibling raises the original Step did not touch), 1 A7 Playwright wait-state regression in notifications/renta_web_open, 1 A5 SetupAnswers duplicate class hygiene, 11 new A1 raises in previously-unaudited modules (calculations, aggregation, auth/operator, core/profile), 11 new A7 enum/constant bypasses (provider_id dispatch chain, _ProviderProbeOutcome.result free-form string, MetadataMatchState Literal inline, etc.). Three consecutive zero-strict-file:line-regression waves now achieved; this wave must also tighten the Step-scope discipline to prevent W2-style partial-fix completions. Authorising audit findings: Wave 4 task #16.

### Phase `W04.P19` - A3 locale W2-scope-completions + survivor sweep

Close 5 W2-Step-scope gaps in _clave_movil.py (3 sites), _authenticator.py (6 sites including 4 originally-flagged), _declarations.py (4 Playwright interaction failures). Plus 11 locale survivors (WorkUnit errors, TransactionValidationError, AmendmentVerificationRefusedError, etc) and 4 f-string-as-locale-key in aggregation errors.

- [x] `W04.P19.S369` - thread translated_message=adapters.auth.clave_movil.errors.already_active on AeatLoginAssertionError at _clave_movil.py:334; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.
- [x] `W04.P19.S370` - thread translated_message=adapters.auth.clave_movil.errors.verify_requires_active_context at _clave_movil.py:488; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.
- [x] `W04.P19.S371` - thread translated_message=adapters.auth.clave_movil.errors.metadata_invalid at _clave_movil.py:885; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.
- [x] `W04.P19.S372` - thread translated_message=adapters.auth.authenticator.errors.closing at _authenticator.py:698; `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.
- [x] `W04.P19.S373` - thread translated_message=adapters.auth.authenticator.errors.no_active_context at _authenticator.py:701; `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.
- [x] `W04.P19.S374` - thread translated_message=adapters.auth.authenticator.errors.capture_requires_active_session at _authenticator.py:729; `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.
- [x] `W04.P19.S375` - thread translated_message=adapters.auth.authenticator.errors.no_context_capture_storage at _authenticator.py:953; `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.
- [x] `W04.P19.S376` - thread translated_message=adapters.auth.authenticator.errors.session_stale at _authenticator.py:685; `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.
- [x] `W04.P19.S377` - thread translated_message=adapters.auth.authenticator.errors.already_active_before_resume at _authenticator.py:744 (AuthValidationError); `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.
- [x] `W04.P19.S378` - thread translated_message=adapters.auth.authenticator.errors.capture_requires_certificate at _authenticator.py:962; `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.
- [x] `W04.P19.S379` - thread translated_message=adapters.auth.authenticator.errors.context_marker_missing at _authenticator.py:1115; `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.
- [x] `W04.P19.S380` - thread translated_message=adapters.auth.authenticator.errors.persisted_session_verification_failed at _authenticator.py:1043 (_PersistedSessionInvalidError); `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.
- [x] `W04.P19.S381` - thread translated_message=adapters.auth.clave_movil.errors.approval_timeout at _clave_movil.py:953; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.
- [x] `W04.P19.S382` - thread translated_message=adapters.auth.clave_movil.errors.dni_nie_not_set at _clave_movil.py:618; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.
- [x] `W04.P19.S383` - thread translated_message on 4 SedeNavigationError Playwright interaction sites at _declarations.py:521,540,558,591; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W04.P19.S384` - thread translated_message on WorkUnitMutationRefusedError at _actions.py:721; `src/aeat/application/modelo/_actions.py`.
- [x] `W04.P19.S385` - thread translated_message on WorkUnitAlreadyDiscardedError at _actions.py:782; `src/aeat/application/modelo/_actions.py`.
- [x] `W04.P19.S386` - thread translated_message on AmendmentVerificationRefusedError at _actions.py:2074 and 2081; `src/aeat/application/modelo/_actions.py`.
- [x] `W04.P19.S387` - thread translated_message on WorkflowInputMismatchError at _actions.py:404; `src/aeat/application/modelo/_actions.py`.
- [x] `W04.P19.S388` - thread translated_message on TransactionValidationError at ledger/_actions.py:232 and 238; `src/aeat/application/ledger/_actions.py`.
- [x] `W04.P19.S389` - thread translated_message on UnsupportedBundleSchemaVersionError at _config/__init__.py:705; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `W04.P19.S390` - replace f-string-as-locale-key in AggregationPeriodError at _prorrata.py:156 with dotted key + context vars; `src/aeat/application/aggregation/_prorrata.py`.
- [x] `W04.P19.S391` - replace f-string-as-locale-key in AggregationUnsupportedModeloError at _grouping.py:105 with dotted key + context vars; `src/aeat/application/aggregation/_grouping.py`.
- [x] `W04.P19.S392` - replace f-string-as-locale-key in AggregationValidationError at _prorrata.py:223 with dotted key; `src/aeat/application/aggregation/_prorrata.py`.
- [x] `W04.P19.S393` - replace f-string-as-locale-key in AggregationValidationError at _prorrata.py:231 with dotted key; `src/aeat/application/aggregation/_prorrata.py`.
- [x] `W04.P19.S394` - wrap _typer.echo next-hint label at wizard/_commands.py:926 in tr; `src/aeat/application/wizard/_commands.py`.
- [x] `W04.P19.S395` - wrap typer.echo namespace+count labels at diagnostics/secure_objects.py:50-51 in tr; `src/aeat/diagnostics/secure_objects.py`.
- [x] `W04.P19.S396` - add real-behavior test asserting all auth + sede + modelo + aggregation locale Steps localize at the operator surface; `src/aeat/test_locale_coverage_inventory.py`.

### Phase `W04.P20` - A7 hardcoded + enum bypass cleanup

Close 1 regression (Playwright wait-state literals in notifications + renta_web_open despite W3 _browser_constants existing) and 11 new bypasses including provider_id dispatch enum, _ProviderProbeOutcome.result enum, MetadataMatchState StrEnum, PDF_MIME_TYPE constant, WorkbookScanStatus, sede latin-1 encoding constant.

- [x] `W04.P20.S397` - enroll bare domcontentloaded/networkidle literals at _notifications.py:450,459 and _renta_web_open.py:182 to PLAYWRIGHT_WAIT_* constants from _browser_constants.py; `src/aeat/adapters/outbound/aeat/sede/_notifications.py`.
- [x] `W04.P20.S398` - introduce PLAYWRIGHT_TIMEOUT_SHORT_MS=2_000 in _browser_constants.py and enroll _walker.py:304; `src/aeat/adapters/outbound/aeat/sede/_browser_constants.py`.
- [x] `W04.P20.S399` - introduce LedgerProviderID(StrEnum) covering auto/csv/ofx/qfx/xlsx/excel/n26/pdf/pdf-n26 and replace provider_id dispatch chain at ledger/_actions.py:2056-2072; `src/aeat/application/ledger/_actions.py`.
- [x] `W04.P20.S400` - add real-behavior test asserting LedgerProviderID covers every dispatch literal in the codebase; `src/aeat/application/ledger/test_provider_id_enum.py`.
- [x] `W04.P20.S401` - introduce SEDE_BODY_ENCODING=latin-1 constant and enroll _declarations.py:1399 and _export_parse.py:208,213; `src/aeat/adapters/outbound/aeat/sede/_browser_constants.py`.
- [x] `W04.P20.S402` - introduce PDF_MIME_TYPE=application/pdf in external_constants and enroll _declarations.py:892,1684 + _walker.py:247 substring sniffs; `src/aeat/core/external_constants.py`.
- [x] `W04.P20.S403` - use AuthAcquisitionLockState.ABSENT identity comparison at _operator.py:1102 instead of .value string check; `src/aeat/application/auth/_operator.py`.
- [x] `W04.P20.S404` - introduce ProviderProbeResult(StrEnum) with 11 members (no_provider, no_path_set, file_missing, unreadable, corrupt, expired, expiring, ok, identity_unset, invalid_identity, plus any missed) and migrate _operator.py:760-927 free-form result string field; `src/aeat/application/auth/_operator.py`.
- [x] `W04.P20.S405` - introduce DeadlineRole(StrEnum) with INFORMATIONAL plus other workflow roles and migrate _engine.py:625,662; `src/aeat/application/workflow/_engine.py`.
- [x] `W04.P20.S406` - introduce FilingWindowState(StrEnum) covering absent + other states and migrate _engine.py:661; `src/aeat/application/workflow/_engine.py`.
- [x] `W04.P20.S407` - introduce WorkflowEnvelopeReasonClass(StrEnum) and WorkbookScanStatus(StrEnum) and migrate _persistence.py:180,211,214 + _workbook_parity.py:42,116,1133,1162; `src/aeat/application/workflow/_persistence.py`.
- [x] `W04.P20.S408` - promote PDF_EXTENSION + XLSX_EXTENSION + XLSM_EXTENSION from financial providers _constants.py to external_constants (cross-layer shared file extensions); `src/aeat/core/external_constants.py`.
- [x] `W04.P20.S409` - migrate domain/calculations/registry/_record_design.py:91,93 and _workbook_parity.py:501,851 to use the promoted extension constants; `src/aeat/domain/calculations/registry/_record_design.py`.
- [x] `W04.P20.S410` - introduce MetadataMatchState(StrEnum) and migrate _calc_sheets_pull.py:216,292,329 Literal-inline to StrEnum; `src/aeat/adapters/outbound/google/_calc_sheets_pull.py`.
- [x] `W04.P20.S411` - add real-behavior inventory test asserting zero bare domcontentloaded/networkidle/pdf-mime/latin-1 literals survive in production; `src/aeat/test_hardcoded_constants_inventory.py`.

### Phase `W04.P21` - A1 exception survivor sweep

Close 9 non-pydantic raises in previously-unaudited modules (calculations, aggregation/_source_mesh, auth/_diagnostics, auth/_sessions, wizard/_persistence, core/profile, ledger/_actions), plus 2 silent except Exception swallows in auth/_operator that mask errors without logging.

- [x] `W04.P21.S412` - introduce ProfileRegistrationError(CoreError) or use ConfigurationError; `replace RuntimeError at core/profile.py:82; `src/aeat/core/profile.py`.
- [x] `W04.P21.S413` - replace TypeError at auth/_sessions.py:408 with SessionDeserializationError(AuthSessionUnavailableError); `src/aeat/application/auth/_sessions.py`.
- [x] `W04.P21.S414` - introduce IvaCompensationError or use existing IvaCompensationModeloError; `replace ValueError at calculations/_iva_compensation_history.py:102,133,333; `src/aeat/application/calculations/_iva_compensation_history.py`.
- [x] `W04.P21.S415` - replace ValueError at calculations/_binding_prefill.py:347 with ModeloApplicabilityFilterError (W2 enrolled); `src/aeat/application/calculations/_binding_prefill.py`.
- [x] `W04.P21.S416` - introduce AuthDiagnosticPayloadError or use AuthDiagnosticPhoneStateError; `replace ValueError at auth/_diagnostics.py:219,226; `src/aeat/application/auth/_diagnostics.py`.
- [x] `W04.P21.S417` - replace ValueError at wizard/_persistence.py:141 with WorkflowInputMismatchError (W2 enrolled); `src/aeat/application/wizard/_persistence.py`.
- [x] `W04.P21.S418` - introduce SourceMeshError(CoreValidationError); `replace ValueError at aggregation/_source_mesh.py:89,91,119,121; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `W04.P21.S419` - narrow silent except Exception swallow at auth/_operator.py:900 (certificate load); `add log.debug + specific exception types; `src/aeat/application/auth/_operator.py`.
- [x] `W04.P21.S420` - narrow silent except Exception swallow at auth/_operator.py:647 (profile tax-id probe); `add log.debug + specific exception types; `src/aeat/application/auth/_operator.py`.
- [x] `W04.P21.S421` - add real-behavior test asserting all new error classes registered + envelope round-trip; `src/aeat/application/test_w04_p21_survivors.py`.

### Phase `W04.P22` - small-axis cleanup: A2, A5, A6

Close A2 get_logger swap in core/profile_catalogue, A5 SetupAnswers duplicate-class collapse + CounterpartSourceKind canonicalisation + _parse_date wrapper consolidation, A6 ApoderadoService dead-code disposition + FinancialProvider @abstractmethod decorators.

- [x] `W04.P22.S422` - swap import logging+getLogger with get_logger at core/profile_catalogue.py:20-23; `src/aeat/core/profile_catalogue.py`.
- [x] `W04.P22.S423` - complete SetupAnswers duplicate-class collapse: delete application/wizard/_setup_answers.py SetupAnswers class, migrate _verifier.py + 4 test files to aeat.core.profile.SetupAnswers; `src/aeat/application/wizard/_setup_answers.py`.
- [x] `W04.P22.S424` - canonicalize CounterpartSourceKind to single domain definition; `align divergent Literal members between application/aggregation/_counterpart.py:28 and domain/calculations/registry/_bindings.py:1627; `src/aeat/domain/calculations/registry/_bindings.py`.
- [x] `W04.P22.S425` - consolidate 3 _parse_date wrapper survivors at sede/_notifications.py:316, sede/_censo.py:249, domain/deadlines/_profiles.py:195 into shared aeat.core.parsing._dates._parse_date with error-policy parameter; `src/aeat/core/parsing/_dates.py`.
- [x] `W04.P22.S426` - audit ApoderadoService + ApoderadoConfiguration in application/auth/_apoderado.py: if 0 callers in production, delete; `else integrate into auth operator flow with imports; `src/aeat/application/auth/_apoderado.py`.
- [x] `W04.P22.S427` - add @property @abstractmethod decorators on FinancialProvider corpus attributes (verification_source, provisional_pending_specimen) at _base.py for static enforcement; `src/aeat/adapters/inbound/financial/providers/_base.py`.
- [x] `W04.P22.S428` - add real-behavior test asserting small-axis cleanup landed; `src/aeat/test_w04_p22_cleanup.py`.

## Wave `W05` - close Wave 5 audit findings: 2 regressions + 38 new/survivor

Wave 5 audit broke the four-consecutive-zero-regression streak with 2 strict file:line regressions: A3 WorkflowError passes tr() as positional message instead of translated_message= (workflow/_persistence.py:105-106), and A7 test_stdio bare os.environ['COLUMNS'] despite _COLUMNS_ENV_VAR import in same file. Plus 38 new/survivor findings to close. The recurring-epic counter resets; we need zero-regression Wave 6 audit to restart the close-condition path.

### Phase `W05.P23` - A3 locale: regression fix + workflow translated_message sweep

Close 1 regression (WorkflowError tr-positional at _persistence.py:105), thread translated_message on 3 W4-introduced classes (SessionDeserializationError, ProfileRegistrationError, AuthProviderReservedError), and 11 new workflow-engine + persistence + adapters + resume bare-string raises.

- [ ] `W05.P23.S429` - fix regression: route WorkflowError at workflow/_persistence.py:105-106 through translated_message= instead of positional tr() arg; `src/aeat/application/workflow/_persistence.py`.
- [ ] `W05.P23.S430` - thread translated_message on SessionDeserializationError at auth/_sessions.py:419; `src/aeat/application/auth/_sessions.py`.
- [ ] `W05.P23.S431` - thread translated_message on AuthProviderReservedError at auth/_operator.py:1215; `src/aeat/application/auth/_operator.py`.
- [ ] `W05.P23.S432` - thread translated_message on ProfileRegistrationError at core/profile.py:92; `src/aeat/core/profile.py`.
- [ ] `W05.P23.S433` - thread translated_message on ProfileLabelAmbiguousError at workflow/_profile_bucket_scan.py:104; `src/aeat/application/workflow/_profile_bucket_scan.py`.
- [ ] `W05.P23.S434` - thread translated_message on 4 WorkflowResumeRefusedError sites at workflow/_resume.py:80,84,88,94; `src/aeat/application/workflow/_resume.py`.
- [ ] `W05.P23.S435` - thread translated_message on WorkflowError at workflow/_persistence.py:141 (state-write-invalid-payload); `src/aeat/application/workflow/_persistence.py`.
- [ ] `W05.P23.S436` - thread translated_message on WorkflowError at workflow/_persistence.py:311 (run-not-found); `src/aeat/application/workflow/_persistence.py`.
- [ ] `W05.P23.S437` - thread translated_message on WorkflowError at workflow/_engine.py:97,111 (period-registry-year-unresolvable); `src/aeat/application/workflow/_engine.py`.
- [ ] `W05.P23.S438` - thread translated_message on WorkflowError at workflow/_resume.py:139 (no-run-for-period); `src/aeat/application/workflow/_resume.py`.
- [ ] `W05.P23.S439` - thread translated_message on 3 WorkflowError adapter-missing raises at workflow/_adapters.py:194,196,198; `src/aeat/application/workflow/_adapters.py`.
- [ ] `W05.P23.S440` - thread translated_message on WorkflowError run-id-invalid raises at workflow/_persistence.py:389,392; `src/aeat/application/workflow/_persistence.py`.
- [ ] `W05.P23.S441` - convert tr-f-string-as-key positional at cli/_config/_google.py:164 to translated_message= with static key + context; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `W05.P23.S442` - assert wizard flow.id description keys exist statically at cli/_commands.py:939 module-init via inventory test; `src/aeat/application/wizard/_commands.py`.
- [ ] `W05.P23.S443` - add aggregate test asserting all W05.P23 raises envelope-localize at operator surface; `src/aeat/test_w05_p23_locale_coverage.py`.

### Phase `W05.P24` - A1 exceptions: W3 class registry binding + except-narrowing sweep

Rebase WizardCatalogueNotRegisteredError + ProjectAnswersNotRegisteredError from RuntimeError to CoreError (W3-introduced classes that bypassed registry). Narrow 8 except Exception swallows in _actions.py, _result_summary.py, state_projection.py, live/__init__.py, ledger/_actions.py, review/_adapters.py, _profile_repository.py.

- [ ] `W05.P24.S444` - rebase WizardCatalogueNotRegisteredError from RuntimeError to CoreError (with registry entry + locale key); `src/aeat/core/profile_catalogue.py`.
- [ ] `W05.P24.S445` - rebase ProjectAnswersNotRegisteredError from RuntimeError to CoreError (with registry entry + locale key); `src/aeat/core/profile.py`.
- [ ] `W05.P24.S446` - introduce WizardCatalogueAlreadyRegisteredError(CoreError) and migrate raise RuntimeError at profile_catalogue.py:76; `src/aeat/core/profile_catalogue.py`.
- [ ] `W05.P24.S447` - narrow except Exception swallow at application/modelo/_actions.py:2743 to decimal.InvalidOperation; `src/aeat/application/modelo/_actions.py`.
- [ ] `W05.P24.S448` - fix missing raise after rollback at user_profile/_profile_repository.py:308 + narrow except Exception to (StorageError, OSError, ValidationError); `src/aeat/application/user_profile/_profile_repository.py`.
- [ ] `W05.P24.S449` - narrow except Exception swallows at modelo/_result_summary.py:73,81 to (LookupError, KeyError, AttributeError, AeatError) and add warning-level logging; `src/aeat/application/modelo/_result_summary.py`.
- [ ] `W05.P24.S450` - narrow except Exception swallows at state_projection.py:357,499 to typed sets; `src/aeat/application/state_projection.py`.
- [ ] `W05.P24.S451` - narrow 3 except Exception swallows at application/live/__init__.py:1390,1419,1435 to (AeatError, OSError, asyncio.TimeoutError); `src/aeat/application/live/__init__.py`.
- [ ] `W05.P24.S452` - narrow except Exception swallows at ledger/_actions.py:3439,3476 (parse + apply loops) to (ValidationError, ValueError, KeyError) and (AeatError, ValidationError); `src/aeat/application/ledger/_actions.py`.
- [ ] `W05.P24.S453` - split except Exception silent import guard at review/_adapters.py:317,323 into ImportError and (AeatError, AttributeError); `src/aeat/application/review/_adapters.py`.
- [ ] `W05.P24.S454` - add aggregate real-behavior test asserting W05.P24 new error classes registered + narrowed except clauses honestly propagate non-typed exceptions; `src/aeat/test_w05_p24_exceptions.py`.

### Phase `W05.P25` - A7 hardcoded: test regression + enum+constant survivors + new drifts

Fix test_stdio.py bare os.environ['COLUMNS'] regression. Enroll _PDF_EXTENSIONS clone, .xlsx cluster in _workbook_parity.py, AEAT_OUTPUT_LANGUAGE env-var constant. Migrate ledger_transaction bare defaults, GENERAL IVARegime fixture bypass, utf-8 fallback literal, manual_cli provenance literal.

- [ ] `W05.P25.S455` - fix regression: replace bare os.environ['COLUMNS'] with _COLUMNS_ENV_VAR at cli/test_stdio.py:242,253,268 (constant already imported); `src/aeat/entrypoints/cli/test_stdio.py`.
- [ ] `W05.P25.S456` - enroll _PDF_EXTENSIONS local frozenset at application/ledger/_evidence.py:41 to use PDF_EXTENSION from external_constants; `src/aeat/application/ledger/_evidence.py`.
- [ ] `W05.P25.S457` - introduce XLS_EXTENSION constant and migrate _workbook_parity.py:64,306,323,335,609 .xlsx cluster + .xls literal; `src/aeat/core/external_constants.py`.
- [ ] `W05.P25.S458` - introduce OUTPUT_LANGUAGE_ENV_VAR='AEAT_OUTPUT_LANGUAGE' constant in aeat.core.i18n and migrate _render.py:121 + test fixtures; `src/aeat/core/i18n/__init__.py`.
- [ ] `W05.P25.S459` - migrate ledger_transaction bare default at ledger/_actions.py:3143 and bindings.py:1629,1648 + schema.py:1787 to AggregationSourceKind.LEDGER_TRANSACTION; `src/aeat/application/ledger/_actions.py`.
- [ ] `W05.P25.S460` - migrate GENERAL bare string at user_profile/_testing.py:44 to IVARegime.GENERAL; `src/aeat/application/user_profile/_testing.py`.
- [ ] `W05.P25.S461` - remove redundant utf-8 fallback at providers/_csv.py:304 (CSV_ENCODING_FALLBACK_CHAIN already covers it); `src/aeat/adapters/inbound/financial/providers/_csv.py`.
- [ ] `W05.P25.S462` - introduce PROVENANCE_SOURCE_MANUAL_CLI constant and migrate user_profile/__init__.py:92,103, _values.py:134, _testing.py:45; `src/aeat/core/external_constants.py`.

### Phase `W05.P26` - A4 pydantic + small cleanup

Fix CLI wire-boundary type mismatch in _modelo_payloads.py:84 (dict[str, object] should align with domain dict[str, str] for inputs_snapshot). Defer RevisionValidationContext 17-field cascade to Wave 7 architectural review.

- [ ] `W05.P26.S463` - align CalculationRevisionPayload.inputs_snapshot type at cli/_modelo_payloads.py:84 from dict[str,object] to dict[str,str] (matching domain Mapping[str,str] contract); `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [ ] `W05.P26.S464` - add real-behavior test asserting CalculationRevisionPayload inputs_snapshot roundtrips dict[str,str] through CLI JSON channel; `src/aeat/entrypoints/cli/test_modelo_payloads.py`.
