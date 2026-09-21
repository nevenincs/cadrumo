"""Authored command declarations for IRPF activity assets."""

from __future__ import annotations

from cadrumo.application.operator_surface.command_ports import CommandNodeKind

from ._app_ledger_command_spec_policies import _POLICY_1, _POLICY_4, _POLICY_5, _POLICY_6
from .command_spec import (
    ArgumentSpec,
    CommandSpec,
    DeferredTarget,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)


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
    schema_module: str,
    schema_name: str,
    policy=_POLICY_5,
) -> CommandSpec:
    return CommandSpec(
        key,
        "app_ledger_actividad_asset",
        token,
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey(f"cli.app.ledger.actividad_asset.{token.replace('-', '_')}_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=parameters,
        policy=policy,
        handler=LazyBinding.available(DeferredTarget("._actividad_asset_cli", handler, __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(schema_module, schema_name, __package__ if schema_module.startswith(".") else None),
            identity=f"ledger.actividad_asset.{token.replace('-', '_')}",
        ),
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
        (_argument("revision_json"),),
        schema_module="cadrumo.application.actividad_asset.history",
        schema_name="ActivityAssetHistory",
        policy=_POLICY_4,
    ),
    _leaf(
        "app_ledger_actividad_asset_inspect",
        "inspect",
        "actividad_asset_inspect",
        (_argument("asset_id"),),
        schema_module="._actividad_asset_cli",
        schema_name="ActivityAssetInspectionPayload",
    ),
    _leaf(
        "app_ledger_actividad_asset_correct",
        "correct",
        "actividad_asset_correct",
        (_argument("revision_json"),),
        schema_module="cadrumo.application.actividad_asset.history",
        schema_name="ActivityAssetHistory",
        policy=_POLICY_4,
    ),
    _leaf(
        "app_ledger_actividad_asset_forecast",
        "forecast",
        "actividad_asset_forecast",
        (
            _argument("asset_id"),
            _option("selection_json", "--selection-json"),
            _option("covered_from", "--covered-from"),
            _option("covered_until", "--covered-until"),
        ),
        schema_module="cadrumo.domain.renta.actividad_asset.schedule",
        schema_name="ScheduledAmortizationCharge",
        policy=_POLICY_6,
    ),
    _leaf(
        "app_ledger_actividad_asset_claim",
        "claim",
        "actividad_asset_record_claim",
        (
            _argument("forecast_json"),
            _option("creating_operation", "--creating-operation"),
            _option("supersedes_claim_id", "--supersedes-claim-id", optional=True),
        ),
        schema_module="cadrumo.application.actividad_asset.history",
        schema_name="ActivityAssetHistoryClaimResult",
        policy=_POLICY_4,
    ),
    _leaf(
        "app_ledger_actividad_asset_filing_handoff",
        "filing-handoff",
        "actividad_asset_filing_handoff",
        (_option("tax_year", "--tax-year", integer=True), _option("m130_period", "--m130-period")),
        schema_module="cadrumo.application.actividad_asset.operations",
        schema_name="ActivityAssetFilingHandoff",
        policy=_POLICY_6,
    ),
)

__all__ = ["LEDGER_ACTIVIDAD_ASSET_COMMAND_SPECS"]
