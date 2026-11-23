"""Independent contracts for ledger invoice lifecycle CommandSpecs."""

from __future__ import annotations

import pytest

from cadrumo_client.commands.parameters import ArgumentSpec, OptionSpec

from ....core.filing_year import FOUR_DIGIT_YEAR_FIRST, FOUR_DIGIT_YEAR_LAST
from ..app_ledger_invoice_common_command_parameters import (
    BUSINESS_PREMISES_LEASE_OPTIONS,
    DECLARED_FX_RATE_OPTION,
    INVOICE_INTAKE_WIZARD_CORE_OPTIONS,
    INVOICE_INTAKE_WIZARD_TRAILING_OPTIONS,
    INVOICE_LIFECYCLE_METADATA_OPTIONS,
    INVOICE_RECTIFICATION_OPTIONS,
    INVOICE_RECTIFICATION_PERIOD_OPTIONS,
    OPTIONAL_IVA_CATEGORY_OPTION,
)
from ..app_ledger_invoice_intake_command_specs import LEDGER_INVOICE_INTAKE_COMMAND_SPECS
from ..app_ledger_invoice_lifecycle_command_specs import (
    LEDGER_INVOICE_LIFECYCLE_COMMAND_SPECS,
    REQUIRED_INVOICE_ID_ARGUMENT,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DEFAULT_CONSTRAINT = (None, None, False, True, False, True, True, False, True, False, False)
#: A filing-year option is bounded by the four-digit year range, which is the
#: only field of the constraint an invoice option departs from.
_YEAR_CONSTRAINT = (
    FOUR_DIGIT_YEAR_FIRST,
    FOUR_DIGIT_YEAR_LAST,
    False,
    True,
    False,
    True,
    True,
    False,
    True,
    False,
    False,
)
_NO_TRANSPORT = ("none", "not_applicable", "not_applicable")
_NO_VALUE_HOOKS = (None, None, None, ())


def _parameter_contract(parameter: ArgumentSpec | OptionSpec) -> tuple[object, ...]:
    """Project every parameter field that reaches the command runtime."""
    value = parameter.value
    common = (
        parameter.kind.value,
        parameter.name,
        (
            value.annotation.identity,
            *(
                target.identity if target is not None else None
                for target in (value.parser, value.completion, value.callback)
            ),
            value.choices,
        ),
        parameter.default.kind.value,
        parameter.default.literal,
        parameter.help_key.value if parameter.help_key is not None else None,
        parameter.metavar,
        parameter.show_default,
        parameter.hidden,
        (
            parameter.constraint.minimum,
            parameter.constraint.maximum,
            parameter.constraint.clamp,
            parameter.constraint.case_sensitive,
            parameter.constraint.exists,
            parameter.constraint.file_okay,
            parameter.constraint.dir_okay,
            parameter.constraint.writable,
            parameter.constraint.readable,
            parameter.constraint.resolve_path,
            parameter.constraint.allow_dash,
        ),
        (
            parameter.transport_locus.value,
            parameter.transport_shape.value,
            parameter.transport_role.value,
        ),
    )
    if isinstance(parameter, ArgumentSpec):
        return common
    return (
        *common,
        parameter.declarations,
        parameter.is_flag,
        parameter.flag_value,
        parameter.multiple,
        parameter.count,
        parameter.prompt_key.value if parameter.prompt_key is not None else None,
        parameter.confirmation_prompt_key.value if parameter.confirmation_prompt_key is not None else None,
        parameter.envvar,
        parameter.eager,
        parameter.machine_secret_channel.value if parameter.machine_secret_channel is not None else None,
        parameter.profile_secret_channel.value if parameter.profile_secret_channel is not None else None,
    )


def _argument(name: str, annotation: str, help_key: str) -> tuple[object, ...]:
    """State the complete required-argument contract as literal facts."""
    return (
        "argument",
        name,
        (annotation, *_NO_VALUE_HOOKS),
        "required",
        None,
        help_key,
        None,
        True,
        False,
        _DEFAULT_CONSTRAINT,
        _NO_TRANSPORT,
    )


def _option(
    name: str,
    annotation: str,
    default: object,
    help_key: str | None,
    *,
    default_kind: str = "literal",
    is_flag: bool = False,
    flag_value: object = None,
    multiple: bool = False,
    declarations: tuple[str, ...] | None = None,
    constraint: tuple[object, ...] = _DEFAULT_CONSTRAINT,
) -> tuple[object, ...]:
    """State the complete ordinary-option contract as literal facts."""
    return (
        "option",
        name,
        (annotation, *_NO_VALUE_HOOKS),
        default_kind,
        default,
        help_key,
        None,
        True,
        False,
        constraint,
        _NO_TRANSPORT,
        declarations if declarations is not None else (f"--{name.replace('_', '-')}",),
        is_flag,
        flag_value,
        multiple,
        False,
        None,
        None,
        (),
        False,
        None,
        None,
    )


_EXPECTED_PARAMETERS = {
    "app_ledger_invoice_add": (
        _option(
            "kind",
            "cadrumo.domain.iva.schema:InvoiceKind",
            None,
            "cli.app.ledger.invoice.kind_help",
            default_kind="required",
        ),
        _option("counterparty_name", "builtins:str", None, None, default_kind="required"),
        _option("invoice_number", "builtins:str", None, None, default_kind="required"),
        _option(
            "invoice_date",
            "builtins:str",
            None,
            "cli.app.ledger.evidence.invoice_date_help",
            default_kind="required",
        ),
        _option("taxable_base", "builtins:str", None, None),
        _option(
            "country_code",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.country_code_help",
            default_kind="required",
        ),
        _option("iva_rate", "builtins:str", None, None),
        _option("currency", "builtins:str", "EUR", None),
        _option(
            "operation_type",
            "cadrumo.core.aggregation:IntracomOperationType",
            None,
            "cli.app.ledger.invoice.operation_type_help",
        ),
        _option("operation_date", "builtins:str", None, "cli.app.ledger.invoice.operation_date_help"),
        _option("retention_rate", "builtins:str", None, "cli.app.ledger.invoice.retention_rate_help"),
        _option("retention_amount", "builtins:str", None, "cli.app.ledger.invoice.retention_amount_help"),
        _option(
            "invoice_class",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.invoice_class_help",
        ),
        _option("counterparty_nif", "builtins:str", None, None),
        _option("series", "builtins:str", None, "cli.app.ledger.invoice.series_help"),
        _option(
            "rectifies_invoice_number",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.rectifies_help",
        ),
        _option(
            "rectification_method",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.rectification_method_help",
        ),
        _option(
            "rectification_cause",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.rectification_cause_help",
        ),
        _option(
            "rectification_direction",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.rectification_direction_help",
        ),
        _option(
            "document_received_on",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.document_received_on_help",
        ),
        _option(
            "issuer_increase_election",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.issuer_increase_election_help",
        ),
        _option(
            "issuer_minoracion_election",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.issuer_minoracion_election_help",
        ),
        _option(
            "issuer_minoracion_regularisation_year",
            "builtins:int",
            None,
            "cli.app.ledger.invoice.issuer_minoracion_regularisation_year_help",
            constraint=_YEAR_CONSTRAINT,
        ),
        _option(
            "issuer_minoracion_regularisation_period",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.issuer_minoracion_regularisation_period_help",
        ),
        _option(
            "recipient_increase_year",
            "builtins:int",
            None,
            "cli.app.ledger.invoice.recipient_increase_year_help",
            constraint=_YEAR_CONSTRAINT,
        ),
        _option(
            "recipient_increase_period",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.recipient_increase_period_help",
        ),
        _option(
            "exercised_deduction_year",
            "builtins:int",
            None,
            "cli.app.ledger.invoice.exercised_deduction_year_help",
            constraint=_YEAR_CONSTRAINT,
        ),
        _option(
            "exercised_deduction_period",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.exercised_deduction_period_help",
        ),
        _option(
            "art_80_tres_obligations_attested",
            "builtins:bool",
            None,
            "cli.app.ledger.invoice.art_80_tres_obligations_attested_help",
            is_flag=True,
            flag_value=True,
            declarations=("--art-80-tres-obligations-attested", "--no-art-80-tres-obligations-attested"),
        ),
        _option("recargo", "builtins:str", None, "cli.app.ledger.invoice.recargo_help"),
        _option(
            "iva_category", "cadrumo.domain.iva.schema:IvaCategory", None, "cli.app.ledger.invoice.iva_category_help"
        ),
        _option(
            "arrendamiento_local_negocio",
            "builtins:bool",
            False,
            "cli.app.ledger.invoice.arrendamiento_local_negocio_help",
            is_flag=True,
            flag_value=True,
        ),
        _option("situacion_inmueble", "builtins:str", None, "cli.app.ledger.invoice.situacion_inmueble_help"),
        _option("referencia_catastral", "builtins:str", None, "cli.app.ledger.invoice.referencia_catastral_help"),
        _option("line", "builtins:str", (), "cli.app.ledger.invoice.line_help", multiple=True),
        _option("notes", "builtins:str", "", None),
        _option("fx_rate", "builtins:str", None, "cli.app.ledger.invoice.fx_rate_help"),
    ),
    "app_ledger_invoice_remove": (
        _argument("invoice_id", "builtins:str", "cli.app.ledger.invoice.invoice_id_help"),
        _option("yes", "builtins:bool", False, "cli.app.ledger.invoice.yes_help", is_flag=True, flag_value=True),
    ),
    "app_ledger_invoice_update": (
        _argument("invoice_id", "builtins:str", "cli.app.ledger.invoice.invoice_id_help"),
        _option("counterparty_name", "builtins:str", None, None),
        _option("counterparty_country", "builtins:str", None, None),
        _option("notes", "builtins:str", None, None),
        _option(
            "iva_category", "cadrumo.domain.iva.schema:IvaCategory", None, "cli.app.ledger.invoice.iva_category_help"
        ),
        _option(
            "operation_type",
            "cadrumo.core.aggregation:IntracomOperationType",
            None,
            "cli.app.ledger.invoice.operation_type_help",
        ),
        _option("operation_date", "builtins:str", None, "cli.app.ledger.invoice.operation_date_help"),
        _option("retention_rate", "builtins:str", None, "cli.app.ledger.invoice.retention_rate_help"),
        _option("retention_amount", "builtins:str", None, "cli.app.ledger.invoice.retention_amount_help"),
        _option(
            "invoice_class",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.invoice_class_help",
        ),
        _option("series", "builtins:str", None, "cli.app.ledger.invoice.series_help"),
        _option(
            "rectifies_invoice_number",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.rectifies_help",
        ),
        _option(
            "rectification_method",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.rectification_method_help",
        ),
        _option(
            "rectification_cause",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.rectification_cause_help",
        ),
        _option(
            "rectification_direction",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.rectification_direction_help",
        ),
        _option(
            "document_received_on",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.document_received_on_help",
        ),
        _option(
            "issuer_increase_election",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.issuer_increase_election_help",
        ),
        _option(
            "issuer_minoracion_election",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.issuer_minoracion_election_help",
        ),
        _option(
            "issuer_minoracion_regularisation_year",
            "builtins:int",
            None,
            "cli.app.ledger.invoice.issuer_minoracion_regularisation_year_help",
            constraint=_YEAR_CONSTRAINT,
        ),
        _option(
            "issuer_minoracion_regularisation_period",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.issuer_minoracion_regularisation_period_help",
        ),
        _option(
            "recipient_increase_year",
            "builtins:int",
            None,
            "cli.app.ledger.invoice.recipient_increase_year_help",
            constraint=_YEAR_CONSTRAINT,
        ),
        _option(
            "recipient_increase_period",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.recipient_increase_period_help",
        ),
        _option(
            "exercised_deduction_year",
            "builtins:int",
            None,
            "cli.app.ledger.invoice.exercised_deduction_year_help",
            constraint=_YEAR_CONSTRAINT,
        ),
        _option(
            "exercised_deduction_period",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.exercised_deduction_period_help",
        ),
        _option(
            "art_80_tres_obligations_attested",
            "builtins:bool",
            None,
            "cli.app.ledger.invoice.art_80_tres_obligations_attested_help",
            is_flag=True,
            flag_value=True,
            declarations=("--art-80-tres-obligations-attested", "--no-art-80-tres-obligations-attested"),
        ),
        _option("fx_rate", "builtins:str", None, "cli.app.ledger.invoice.fx_rate_help"),
    ),
    "app_ledger_invoice_view": (_argument("invoice_id", "builtins:str", "cli.app.ledger.invoice.invoice_id_help"),),
    "app_ledger_invoice_wizard": (
        _option(
            "kind",
            "cadrumo.domain.iva.schema:InvoiceKind",
            None,
            "cli.app.ledger.invoice.kind_help",
            default_kind="required",
        ),
        _option("counterparty_nif", "builtins:str", None, None, default_kind="required"),
        _option("counterparty_name", "builtins:str", None, None, default_kind="required"),
        _option("invoice_number", "builtins:str", None, None, default_kind="required"),
        _option(
            "invoice_date",
            "builtins:str",
            None,
            "cli.app.ledger.evidence.invoice_date_help",
            default_kind="required",
        ),
        _option("taxable_base", "builtins:str", None, None, default_kind="required"),
        _option(
            "country_code",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.country_code_help",
            default_kind="required",
        ),
        _option("iva_rate", "builtins:str", None, None),
        _option("currency", "builtins:str", "EUR", None),
        _option(
            "operation_type",
            "cadrumo.core.aggregation:IntracomOperationType",
            None,
            "cli.app.ledger.invoice.operation_type_help",
        ),
        _option("operation_date", "builtins:str", None, "cli.app.ledger.invoice.operation_date_help"),
        _option("retention_rate", "builtins:str", None, "cli.app.ledger.invoice.retention_rate_help"),
        _option("retention_amount", "builtins:str", None, "cli.app.ledger.invoice.retention_amount_help"),
        _option(
            "invoice_class",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.invoice_class_help",
        ),
        _option("series", "builtins:str", None, "cli.app.ledger.invoice.series_help"),
        _option(
            "rectifies_invoice_number",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.rectifies_help",
        ),
        _option(
            "rectification_method",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.rectification_method_help",
        ),
        _option(
            "rectification_cause",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.rectification_cause_help",
        ),
        _option(
            "rectification_direction",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.rectification_direction_help",
        ),
        _option(
            "document_received_on",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.document_received_on_help",
        ),
        _option(
            "issuer_increase_election",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.issuer_increase_election_help",
        ),
        _option(
            "issuer_minoracion_election",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.issuer_minoracion_election_help",
        ),
        _option(
            "issuer_minoracion_regularisation_year",
            "builtins:int",
            None,
            "cli.app.ledger.invoice.issuer_minoracion_regularisation_year_help",
            constraint=_YEAR_CONSTRAINT,
        ),
        _option(
            "issuer_minoracion_regularisation_period",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.issuer_minoracion_regularisation_period_help",
        ),
        _option(
            "recipient_increase_year",
            "builtins:int",
            None,
            "cli.app.ledger.invoice.recipient_increase_year_help",
            constraint=_YEAR_CONSTRAINT,
        ),
        _option(
            "recipient_increase_period",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.recipient_increase_period_help",
        ),
        _option(
            "exercised_deduction_year",
            "builtins:int",
            None,
            "cli.app.ledger.invoice.exercised_deduction_year_help",
            constraint=_YEAR_CONSTRAINT,
        ),
        _option(
            "exercised_deduction_period",
            "builtins:str",
            None,
            "cli.app.ledger.invoice.exercised_deduction_period_help",
        ),
        _option(
            "art_80_tres_obligations_attested",
            "builtins:bool",
            None,
            "cli.app.ledger.invoice.art_80_tres_obligations_attested_help",
            is_flag=True,
            flag_value=True,
            declarations=("--art-80-tres-obligations-attested", "--no-art-80-tres-obligations-attested"),
        ),
        _option("recargo", "builtins:str", None, "cli.app.ledger.invoice.recargo_help"),
        _option(
            "iva_category", "cadrumo.domain.iva.schema:IvaCategory", None, "cli.app.ledger.invoice.iva_category_help"
        ),
        _option("notes", "builtins:str", "", None),
    ),
}


def test_invoice_lifecycle_parameter_contracts_are_complete_and_ordered() -> None:
    specs = {spec.key: spec for spec in (*LEDGER_INVOICE_INTAKE_COMMAND_SPECS, *LEDGER_INVOICE_LIFECYCLE_COMMAND_SPECS)}

    assert {
        key: tuple(_parameter_contract(parameter) for parameter in specs[key].parameters)
        for key in _EXPECTED_PARAMETERS
    } == _EXPECTED_PARAMETERS


def test_shared_immutable_parameters_preserve_distinct_command_facts() -> None:
    specs = {spec.key: spec for spec in (*LEDGER_INVOICE_INTAKE_COMMAND_SPECS, *LEDGER_INVOICE_LIFECYCLE_COMMAND_SPECS)}
    add = specs["app_ledger_invoice_add"]
    remove = specs["app_ledger_invoice_remove"]
    update = specs["app_ledger_invoice_update"]
    view = specs["app_ledger_invoice_view"]
    wizard = specs["app_ledger_invoice_wizard"]

    assert type(INVOICE_INTAKE_WIZARD_CORE_OPTIONS) is tuple
    assert type(INVOICE_INTAKE_WIZARD_TRAILING_OPTIONS) is tuple
    assert type(INVOICE_LIFECYCLE_METADATA_OPTIONS) is tuple
    assert type(INVOICE_RECTIFICATION_OPTIONS) is tuple
    assert remove.parameters[0] is update.parameters[0] is view.parameters[0] is REQUIRED_INVOICE_ID_ARGUMENT
    assert add.parameters[0] is wizard.parameters[0] is INVOICE_INTAKE_WIZARD_CORE_OPTIONS[0]
    assert add.parameters[4] is not INVOICE_INTAKE_WIZARD_CORE_OPTIONS[4]
    assert all(
        actual is expected
        for actual, expected in zip(add.parameters[1:4], INVOICE_INTAKE_WIZARD_CORE_OPTIONS[1:4], strict=True)
    )
    assert all(
        actual is expected
        for actual, expected in zip(add.parameters[5:8], INVOICE_INTAKE_WIZARD_CORE_OPTIONS[5:8], strict=True)
    )
    assert all(
        actual is expected
        for actual, expected in zip(wizard.parameters[2:9], INVOICE_INTAKE_WIZARD_CORE_OPTIONS[1:], strict=True)
    )
    assert update.parameters[4] is wizard.parameters[30] is add.parameters[30] is OPTIONAL_IVA_CATEGORY_OPTION
    assert all(
        actual is expected
        for actual, expected in zip(update.parameters[5:12], INVOICE_LIFECYCLE_METADATA_OPTIONS, strict=True)
    )
    assert all(
        actual is expected
        for actual, expected in zip(wizard.parameters[9:16], INVOICE_LIFECYCLE_METADATA_OPTIONS, strict=True)
    )
    assert all(
        actual is expected
        for actual, expected in zip(add.parameters[8:13], INVOICE_LIFECYCLE_METADATA_OPTIONS[:5], strict=True)
    )
    assert all(
        actual is expected
        for actual, expected in zip(add.parameters[14:16], INVOICE_LIFECYCLE_METADATA_OPTIONS[5:], strict=True)
    )
    assert add.parameters[29] is wizard.parameters[29] is INVOICE_INTAKE_WIZARD_TRAILING_OPTIONS[0]
    assert add.parameters[31:34] == BUSINESS_PREMISES_LEASE_OPTIONS
    # The four rectification facts, and the elections and attestation beside
    # them, are shared by the three verbs that WRITE an invoice and reach no
    # other: the preview verb takes the lifecycle tuple whole and computes
    # figures none of these facts changes.
    assert all(
        add.parameters[16 + offset] is wizard.parameters[16 + offset] is update.parameters[12 + offset] is option
        for offset, option in enumerate((*INVOICE_RECTIFICATION_OPTIONS, *INVOICE_RECTIFICATION_PERIOD_OPTIONS))
    )
    assert type(INVOICE_RECTIFICATION_PERIOD_OPTIONS) is tuple
    assert add.parameters[35] is wizard.parameters[31] is INVOICE_INTAKE_WIZARD_TRAILING_OPTIONS[1]
    assert add.parameters[36] is update.parameters[25] is DECLARED_FX_RATE_OPTION

    update_notes = update.parameters[3]
    wizard_notes = wizard.parameters[-1]
    add_counterparty_nif = add.parameters[13]
    wizard_counterparty_nif = wizard.parameters[1]
    assert update_notes is not wizard_notes
    assert update_notes.default.literal is None
    assert wizard_notes.default.literal == ""
    assert add_counterparty_nif.default.literal is None
    assert wizard_counterparty_nif.default.kind.value == "required"
