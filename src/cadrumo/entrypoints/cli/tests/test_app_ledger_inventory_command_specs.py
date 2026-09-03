"""Exact parameter and shared-identity contracts for inventory commands."""

from __future__ import annotations

import pytest

from ....core.transport_locus import TransportLocus, TransportRole, TransportShape
from .._app_ledger_inventory_analysis_command_specs import LEDGER_INVENTORY_ANALYSIS_COMMAND_SPECS
from .._app_ledger_inventory_command_specs import LEDGER_INVENTORY_COMMAND_SPECS
from ..app_ledger_inventory_common_command_parameters import (
    INVENTORY_ACTIVIDAD_ID_ARGUMENT,
    INVENTORY_ACTIVIDAD_ID_OPTION,
    INVENTORY_YEAR_OPTION,
)
from ..command_spec import (
    ArgumentSpec,
    DeferredTarget,
    LiteralValue,
    OptionSpec,
    ParameterDefault,
    TranslationKey,
    ValueContract,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _argument(name: str, annotation: str, help_key: str) -> ArgumentSpec:
    """Build an independent complete argument contract for one expected field."""
    return ArgumentSpec(
        name=name,
        value=ValueContract(DeferredTarget(*annotation.split(":", maxsplit=1))),
        default=ParameterDefault.required(),
        help_key=TranslationKey(help_key),
    )


def _option(
    name: str,
    annotation: str,
    default: LiteralValue,
    help_key: str | None,
    *,
    required: bool = False,
    declarations: tuple[str, ...] | None = None,
    is_flag: bool = False,
    transport: tuple[TransportLocus, TransportShape, TransportRole] | None = None,
) -> OptionSpec:
    """Build an independent complete option contract for one expected field."""
    locus, shape, role = transport or (TransportLocus.NONE, TransportShape.NOT_APPLICABLE, TransportRole.NOT_APPLICABLE)
    return OptionSpec(
        name=name,
        declarations=declarations or (f"--{name.replace('_', '-')}",),
        value=ValueContract(DeferredTarget(*annotation.split(":", maxsplit=1))),
        default=ParameterDefault.required() if required else ParameterDefault.value(default),
        help_key=TranslationKey(help_key) if help_key is not None else None,
        is_flag=is_flag,
        flag_value=True if is_flag else None,
        transport_locus=locus,
        transport_shape=shape,
        transport_role=role,
    )


def test_inventory_parameter_contracts_are_complete_and_ordered() -> None:
    """Every inventory command preserves its exact runtime parameter contract."""
    specs = {spec.key: spec for spec in (*LEDGER_INVENTORY_COMMAND_SPECS, *LEDGER_INVENTORY_ANALYSIS_COMMAND_SPECS)}

    assert specs["app_ledger_inventory_create"].parameters == (
        _argument("actividad_id", "builtins:str", "cli.app.ledger.inventory.actividad_id_help"),
        _option("year", "builtins:int", None, "cli.app.ledger.inventory.year_help", required=True),
        _option(
            "valuation_method", "builtins:str", None, "cli.app.ledger.inventory.valuation_method_help", required=True
        ),
        _option("opening_stock", "builtins:str", "0", "cli.app.ledger.inventory.opening_stock_help"),
    )
    assert specs["app_ledger_inventory_closing_authority_record"].parameters == (
        _argument("actividad_id", "builtins:str", "cli.app.ledger.inventory.actividad_id_help"),
        _option("year", "builtins:int", None, "cli.app.ledger.inventory.year_help", required=True),
        _option(
            "file",
            "pathlib:Path",
            None,
            "cli.app.ledger.inventory.authority_file_help",
            required=True,
            transport=(TransportLocus.LOCAL_IN, TransportShape.FILE, TransportRole.PRIMARY),
        ),
    )
    assert specs["app_ledger_inventory_movement_add"].parameters == (
        _option("actividad_id", "builtins:str", None, "cli.app.ledger.inventory.actividad_id_help", required=True),
        _option("year", "builtins:int", None, "cli.app.ledger.inventory.year_help", required=True),
        _option("movement_id", "builtins:str", None, "cli.app.ledger.inventory.movement_id_help", required=True),
        _option(
            "movement_date",
            "builtins:str",
            None,
            "cli.app.ledger.inventory.movement_date_help",
            required=True,
            declarations=("--date",),
        ),
        _option(
            "kind",
            "cadrumo.domain.contribuyente.inventory.records:MovementKind",
            None,
            "cli.app.ledger.inventory.movement_kind_help",
            required=True,
        ),
        _option("quantity", "builtins:str", None, "cli.app.ledger.inventory.quantity_help", required=True),
        _option("unit_cost", "builtins:str", None, "cli.app.ledger.inventory.unit_cost_help"),
        _option("taxable_base", "builtins:str", None, "cli.app.ledger.inventory.taxable_base_help"),
        _option(
            "acquisition_cost_stdin",
            "builtins:bool",
            False,
            "cli.app.ledger.inventory.acquisition_cost_stdin_help",
            is_flag=True,
        ),
    )
    assert specs["app_ledger_inventory_valuation_preview"].parameters == (
        _option("actividad_id", "builtins:str", None, "cli.app.ledger.inventory.actividad_id_help", required=True),
        _option("year", "builtins:int", None, "cli.app.ledger.inventory.year_help", required=True),
    )


def test_shared_inventory_parameters_have_one_immutable_authority() -> None:
    """Only exactly equal records share identities across inventory command shapes."""
    specs = {spec.key: spec for spec in (*LEDGER_INVENTORY_COMMAND_SPECS, *LEDGER_INVENTORY_ANALYSIS_COMMAND_SPECS)}
    create = specs["app_ledger_inventory_create"]
    authority = specs["app_ledger_inventory_closing_authority_record"]
    movement = specs["app_ledger_inventory_movement_add"]
    preview = specs["app_ledger_inventory_valuation_preview"]

    assert create.parameters[0] is authority.parameters[0] is INVENTORY_ACTIVIDAD_ID_ARGUMENT
    assert movement.parameters[0] is preview.parameters[0] is INVENTORY_ACTIVIDAD_ID_OPTION
    assert create.parameters[1] is authority.parameters[1] is movement.parameters[1] is preview.parameters[1]
    assert create.parameters[1] is INVENTORY_YEAR_OPTION
    assert INVENTORY_ACTIVIDAD_ID_ARGUMENT != INVENTORY_ACTIVIDAD_ID_OPTION
    assert type(INVENTORY_ACTIVIDAD_ID_ARGUMENT).__dataclass_params__.frozen
    assert type(INVENTORY_ACTIVIDAD_ID_OPTION).__dataclass_params__.frozen
    assert type(INVENTORY_YEAR_OPTION).__dataclass_params__.frozen
