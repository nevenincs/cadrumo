"""Declarative command specs for the ledger invoice intake CLI commands."""

from __future__ import annotations

from dataclasses import replace

from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.secret_contracts import (
    MachineSecretFieldSpec,
    MachineSecretSpec,
    MachineSecretVariantSpec,
)
from cadrumo_client.commands.secret_parameters import MACHINE_SECRET_FD_OPTION, MACHINE_SECRET_STDIN_OPTION
from cadrumo_client.commands.shared_contracts import (
    NON_BLANK_CONSTRAINT,
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

from ...application.ledger.operator_input_contracts import INVOICE_KIND_INPUT
from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from .app_ledger_command_spec_policies import (
    POLICY_2,
    POLICY_6,
)
from .app_ledger_command_spec_support import option_from_application_contract
from .app_ledger_invoice_common_command_parameters import (
    BUSINESS_PREMISES_LEASE_OPTIONS,
    INVOICE_INTAKE_WIZARD_CORE_OPTIONS,
    INVOICE_INTAKE_WIZARD_TRAILING_OPTIONS,
    INVOICE_LIFECYCLE_METADATA_OPTIONS,
    OPTIONAL_IVA_CATEGORY_OPTION,
)

LEDGER_INVOICE_INTAKE_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_ledger_invoice_add",
        "app_ledger_invoice",
        "add",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.invoice.add_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            *(
                replace(option, default=ParameterDefault.value(None)) if option.name == "taxable_base" else option
                for option in INVOICE_INTAKE_WIZARD_CORE_OPTIONS
            ),
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
            *BUSINESS_PREMISES_LEASE_OPTIONS,
            OptionSpec(
                name="line",
                declarations=("--line",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(()),
                help_key=TranslationKey("cli.app.ledger.invoice.line_help"),
                metavar=None,
                is_flag=False,
                flag_value=None,
                multiple=True,
                count=False,
                eager=False,
                constraint=ParameterConstraint(),
                show_default=True,
                hidden=False,
            ),
            INVOICE_INTAKE_WIZARD_TRAILING_OPTIONS[1],
        ),
        policy=POLICY_2,
        handler=LazyBinding.available(DeferredTarget(".ledger_business_invoice_commands", "invoice_add", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_catalogue_invoice_results", "CatalogueInvoiceCreatePayload", __package__),
            identity="ledger.invoice.add",
        ),
    ),
    CommandSpec(
        "app_ledger_invoice_duplicate",
        "app_ledger_invoice",
        "duplicate",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.invoice.duplicate_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="kind",
                declarations=("--kind",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.app.ledger.invoice.duplicate_kind_help"),
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
            MACHINE_SECRET_STDIN_OPTION,
            MACHINE_SECRET_FD_OPTION,
        ),
        policy=POLICY_6,
        handler=LazyBinding.available(DeferredTarget(".invoice_duplicate_commands", "invoice_duplicate", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_results", "LedgerInvoiceDuplicateEnvelope", __package__),
            identity="ledger.invoice.duplicate",
        ),
        machine_secret=MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "document",
                    (
                        MachineSecretFieldSpec("invoice_number"),
                        MachineSecretFieldSpec("counterparty_tax_id"),
                        MachineSecretFieldSpec("invoice_date"),
                        MachineSecretFieldSpec("grand_total"),
                    ),
                    DeferredTarget(".invoice_duplicate_commands", "InvoiceDuplicateSecrets", __package__),
                ),
            ),
        ),
    ),
    CommandSpec(
        "app_ledger_invoice_preview",
        "app_ledger_invoice",
        "preview",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.invoice.preview_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            *(
                replace(option, default=ParameterDefault.value(None))
                for option in INVOICE_INTAKE_WIZARD_CORE_OPTIONS
                if option.name != "iva_rate"
            ),
            *INVOICE_LIFECYCLE_METADATA_OPTIONS,
            INVOICE_INTAKE_WIZARD_TRAILING_OPTIONS[0],
            OptionSpec(
                name="printed_total",
                declarations=("--printed-total",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.ledger.invoice.preview_printed_total_help"),
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
            *BUSINESS_PREMISES_LEASE_OPTIONS,
            INVOICE_INTAKE_WIZARD_TRAILING_OPTIONS[1],
            OptionSpec(
                name="stored_invoice_id",
                declarations=("--stored-invoice-id",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.ledger.invoice.preview_stored_invoice_id_help"),
                metavar=None,
                is_flag=False,
                flag_value=None,
                multiple=False,
                count=False,
                eager=False,
                constraint=NON_BLANK_CONSTRAINT,
                show_default=True,
                hidden=False,
            ),
            OptionSpec(
                name="stored_grand_total",
                declarations=("--stored-grand-total",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.ledger.invoice.preview_stored_grand_total_help"),
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
                name="operation_date_role",
                declarations=("--operation-date-role",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.ledger.invoice.preview_operation_date_role_help"),
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
            MACHINE_SECRET_STDIN_OPTION,
            MACHINE_SECRET_FD_OPTION,
        ),
        policy=POLICY_6,
        handler=LazyBinding.available(DeferredTarget(".invoice_preview_commands", "invoice_preview", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_results", "LedgerInvoicePreviewResult", __package__),
            identity="ledger.invoice.preview",
        ),
        machine_secret=MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "draft",
                    (
                        MachineSecretFieldSpec("counterparty_nif"),
                        MachineSecretFieldSpec("lines"),
                    ),
                    DeferredTarget(".invoice_preview_commands", "InvoicePreviewSecrets", __package__),
                ),
            ),
        ),
    ),
    CommandSpec(
        "app_ledger_invoice_import",
        "app_ledger_invoice",
        "import",
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
                constraint=ParameterConstraint(exists=True, dir_okay=False),
                show_default=True,
                hidden=False,
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            option_from_application_contract(INVOICE_KIND_INPUT, "cli.app.ledger.invoice.kind_help"),
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
        policy=POLICY_2,
        handler=LazyBinding.available(
            DeferredTarget(".ledger_business_invoice_commands", "invoice_import", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_catalogue_invoice_results", "CatalogueInvoiceImportResult", __package__),
            identity="ledger.invoice.import",
        ),
    ),
)

__all__ = ["LEDGER_INVOICE_INTAKE_COMMAND_SPECS"]
"""Authored CommandSpec declarations for the ledger invoice intake surface."""
"""Authored CommandSpec declarations for the ledger invoice intake surface."""
