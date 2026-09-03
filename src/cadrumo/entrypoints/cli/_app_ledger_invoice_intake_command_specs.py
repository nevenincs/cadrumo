"""Authored CommandSpec declarations for the ledger invoice intake surface."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from ._app_ledger_command_spec_policies import (
    _POLICY_2,
)
from .app_ledger_invoice_common_command_parameters import (
    INVOICE_INTAKE_WIZARD_CORE_OPTIONS,
    INVOICE_INTAKE_WIZARD_TRAILING_OPTIONS,
    INVOICE_LIFECYCLE_METADATA_OPTIONS,
    OPTIONAL_IVA_CATEGORY_OPTION,
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

LEDGER_INVOICE_INTAKE_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_ledger_invoice_add",
        parent_key="app_ledger_invoice",
        token="add",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.invoice.add_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            *INVOICE_INTAKE_WIZARD_CORE_OPTIONS,
            *INVOICE_LIFECYCLE_METADATA_OPTIONS[:5],
            OptionSpec(
                name="counterparty_nif",
                declarations=("--counterparty-nif",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=None,
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
            *INVOICE_LIFECYCLE_METADATA_OPTIONS[5:],
            INVOICE_INTAKE_WIZARD_TRAILING_OPTIONS[0],
            OPTIONAL_IVA_CATEGORY_OPTION,
            INVOICE_INTAKE_WIZARD_TRAILING_OPTIONS[1],
        ),
        policy=_POLICY_2,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._ledger_business_invoice_cli", "invoice_add")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._ledger_catalogue_invoice_payloads", "CatalogueInvoiceCreatePayload"
            ),
            identity="ledger.invoice.add",
        ),
    ),
    CommandSpec(
        key="app_ledger_invoice_import",
        parent_key="app_ledger_invoice",
        token="import",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.invoice.import_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="file",
                declarations=("--file",),
                value=ValueContract(DeferredTarget("pathlib", "Path")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.app.ledger.invoice.import_file_help"),
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
            OptionSpec(
                name="kind",
                declarations=("--kind",),
                value=ValueContract(DeferredTarget("cadrumo.domain.iva.classification", "InvoiceKind")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.app.ledger.invoice.kind_help"),
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
                name="country",
                declarations=("--country",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.ledger.invoice.import_country_help"),
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
        policy=_POLICY_2,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._ledger_business_invoice_cli", "invoice_import")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._ledger_catalogue_invoice_payloads", "CatalogueInvoiceImportResult"
            ),
            identity="ledger.invoice.import",
        ),
    ),
)

__all__ = ["LEDGER_INVOICE_INTAKE_COMMAND_SPECS"]
