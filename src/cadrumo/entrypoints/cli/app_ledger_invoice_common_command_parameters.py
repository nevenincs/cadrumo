"""Frozen IVA and lifecycle metadata parameters shared by invoice commands."""

from __future__ import annotations

from typing import Final

from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.shared_contracts import (
    DeferredTarget,
    ParameterConstraint,
    ParameterDefault,
    TranslationKey,
    ValueContract,
)

from ...application.ledger.operator_input_contracts import INVOICE_CLASS_INPUT
from .app_ledger_command_spec_support import option_from_application_contract

OPTIONAL_IVA_CATEGORY_OPTION: Final[OptionSpec] = OptionSpec(
    name="iva_category",
    declarations=("--iva-category",),
    value=ValueContract(DeferredTarget("...domain.iva.schema", "IvaCategory", __package__)),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.app.ledger.invoice.iva_category_help"),
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

DECLARED_FX_RATE_OPTION: Final[OptionSpec] = OptionSpec(
    name="fx_rate",
    declarations=("--fx-rate",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.app.ledger.invoice.fx_rate_help"),
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
"""The exchange rate the operator states for a foreign invoice (LIVA art. 79.Once)."""

BUSINESS_PREMISES_LEASE_OPTIONS: Final[tuple[OptionSpec, ...]] = (
    OptionSpec(
        name="arrendamiento_local_negocio",
        declarations=("--arrendamiento-local-negocio",),
        value=ValueContract(DeferredTarget("builtins", "bool")),
        default=ParameterDefault.value(False),
        help_key=TranslationKey("cli.app.ledger.invoice.arrendamiento_local_negocio_help"),
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
    OptionSpec(
        name="situacion_inmueble",
        declarations=("--situacion-inmueble",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.ledger.invoice.situacion_inmueble_help"),
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
        name="referencia_catastral",
        declarations=("--referencia-catastral",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.ledger.invoice.referencia_catastral_help"),
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
)
"""The lessor's business-premises lease facts an issued invoice can state (RD 1065/2007 art. 34.1.d)."""

INVOICE_LIFECYCLE_METADATA_OPTIONS: Final[tuple[OptionSpec, ...]] = (
    OptionSpec(
        name="operation_type",
        declarations=("--operation-type",),
        value=ValueContract(DeferredTarget("...core.aggregation", "IntracomOperationType", __package__)),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.ledger.invoice.operation_type_help"),
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
        name="operation_date",
        declarations=("--operation-date",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.ledger.invoice.operation_date_help"),
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
        name="retention_rate",
        declarations=("--retention-rate",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.ledger.invoice.retention_rate_help"),
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
        name="retention_amount",
        declarations=("--retention-amount",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.ledger.invoice.retention_amount_help"),
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
    option_from_application_contract(INVOICE_CLASS_INPUT, "cli.app.ledger.invoice.invoice_class_help"),
    OptionSpec(
        name="series",
        declarations=("--series",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.ledger.invoice.series_help"),
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
        name="rectifies_invoice_number",
        declarations=("--rectifies-invoice-number",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.ledger.invoice.rectifies_help"),
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
)

INVOICE_RECTIFICATION_OPTIONS: Final[tuple[OptionSpec, ...]] = (
    OptionSpec(
        name="rectification_method",
        declarations=("--rectification-method",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.ledger.invoice.rectification_method_help"),
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
        name="rectification_cause",
        declarations=("--rectification-cause",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.ledger.invoice.rectification_cause_help"),
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
        name="rectification_direction",
        declarations=("--rectification-direction",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.ledger.invoice.rectification_direction_help"),
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
        name="document_received_on",
        declarations=("--document-received-on",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.ledger.invoice.document_received_on_help"),
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
)
"""The facts a factura rectificativa states (RD 1619/2012 art. 15.5, LIVA art. 80 and art. 89).

Declared as their own tuple rather than appended to
:data:`INVOICE_LIFECYCLE_METADATA_OPTIONS` because only the verbs that WRITE an
invoice take them. The preview verb reuses that tuple whole and computes
figures, and none of these four facts changes a figure: the modification they
describe is derived where the Modelo 303 declares it, not on this record.

Each value is a stable untranslated token the served vocabulary declares, so
the verb accepts whatever fact 0141 carries for the invoice's date and holds no
list of its own.
"""

INVOICE_INTAKE_WIZARD_CORE_OPTIONS: Final[tuple[OptionSpec, ...]] = (
    OptionSpec(
        name="kind",
        declarations=("--kind",),
        value=ValueContract(DeferredTarget("...domain.iva.schema", "InvoiceKind", __package__)),
        default=ParameterDefault.required(),
        help_key=TranslationKey("cli.app.ledger.invoice.kind_help"),
    ),
    OptionSpec(
        name="counterparty_name",
        declarations=("--counterparty-name",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.required(),
        help_key=None,
    ),
    OptionSpec(
        name="invoice_number",
        declarations=("--invoice-number",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.required(),
        help_key=None,
    ),
    OptionSpec(
        name="invoice_date",
        declarations=("--invoice-date",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.required(),
        help_key=TranslationKey("cli.app.ledger.evidence.invoice_date_help"),
    ),
    OptionSpec(
        name="taxable_base",
        declarations=("--taxable-base",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.required(),
        help_key=None,
    ),
    OptionSpec(
        name="country_code",
        declarations=("--country-code",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.required(),
        help_key=TranslationKey("cli.app.ledger.invoice.country_code_help"),
    ),
    OptionSpec(
        name="iva_rate",
        declarations=("--iva-rate",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=None,
    ),
    OptionSpec(
        name="currency",
        declarations=("--currency",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value("EUR"),
        help_key=None,
    ),
)

INVOICE_INTAKE_WIZARD_TRAILING_OPTIONS: Final[tuple[OptionSpec, ...]] = (
    OptionSpec(
        name="recargo",
        declarations=("--recargo",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.ledger.invoice.recargo_help"),
    ),
    OptionSpec(
        name="notes",
        declarations=("--notes",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(""),
        help_key=None,
    ),
)

__all__ = [
    "BUSINESS_PREMISES_LEASE_OPTIONS",
    "DECLARED_FX_RATE_OPTION",
    "INVOICE_INTAKE_WIZARD_CORE_OPTIONS",
    "INVOICE_INTAKE_WIZARD_TRAILING_OPTIONS",
    "INVOICE_LIFECYCLE_METADATA_OPTIONS",
    "INVOICE_RECTIFICATION_OPTIONS",
    "OPTIONAL_IVA_CATEGORY_OPTION",
]
