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
from cadrumo_client.commands.spec import CommandSpec, InvocationSpec
from cadrumo_client.contracts.command_ports import CommandNodeKind

from ._app_ledger_command_spec_policies import (
    _POLICY_4,
    _POLICY_5,
    _POLICY_6,
)
from .app_ledger_inventory_common_command_parameters import (
    INVENTORY_ACTIVIDAD_ID_ARGUMENT,
    INVENTORY_ACTIVIDAD_ID_OPTION,
    INVENTORY_YEAR_OPTION,
)

_MOVEMENT_FACT_OPTIONS: tuple[OptionSpec, ...] = (
    OptionSpec(
        name="movement_id",
        declarations=("--movement-id",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.required(),
        help_key=TranslationKey("cli.app.ledger.inventory.movement_id_help"),
        metavar=None,
        is_flag=False,
        flag_value=None,
        multiple=False,
        count=False,
        eager=False,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    ),
    OptionSpec(
        name="movement_date",
        declarations=("--date",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.required(),
        help_key=TranslationKey("cli.app.ledger.inventory.movement_date_help"),
        metavar=None,
        is_flag=False,
        flag_value=None,
        multiple=False,
        count=False,
        eager=False,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    ),
    OptionSpec(
        name="kind",
        declarations=("--kind",),
        value=ValueContract(DeferredTarget("...domain.contribuyente.inventory.records", "MovementKind", __package__)),
        default=ParameterDefault.required(),
        help_key=TranslationKey("cli.app.ledger.inventory.movement_kind_help"),
        metavar=None,
        is_flag=False,
        flag_value=None,
        multiple=False,
        count=False,
        eager=False,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    ),
    OptionSpec(
        name="quantity",
        declarations=("--quantity",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.required(),
        help_key=TranslationKey("cli.app.ledger.inventory.quantity_help"),
        metavar=None,
        is_flag=False,
        flag_value=None,
        multiple=False,
        count=False,
        eager=False,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    ),
    OptionSpec(
        name="unit_cost",
        declarations=("--unit-cost",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.ledger.inventory.unit_cost_help"),
        metavar=None,
        is_flag=False,
        flag_value=None,
        multiple=False,
        count=False,
        eager=False,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    ),
    OptionSpec(
        name="taxable_base",
        declarations=("--taxable-base",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.ledger.inventory.taxable_base_help"),
        metavar=None,
        is_flag=False,
        flag_value=None,
        multiple=False,
        count=False,
        eager=False,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    ),
    OptionSpec(
        name="acquisition_cost_stdin",
        declarations=("--acquisition-cost-stdin",),
        value=ValueContract(DeferredTarget("builtins", "bool")),
        default=ParameterDefault.value(False),
        help_key=TranslationKey("cli.app.ledger.inventory.acquisition_cost_stdin_help"),
        metavar=None,
        is_flag=True,
        flag_value=True,
        multiple=False,
        count=False,
        eager=False,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    ),
)


def _required_text_option(name: str, flag: str, help_key: str) -> OptionSpec:
    return OptionSpec(
        name=name,
        declarations=(flag,),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.required(),
        help_key=TranslationKey(help_key),
        metavar=None,
        is_flag=False,
        flag_value=None,
        multiple=False,
        count=False,
        eager=False,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    )


def _optional_option(name: str, flag: str, help_key: str, target: DeferredTarget) -> OptionSpec:
    return OptionSpec(
        name=name,
        declarations=(flag,),
        value=ValueContract(target),
        default=ParameterDefault.value(None),
        help_key=TranslationKey(help_key),
        metavar=None,
        is_flag=False,
        flag_value=None,
        multiple=False,
        count=False,
        eager=False,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    )


def _required_enum_option(name: str, flag: str, help_key: str, enum_name: str) -> OptionSpec:
    return OptionSpec(
        name=name,
        declarations=(flag,),
        value=ValueContract(DeferredTarget("...domain.contribuyente.inventory.records", enum_name, __package__)),
        default=ParameterDefault.required(),
        help_key=TranslationKey(help_key),
        metavar=None,
        is_flag=False,
        flag_value=None,
        multiple=False,
        count=False,
        eager=False,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    )


_CORRECTION_ID_OPTION = _required_text_option(
    "correction_id", "--correction-id", "cli.app.ledger.inventory.correction_id_help"
)
_TARGET_MOVEMENT_OPTION = _required_text_option(
    "target_movement_id", "--target-movement-id", "cli.app.ledger.inventory.target_movement_id_help"
)
_CORRECTION_REASON_OPTION = _required_enum_option(
    "reason", "--reason", "cli.app.ledger.inventory.correction_reason_help", "InventoryCorrectionReason"
)
_RETIREMENT_REASON_OPTION = _required_enum_option(
    "reason", "--reason", "cli.app.ledger.inventory.retirement_reason_help", "InventoryRetirementReason"
)


def _ledger_change_spec(
    key: str,
    parent: str,
    name: str,
    *,
    parameters: tuple[ArgumentSpec | OptionSpec, ...],
    handler: str,
    identity: str,
) -> CommandSpec:
    return CommandSpec(
        key,
        parent,
        name,
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey(f"cli.app.ledger.inventory.{key.removeprefix('app_ledger_inventory_')}_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=parameters,
        policy=_POLICY_4,
        handler=LazyBinding.available(DeferredTarget(".ledger_inventory_commands", handler, __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_business_payloads", "InventoryLedgerChangeResult", __package__),
            identity=identity,
        ),
    )


LEDGER_INVENTORY_ANALYSIS_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_ledger_inventory_inspect",
        "app_ledger_inventory",
        "inspect",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.inventory.inspect_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(INVENTORY_ACTIVIDAD_ID_ARGUMENT, INVENTORY_YEAR_OPTION),
        policy=_POLICY_5,
        handler=LazyBinding.available(DeferredTarget(".ledger_inventory_commands", "inventory_inspect", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_business_payloads", "InventoryInspectResult", __package__),
            identity="ledger.inventory.inspect",
        ),
    ),
    _ledger_change_spec(
        "app_ledger_inventory_describe",
        "app_ledger_inventory",
        "describe",
        parameters=(
            INVENTORY_ACTIVIDAD_ID_ARGUMENT,
            INVENTORY_YEAR_OPTION,
            _CORRECTION_ID_OPTION,
            _required_text_option("label", "--label", "cli.app.ledger.inventory.label_help"),
            _optional_option(
                "description",
                "--description",
                "cli.app.ledger.inventory.description_help",
                DeferredTarget("builtins", "str"),
            ),
        ),
        handler="inventory_describe",
        identity="ledger.inventory.describe",
    ),
    _ledger_change_spec(
        "app_ledger_inventory_correct",
        "app_ledger_inventory",
        "correct",
        parameters=(
            INVENTORY_ACTIVIDAD_ID_ARGUMENT,
            INVENTORY_YEAR_OPTION,
            _CORRECTION_ID_OPTION,
            _CORRECTION_REASON_OPTION,
            _optional_option(
                "opening_stock",
                "--opening-stock",
                "cli.app.ledger.inventory.corrected_opening_stock_help",
                DeferredTarget("builtins", "str"),
            ),
            _optional_option(
                "valuation_method",
                "--valuation-method",
                "cli.app.ledger.inventory.corrected_valuation_method_help",
                DeferredTarget("...domain.contribuyente.inventory.records", "ValuationMethod", __package__),
            ),
        ),
        handler="inventory_correct",
        identity="ledger.inventory.correct",
    ),
    _ledger_change_spec(
        "app_ledger_inventory_retire",
        "app_ledger_inventory",
        "retire",
        parameters=(
            INVENTORY_ACTIVIDAD_ID_ARGUMENT,
            INVENTORY_YEAR_OPTION,
            _CORRECTION_ID_OPTION,
            _RETIREMENT_REASON_OPTION,
        ),
        handler="inventory_retire",
        identity="ledger.inventory.retire",
    ),
    _ledger_change_spec(
        "app_ledger_inventory_restore",
        "app_ledger_inventory",
        "restore",
        parameters=(INVENTORY_ACTIVIDAD_ID_ARGUMENT, INVENTORY_YEAR_OPTION, _CORRECTION_ID_OPTION),
        handler="inventory_restore",
        identity="ledger.inventory.restore",
    ),
    _ledger_change_spec(
        "app_ledger_inventory_movement_correct",
        "app_ledger_inventory_movement",
        "correct",
        parameters=(
            INVENTORY_ACTIVIDAD_ID_OPTION,
            INVENTORY_YEAR_OPTION,
            _CORRECTION_ID_OPTION,
            _TARGET_MOVEMENT_OPTION,
            _CORRECTION_REASON_OPTION,
            *_MOVEMENT_FACT_OPTIONS,
        ),
        handler="inventory_movement_correct",
        identity="ledger.inventory.movement.correct",
    ),
    _ledger_change_spec(
        "app_ledger_inventory_movement_reverse",
        "app_ledger_inventory_movement",
        "reverse",
        parameters=(
            INVENTORY_ACTIVIDAD_ID_OPTION,
            INVENTORY_YEAR_OPTION,
            _CORRECTION_ID_OPTION,
            _TARGET_MOVEMENT_OPTION,
            _CORRECTION_REASON_OPTION,
        ),
        handler="inventory_movement_reverse",
        identity="ledger.inventory.movement.reverse",
    ),
    CommandSpec(
        "app_ledger_inventory_movement_add",
        "app_ledger_inventory_movement",
        "add",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.inventory.movement_add_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            INVENTORY_ACTIVIDAD_ID_OPTION,
            INVENTORY_YEAR_OPTION,
            *_MOVEMENT_FACT_OPTIONS,
        ),
        policy=_POLICY_4,
        handler=LazyBinding.available(
            DeferredTarget(".ledger_inventory_commands", "inventory_movement_add", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_business_payloads", "InventoryMovementAddResult", __package__),
            identity="ledger.inventory.movement.add",
        ),
    ),
    CommandSpec(
        "app_ledger_inventory_valuation_preview",
        "app_ledger_inventory_valuation",
        "preview",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.inventory.valuation_preview_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            INVENTORY_ACTIVIDAD_ID_OPTION,
            INVENTORY_YEAR_OPTION,
        ),
        policy=_POLICY_6,
        handler=LazyBinding.available(
            DeferredTarget(".ledger_inventory_commands", "inventory_valuation_preview", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_business_payloads", "InventoryValuationPreviewPayload", __package__),
            identity="ledger.inventory.valuation.preview",
        ),
    ),
)

__all__ = ["LEDGER_INVENTORY_ANALYSIS_COMMAND_SPECS"]
"""Authored CommandSpec declarations for the ledger inventory analysis surface."""
"""Authored CommandSpec declarations for the ledger inventory analysis surface."""
