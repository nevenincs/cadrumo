"""Authored command declarations for IRPF activity assets."""

from __future__ import annotations

from cadrumo_client.commands.parameters import ArgumentSpec, OptionSpec
from cadrumo_client.commands.shared_contracts import (
    DeferredTarget,
    LazyBinding,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from cadrumo_client.commands.spec import CommandSpec, ExecutionPolicySpec, InvocationSpec
from cadrumo_client.contracts.command_ports import CommandNodeKind

from ._app_ledger_command_spec_policies import _POLICY_1, _POLICY_4, _POLICY_5, _POLICY_6


def _argument(name: str) -> ArgumentSpec:
    return ArgumentSpec(
        name=name,
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.required(),
        help_key=None,
        metavar=None,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    )


def _option(name: str, declaration: str, *, integer: bool = False, optional: bool = False) -> OptionSpec:
    return OptionSpec(
        name=name,
        declarations=(declaration,),
        value=ValueContract(DeferredTarget("builtins", "int" if integer else "str")),
        default=ParameterDefault.value(None) if optional else ParameterDefault.required(),
        help_key=None,
        metavar=None,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    )


def _leaf(
    key: str,
    token: str,
    handler: str,
    parameters: tuple[ArgumentSpec | OptionSpec, ...],
    *,
    help_key: TranslationKey,
    schema_module: str,
    schema_name: str,
    policy: ExecutionPolicySpec = _POLICY_5,
) -> CommandSpec:
    return CommandSpec(
        key,
        "app_ledger_actividad_asset",
        token,
        kind=CommandNodeKind.LEAF,
        help_key=help_key,
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=parameters,
        policy=policy,
        handler=LazyBinding.available(DeferredTarget(".actividad_asset_commands", handler, __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(schema_module, schema_name, __package__ if schema_module.startswith(".") else None),
            identity=f"ledger.actividad_asset.{token.replace('-', '_')}",
        ),
    )


_DESCRIPTOR_OPTIONS = (
    _option("name", "--name"),
    _option("serial_number", "--serial-number", optional=True),
    _option("description", "--description", optional=True),
    _option("document_kind", "--document-kind", optional=True),
    _option("document_number", "--document-number", optional=True),
    _option("supplier_name", "--supplier-name", optional=True),
    _option("supplier_tax_id", "--supplier-tax-id", optional=True),
)

_DISPOSAL_AMOUNT_OPTIONS = (
    _option("market_value", "--market-value", optional=True),
    _option("prior_free_depreciation_regime", "--prior-free-depreciation-regime", optional=True),
    _option("later_affectation_on", "--later-affectation-on", optional=True),
)

#: Closed read-command vocabulary; every help key remains visible to locale discovery.
_READ_HELP_LOCALE_KEYS = {
    "list": TranslationKey("cli.app.ledger.actividad_asset.list_help"),
    "plan": TranslationKey("cli.app.ledger.actividad_asset.plan_help"),
    "disposal-calculate": TranslationKey("cli.app.ledger.actividad_asset.disposal_calculate_help"),
    "timeline": TranslationKey("cli.app.ledger.actividad_asset.timeline_help"),
    "form-options": TranslationKey("cli.app.ledger.actividad_asset.form_options_help"),
    "acquisition-candidates": TranslationKey("cli.app.ledger.actividad_asset.acquisition_candidates_help"),
}


def _read_leaf(
    token: str,
    parameters: tuple[ArgumentSpec | OptionSpec, ...] = (),
) -> CommandSpec:
    name = token.replace("-", "_")
    return _leaf(
        f"app_ledger_actividad_asset_{name}",
        token,
        f"actividad_asset_{name}",
        parameters,
        help_key=_READ_HELP_LOCALE_KEYS[token],
        schema_module="._actividad_asset_payloads",
        schema_name="ActivityAssetReadPayload",
        policy=_POLICY_6,
    )


LEDGER_ACTIVIDAD_ASSET_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_ledger_actividad_asset",
        "app_ledger",
        "actividad-asset",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.app.ledger.actividad_asset.group_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=_POLICY_1,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    _leaf(
        "app_ledger_actividad_asset_create",
        "create",
        "actividad_asset_create",
        (_argument("revision_json"), *_DESCRIPTOR_OPTIONS),
        help_key=TranslationKey("cli.app.ledger.actividad_asset.create_help"),
        schema_module="._actividad_asset_payloads",
        schema_name="ActivityAssetHistoryPayload",
        policy=_POLICY_4,
    ),
    _leaf(
        "app_ledger_actividad_asset_inspect",
        "inspect",
        "actividad_asset_inspect",
        (_argument("asset_id"),),
        help_key=TranslationKey("cli.app.ledger.actividad_asset.inspect_help"),
        schema_module="._actividad_asset_payloads",
        schema_name="ActivityAssetInspectionPayload",
    ),
    _leaf(
        "app_ledger_actividad_asset_correct",
        "correct",
        "actividad_asset_correct",
        (_argument("revision_json"), _option("superseding_claims_json", "--superseding-claims-json", optional=True)),
        help_key=TranslationKey("cli.app.ledger.actividad_asset.correct_help"),
        schema_module="._actividad_asset_payloads",
        schema_name="ActivityAssetHistoryPayload",
        policy=_POLICY_4,
    ),
    _leaf(
        "app_ledger_actividad_asset_forecast",
        "forecast",
        "actividad_asset_forecast",
        (
            _argument("asset_id"),
            _option("covered_from", "--covered-from"),
            _option("covered_until", "--covered-until"),
            _option("free_depreciation_amount", "--free-depreciation-amount", optional=True),
            _option("supersedes_claim_id", "--supersedes-claim-id", optional=True),
        ),
        help_key=TranslationKey("cli.app.ledger.actividad_asset.forecast_help"),
        schema_module="._actividad_asset_payloads",
        schema_name="ActivityAssetForecastPayload",
        policy=_POLICY_6,
    ),
    _leaf(
        "app_ledger_actividad_asset_claim",
        "claim",
        "actividad_asset_record_claim",
        (
            _argument("forecast_json"),
            _option("supersedes_claim_id", "--supersedes-claim-id", optional=True),
        ),
        help_key=TranslationKey("cli.app.ledger.actividad_asset.claim_help"),
        schema_module="._actividad_asset_payloads",
        schema_name="ActivityAssetClaimPayload",
        policy=_POLICY_4,
    ),
    _leaf(
        "app_ledger_actividad_asset_filing_handoff",
        "filing-handoff",
        "actividad_asset_filing_handoff",
        (_option("tax_year", "--tax-year", integer=True), _option("m130_period", "--m130-period")),
        help_key=TranslationKey("cli.app.ledger.actividad_asset.filing_handoff_help"),
        schema_module="._actividad_asset_payloads",
        schema_name="ActivityAssetFilingHandoffPayload",
        policy=_POLICY_6,
    ),
    _leaf(
        "app_ledger_actividad_asset_describe",
        "describe",
        "actividad_asset_describe",
        (_argument("asset_id"), *_DESCRIPTOR_OPTIONS),
        help_key=TranslationKey("cli.app.ledger.actividad_asset.describe_help"),
        schema_module="._actividad_asset_payloads",
        schema_name="ActivityAssetHistoryPayload",
        policy=_POLICY_4,
    ),
    _leaf(
        "app_ledger_actividad_asset_dispose",
        "dispose",
        "actividad_asset_dispose",
        (
            _argument("asset_id"),
            _option("disposal_date", "--disposal-date"),
            _option("reason", "--reason"),
            _option("proceeds", "--proceeds"),
            _option("transmission_costs", "--transmission-costs"),
            *_DISPOSAL_AMOUNT_OPTIONS,
        ),
        help_key=TranslationKey("cli.app.ledger.actividad_asset.dispose_help"),
        schema_module="._actividad_asset_payloads",
        schema_name="ActivityAssetHistoryPayload",
        policy=_POLICY_4,
    ),
    _read_leaf(
        "disposal-calculate",
        (
            _argument("asset_id"),
            _option("disposal_date", "--disposal-date", optional=True),
            _option("reason", "--reason", optional=True),
            _option("proceeds", "--proceeds", optional=True),
            _option("transmission_costs", "--transmission-costs", optional=True),
            *_DISPOSAL_AMOUNT_OPTIONS,
        ),
    ),
    _read_leaf("list"),
    _read_leaf("plan", (_argument("asset_id"),)),
    _read_leaf("timeline", (_argument("asset_id"),)),
    _read_leaf(
        "form-options", (_option("asset_kind", "--asset-kind"), _option("tax_year", "--tax-year", integer=True))
    ),
    _read_leaf("acquisition-candidates"),
)

__all__ = ["LEDGER_ACTIVIDAD_ASSET_COMMAND_SPECS"]
