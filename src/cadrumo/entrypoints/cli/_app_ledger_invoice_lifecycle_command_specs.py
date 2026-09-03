"""Authored CommandSpec declarations for the ledger invoice lifecycle surface."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from typing import Final

from ._app_ledger_command_spec_policies import (
    _POLICY_2,
    _POLICY_4,
    _POLICY_5,
    _POLICY_9,
)
from .app_ledger_invoice_common_command_parameters import (
    INVOICE_INTAKE_WIZARD_CORE_OPTIONS,
    INVOICE_INTAKE_WIZARD_TRAILING_OPTIONS,
    INVOICE_LIFECYCLE_METADATA_OPTIONS,
    OPTIONAL_IVA_CATEGORY_OPTION,
)
from .command_spec import (
    ArgumentSpec,
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

_REQUIRED_INVOICE_ID_ARGUMENT: Final[ArgumentSpec] = ArgumentSpec(
    name="invoice_id",
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.required(),
    help_key=TranslationKey("cli.app.ledger.invoice.invoice_id_help"),
    metavar=None,
    constraint=ParameterConstraint(),
    show_default=True,
    hidden=False,
)

LEDGER_INVOICE_LIFECYCLE_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_ledger_invoice_list",
        parent_key="app_ledger_invoice",
        token="list",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.invoice.list_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="kind",
                declarations=("--kind",),
                value=ValueContract(DeferredTarget("cadrumo.domain.iva.classification", "InvoiceKind")),
                default=ParameterDefault.value(None),
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
        ),
        policy=_POLICY_5,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._ledger_business_invoice_cli", "invoice_list")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._ledger_catalogue_invoice_payloads", "CatalogueInvoiceListResult"
            ),
            identity="ledger.invoice.list",
        ),
    ),
    CommandSpec(
        key="app_ledger_invoice_remove",
        parent_key="app_ledger_invoice",
        token="remove",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.invoice.remove_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            _REQUIRED_INVOICE_ID_ARGUMENT,
            OptionSpec(
                name="yes",
                declarations=("--yes",),
                value=ValueContract(DeferredTarget("builtins", "bool")),
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.app.ledger.invoice.yes_help"),
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
        ),
        policy=_POLICY_9,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._ledger_business_invoice_cli", "invoice_remove")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._ledger_catalogue_invoice_payloads", "CatalogueInvoiceRemovePayload"
            ),
            identity="ledger.invoice.remove",
        ),
    ),
    CommandSpec(
        key="app_ledger_invoice_update",
        parent_key="app_ledger_invoice",
        token="update",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.invoice.update_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            _REQUIRED_INVOICE_ID_ARGUMENT,
            OptionSpec(
                name="counterparty_name",
                declarations=("--counterparty-name",),
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
            OptionSpec(
                name="counterparty_country",
                declarations=("--counterparty-country",),
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
            OptionSpec(
                name="notes",
                declarations=("--notes",),
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
            OPTIONAL_IVA_CATEGORY_OPTION,
            *INVOICE_LIFECYCLE_METADATA_OPTIONS,
        ),
        policy=_POLICY_4,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._ledger_business_invoice_cli", "invoice_update")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._ledger_catalogue_invoice_payloads", "CatalogueInvoiceUpdatePayload"
            ),
            identity="ledger.invoice.update",
        ),
    ),
    CommandSpec(
        key="app_ledger_invoice_view",
        parent_key="app_ledger_invoice",
        token="view",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.invoice.view_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(_REQUIRED_INVOICE_ID_ARGUMENT,),
        policy=_POLICY_5,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._ledger_business_invoice_cli", "invoice_view")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._ledger_catalogue_invoice_payloads", "CatalogueInvoiceViewResult"
            ),
            identity="ledger.invoice.view",
        ),
    ),
    CommandSpec(
        key="app_ledger_invoice_wizard",
        parent_key="app_ledger_invoice",
        token="wizard",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.invoice.wizard_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            INVOICE_INTAKE_WIZARD_CORE_OPTIONS[0],
            OptionSpec(
                name="counterparty_nif",
                declarations=("--counterparty-nif",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
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
            *INVOICE_INTAKE_WIZARD_CORE_OPTIONS[1:],
            *INVOICE_LIFECYCLE_METADATA_OPTIONS,
            INVOICE_INTAKE_WIZARD_TRAILING_OPTIONS[0],
            OPTIONAL_IVA_CATEGORY_OPTION,
            INVOICE_INTAKE_WIZARD_TRAILING_OPTIONS[1],
        ),
        policy=_POLICY_2,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._ledger_business_invoice_cli", "invoice_wizard")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._ledger_catalogue_invoice_payloads", "CatalogueInvoiceWizardResult"
            ),
            identity="ledger.invoice.wizard",
        ),
    ),
)

__all__ = ["LEDGER_INVOICE_LIFECYCLE_COMMAND_SPECS"]
