"""Authored CommandSpec declarations for the ledger inventory surface."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from ._app_ledger_command_spec_policies import (
    _POLICY_1,
    _POLICY_4,
    _POLICY_5,
)
from .app_ledger_inventory_common_command_parameters import (
    INVENTORY_ACTIVIDAD_ID_ARGUMENT,
    INVENTORY_YEAR_OPTION,
)
from .command_spec import (
    CommandNodeKind,
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

LEDGER_INVENTORY_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_ledger_inventory_create",
        parent_key="app_ledger_inventory",
        token="create",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.inventory.create_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            INVENTORY_ACTIVIDAD_ID_ARGUMENT,
            INVENTORY_YEAR_OPTION,
            OptionSpec(
                name="valuation_method",
                declarations=("--valuation-method",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.app.ledger.inventory.valuation_method_help"),
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
                name="opening_stock",
                declarations=("--opening-stock",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value("0"),
                help_key=TranslationKey("cli.app.ledger.inventory.opening_stock_help"),
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
        ),
        policy=_POLICY_4,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._ledger_inventory_cli", "inventory_create")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli.ledger_business_payloads", "InventoryCreateResult"),
            identity="ledger.inventory.create",
        ),
    ),
    CommandSpec(
        key="app_ledger_inventory_list",
        parent_key="app_ledger_inventory",
        token="list",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.inventory.list_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(),
        policy=_POLICY_5,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._ledger_inventory_cli", "inventory_list")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli.ledger_business_payloads", "InventoryListResult"),
            identity="ledger.inventory.list",
        ),
    ),
    CommandSpec(
        key="app_ledger_inventory_closing_authority_record",
        parent_key="app_ledger_inventory",
        token="closing-authority-record",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.inventory.closing_authority_record_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            INVENTORY_ACTIVIDAD_ID_ARGUMENT,
            INVENTORY_YEAR_OPTION,
            OptionSpec(
                name="file",
                declarations=("--file",),
                value=ValueContract(DeferredTarget("pathlib", "Path")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.app.ledger.inventory.authority_file_help"),
                metavar=None,
                is_flag=False,
                flag_value=None,
                multiple=False,
                count=False,
                eager=False,
                constraint=ParameterConstraint(),
                show_default=True,
                hidden=False,
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
        ),
        policy=_POLICY_4,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._ledger_inventory_cli", "inventory_closing_authority_record")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli.ledger_business_payloads",
                "InventoryClosingAuthorityRecordResult",
            ),
            identity="ledger.inventory.closing-authority.record",
        ),
    ),
    CommandSpec(
        key="app_ledger_inventory_movement",
        parent_key="app_ledger_inventory",
        token="movement",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.app.ledger.inventory.movement_group_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=True, context_parameter=None),
        parameters=(),
        policy=_POLICY_1,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        key="app_ledger_inventory_valuation",
        parent_key="app_ledger_inventory",
        token="valuation",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.app.ledger.inventory.valuation_group_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=True, context_parameter=None),
        parameters=(),
        policy=_POLICY_1,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
)

__all__ = ["LEDGER_INVENTORY_COMMAND_SPECS"]
