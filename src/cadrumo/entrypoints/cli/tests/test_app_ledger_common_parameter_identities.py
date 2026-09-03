"""Exact field, order, and identity contracts for shared ledger CLI parameters."""

from __future__ import annotations

from typing import Final

import pytest

from .._app_ledger_command_spec_support import (
    _ARCHIVE_REASON_OPTION,
    _LEDGER_ACTOR_OPTION,
    _LEDGER_ADD_CATEGORY_ID_OPTION,
    _LEDGER_USAGE_RATIO_ID_OPTION,
    _OPTIONAL_PERIOD_OPTION,
    _OPTIONAL_YEAR_OPTION,
)
from .._app_ledger_foundation_command_specs import LEDGER_FOUNDATION_COMMAND_SPECS
from .._app_ledger_inventory_analysis_command_specs import LEDGER_INVENTORY_ANALYSIS_COMMAND_SPECS
from .._app_ledger_lifecycle_command_specs import LEDGER_LIFECYCLE_COMMAND_SPECS
from .._app_ledger_rule_command_specs import LEDGER_RULE_COMMAND_SPECS
from ..command_spec import (
    DeferredTarget,
    LiteralValue,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    TranslationKey,
    ValueContract,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OPTION_FIELDS: Final[tuple[str, ...]] = tuple(OptionSpec.__dataclass_fields__)


def _option(
    name: str,
    declaration: str,
    help_key: str,
    *,
    default: LiteralValue = None,
    annotation: str = "builtins:str",
) -> OptionSpec:
    """Build the complete independent contract for one scalar option."""
    module, qualname = annotation.split(":", maxsplit=1)
    return OptionSpec(
        name=name,
        declarations=(declaration,),
        value=ValueContract(DeferredTarget(module, qualname)),
        default=ParameterDefault.value(default),
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


def _fields(option: OptionSpec) -> tuple[object, ...]:
    """Project every OptionSpec field so a future field cannot evade this contract."""
    return tuple(getattr(option, field) for field in _OPTION_FIELDS)


def test_shared_ledger_parameter_fields_are_complete_and_immutable() -> None:
    """Every shared option retains its full literal CLI contract."""
    expected = {
        _LEDGER_ADD_CATEGORY_ID_OPTION: _option("category_id", "--category-id", "cli.ledger.add.category_help"),
        _LEDGER_USAGE_RATIO_ID_OPTION: _option("usage_ratio_id", "--usage-ratio-id", "cli.ledger.add.usage_ratio_help"),
        _LEDGER_ACTOR_OPTION: _option("actor", "--actor", "cli.ledger.add.actor_help"),
        _ARCHIVE_REASON_OPTION: _option("reason", "--reason", "cli.ledger.archive.reason_help", default=""),
        _OPTIONAL_PERIOD_OPTION: _option("period", "--period", "cli.ledger.export.period_help"),
        _OPTIONAL_YEAR_OPTION: _option("year", "--year", "cli.ledger.check.year_help", annotation="builtins:int"),
    }

    assert tuple(_fields(option) for option in expected) == tuple(_fields(contract) for contract in expected.values())
    assert all(type(option).__dataclass_params__.frozen for option in expected)


def test_common_ledger_parameters_keep_their_full_command_order_and_identity() -> None:
    """Only equal immutable records are shared at their exact parameter locations."""
    specs = {spec.key: spec for spec in (*LEDGER_FOUNDATION_COMMAND_SPECS, *LEDGER_LIFECYCLE_COMMAND_SPECS)}

    assert {
        key: tuple(parameter.name for parameter in specs[key].parameters)
        for key in (
            "app_ledger_add",
            "app_ledger_allocate",
            "app_ledger_archive",
            "app_ledger_attach",
            "app_ledger_check",
            "app_ledger_restore",
            "app_ledger_stash",
            "app_ledger_status",
        )
    } == {
        "app_ledger_add": (
            "booked_date",
            "amount",
            "direction",
            "description",
            "value_date",
            "currency",
            "counterparty",
            "business_classification",
            "business_pct",
            "category_id",
            "taxable_base",
            "iva_rate",
            "iva_amount",
            "iva_category",
            "deduction_fact_kind",
            "counterparty_country",
            "counterparty_identification_state",
            "recargo_amount",
            "irpf_category",
            "usage_ratio_id",
            "prorrata_reference",
            "art_104_tres_exclusion",
            "input_classification",
            "prorrata_sector",
            "purchase_invoice_evidence_id",
            "attachment_ids",
            "notes",
            "actor",
            "idempotency_key",
            "source_jurisdiction",
        ),
        "app_ledger_allocate": (
            "transaction_id",
            "business_pct",
            "category_id",
            "usage_ratio_id",
            "prorrata_reference",
            "actor",
        ),
        "app_ledger_archive": ("transaction_id", "reason", "yes", "actor"),
        "app_ledger_attach": ("transaction_id", "purchase_invoice_evidence_id", "attachment_ids", "actor"),
        "app_ledger_check": ("bucket_id_option", "period", "year"),
        "app_ledger_restore": ("transaction_id", "reason", "yes", "actor"),
        "app_ledger_stash": ("transaction_id", "reason", "yes", "actor"),
        "app_ledger_status": ("period", "year"),
    }

    add, allocate, archive, attach, check = (
        specs[key]
        for key in (
            "app_ledger_add",
            "app_ledger_allocate",
            "app_ledger_archive",
            "app_ledger_attach",
            "app_ledger_check",
        )
    )
    restore, stash, status = (specs[key] for key in ("app_ledger_restore", "app_ledger_stash", "app_ledger_status"))
    assert add.parameters[9] is allocate.parameters[2] is _LEDGER_ADD_CATEGORY_ID_OPTION
    assert add.parameters[19] is allocate.parameters[3] is _LEDGER_USAGE_RATIO_ID_OPTION
    assert all(
        parameter is _LEDGER_ACTOR_OPTION
        for parameter in (
            add.parameters[27],
            allocate.parameters[5],
            archive.parameters[3],
            attach.parameters[3],
            restore.parameters[3],
            stash.parameters[3],
        )
    )
    assert archive.parameters[1] is restore.parameters[1] is stash.parameters[1] is _ARCHIVE_REASON_OPTION
    assert status.parameters[0] is _OPTIONAL_PERIOD_OPTION
    assert check.parameters[2] is status.parameters[1] is _OPTIONAL_YEAR_OPTION


def test_domain_specific_scalar_options_remain_distinct() -> None:
    """Similar names with different help contracts never share an authority."""
    foundation = {spec.key: spec for spec in LEDGER_FOUNDATION_COMMAND_SPECS}
    rule = {spec.key: spec for spec in LEDGER_RULE_COMMAND_SPECS}
    inventory = {spec.key: spec for spec in LEDGER_INVENTORY_ANALYSIS_COMMAND_SPECS}

    assert rule["app_ledger_rule_add"].parameters[2] is not _LEDGER_ADD_CATEGORY_ID_OPTION
    assert rule["app_ledger_rule_add"].parameters[-1] is not _LEDGER_ACTOR_OPTION
    assert (
        foundation["app_ledger_add"].parameters[10] is not inventory["app_ledger_inventory_movement_add"].parameters[7]
    )
    assert rule["app_ledger_rule_add"].parameters[2].help_key != _LEDGER_ADD_CATEGORY_ID_OPTION.help_key
    assert rule["app_ledger_rule_add"].parameters[-1].help_key != _LEDGER_ACTOR_OPTION.help_key
    assert (
        foundation["app_ledger_add"].parameters[10].help_key
        != inventory["app_ledger_inventory_movement_add"].parameters[7].help_key
    )
