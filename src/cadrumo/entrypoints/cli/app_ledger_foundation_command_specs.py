"""Declare the command specs for the ledger foundation commands."""

from __future__ import annotations

from cadrumo_client.commands.parameters import OptionSpec
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

from ...application.ledger.operator_input_contracts import (
    COUNTERPARTY_IDENTIFICATION_STATE_INPUT,
    DEDUCTION_FACT_KIND_INPUT,
    IVA_CATEGORY_INPUT,
)
from .app_ledger_command_spec_policies import (
    POLICY_1,
    POLICY_2,
    POLICY_3,
    POLICY_4,
    POLICY_6,
)
from .app_ledger_command_spec_support import (
    ARCHIVE_REASON_OPTION,
    LEDGER_ACTOR_OPTION,
    LEDGER_ADD_CATEGORY_ID_OPTION,
    LEDGER_RENTAL_LINK_OPTIONS,
    LEDGER_SAVINGS_LINK_OPTIONS,
    LEDGER_USAGE_RATIO_ID_OPTION,
    OPTIONAL_YEAR_OPTION,
    blank_default_text_option,
    boolean_flag_option,
    irpf_category_option,
    option_from_application_contract,
    optional_text_option,
    repeatable_text_option,
    required_text_argument,
    required_text_option,
)

LEDGER_FOUNDATION_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_ledger",
        "app",
        "ledger",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.ledger.app_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=True, context_parameter=None),
        parameters=(),
        policy=POLICY_1,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        "app_ledger_add",
        "app_ledger",
        "add",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.ledger.add.help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            required_text_option("booked_date", ("--date",), "cli.ledger.add.date_help"),
            required_text_option("amount", ("--amount",), "cli.ledger.add.amount_help"),
            OptionSpec(
                name="direction",
                declarations=("--direction",),
                value=ValueContract(
                    DeferredTarget("...domain.transactions.enums", "TransactionDirection", __package__)
                ),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.ledger.add.direction_help"),
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
            required_text_option("description", ("--description",), "cli.ledger.add.description_help"),
            optional_text_option("value_date", ("--value-date",), "cli.ledger.add.value_date_help"),
            optional_text_option("operation_date", ("--operation-date",), "cli.ledger.add.operation_date_help"),
            optional_text_option("accrual_date", ("--accrual-date",), "cli.ledger.add.accrual_date_help"),
            OptionSpec(
                name="currency",
                declarations=("--currency",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value("EUR"),
                help_key=TranslationKey("cli.ledger.add.currency_help"),
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
            optional_text_option("counterparty", ("--counterparty",), "cli.ledger.add.counterparty_help"),
            OptionSpec(
                name="business_classification",
                declarations=("--classification",),
                value=ValueContract(
                    DeferredTarget("...domain.transactions.enums", "BusinessClassification", __package__)
                ),
                default=ParameterDefault.value("NOT_YET_PROCESSED"),
                help_key=TranslationKey("cli.ledger.add.classification_help"),
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
            optional_text_option("business_pct", ("--business-pct",), "cli.ledger.add.business_pct_help"),
            LEDGER_ADD_CATEGORY_ID_OPTION,
            optional_text_option("taxable_base", ("--taxable-base",), "cli.ledger.add.taxable_base_help"),
            optional_text_option("iva_rate", ("--iva-rate",), "cli.ledger.add.iva_rate_help"),
            optional_text_option("iva_amount", ("--iva-amount",), "cli.ledger.add.iva_amount_help"),
            option_from_application_contract(IVA_CATEGORY_INPUT, "cli.ledger.classify.iva_category_help"),
            option_from_application_contract(DEDUCTION_FACT_KIND_INPUT, "cli.ledger.classify.deduction_fact_kind_help"),
            optional_text_option(
                "investment_asset_id",
                ("--investment-asset-id",),
                "cli.ledger.classify.investment_asset_id_help",
            ),
            optional_text_option(
                "iva_vehicle_use",
                ("--iva-vehicle-use",),
                "cli.ledger.classify.iva_vehicle_use_help",
            ),
            optional_text_option(
                "counterparty_country", ("--counterparty-country",), "cli.ledger.classify.counterparty_country_help"
            ),
            option_from_application_contract(
                COUNTERPARTY_IDENTIFICATION_STATE_INPUT,
                "cli.ledger.classify.counterparty_identification_state_help",
            ),
            *LEDGER_RENTAL_LINK_OPTIONS,
            *LEDGER_SAVINGS_LINK_OPTIONS,
            optional_text_option("recargo_amount", ("--recargo-amount",), "cli.ledger.add.recargo_amount_help"),
            irpf_category_option("cli.ledger.add.irpf_category_help"),
            LEDGER_USAGE_RATIO_ID_OPTION,
            optional_text_option(
                "prorrata_reference", ("--prorrata-reference",), "cli.ledger.add.prorrata_reference_help"
            ),
            OptionSpec(
                name="art_104_tres_exclusion",
                declarations=("--art-104-tres-exclusion",),
                value=ValueContract(DeferredTarget("...core.prorrata_exclusions", "Art104TresExclusion", __package__)),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.ledger.add.art_104_tres_exclusion_help"),
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
                name="input_classification",
                declarations=("--input-classification",),
                # Raw text: the handler projects it through the registry on the
                # transaction's own date, which a boundary type cannot know.
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.ledger.add.input_classification_help"),
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
            optional_text_option("prorrata_sector", ("--sector",), "cli.ledger.add.prorrata_sector_help"),
            optional_text_option(
                "purchase_invoice_evidence_id",
                ("--purchase-invoice-evidence-id",),
                "cli.ledger.add.purchase_invoice_evidence_help",
            ),
            repeatable_text_option(
                "attachment_ids", ("--attachment-id",), "cli.ledger.add.attachment_help", non_blank=True
            ),
            blank_default_text_option("notes", ("--notes",), "cli.ledger.add.notes_help"),
            LEDGER_ACTOR_OPTION,
            optional_text_option("idempotency_key", ("--idempotency-key",), "cli.ledger.add.idempotency_key_help"),
            optional_text_option(
                "source_jurisdiction", ("--source-jurisdiction",), "cli.ledger.add.source_jurisdiction_help"
            ),
            optional_text_option("account", ("--account",), "cli.ledger.add.account_help"),
        ),
        policy=POLICY_2,
        handler=LazyBinding.available(DeferredTarget(".ledger_commands", "ledger_add", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_results", "LedgerAddResult", __package__),
            identity="ledger.add",
        ),
    ),
    CommandSpec(
        "app_ledger_allocate",
        "app_ledger",
        "allocate",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.ledger.allocate.help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            required_text_argument("transaction_id", "cli.ledger.allocate.id_help", non_blank=True),
            required_text_option("business_pct", ("--business-pct",), "cli.ledger.allocate.business_pct_help"),
            LEDGER_ADD_CATEGORY_ID_OPTION,
            LEDGER_USAGE_RATIO_ID_OPTION,
            optional_text_option(
                "prorrata_reference", ("--prorrata-reference",), "cli.ledger.allocate.prorrata_reference_help"
            ),
            LEDGER_ACTOR_OPTION,
        ),
        policy=POLICY_3,
        handler=LazyBinding.available(DeferredTarget(".ledger_commands", "ledger_allocate", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_results", "LedgerAllocateResult", __package__),
            identity="ledger.allocate",
        ),
    ),
    CommandSpec(
        "app_ledger_archive",
        "app_ledger",
        "archive",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.ledger.archive.help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            required_text_argument("transaction_id", "cli.ledger.archive.id_help", non_blank=True),
            ARCHIVE_REASON_OPTION,
            boolean_flag_option("yes", ("--yes",), "cli.ledger.archive.yes_help"),
            LEDGER_ACTOR_OPTION,
        ),
        policy=POLICY_4,
        handler=LazyBinding.available(DeferredTarget(".ledger_lifecycle_cli", "ledger_archive", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_results", "LedgerArchiveResult", __package__),
            identity="ledger.archive",
        ),
    ),
    CommandSpec(
        "app_ledger_attach",
        "app_ledger",
        "attach",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.ledger.attach.help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            required_text_argument("transaction_id", "cli.ledger.attach.id_help", non_blank=True),
            optional_text_option(
                "purchase_invoice_evidence_id",
                ("--purchase-invoice-evidence-id",),
                "cli.ledger.attach.purchase_invoice_evidence_help",
            ),
            repeatable_text_option(
                "attachment_ids", ("--attachment-id",), "cli.ledger.attach.attachment_help", non_blank=True
            ),
            LEDGER_ACTOR_OPTION,
        ),
        policy=POLICY_4,
        handler=LazyBinding.available(DeferredTarget(".ledger_lifecycle_cli", "ledger_attach", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_results", "LedgerAttachResult", __package__),
            identity="ledger.attach",
        ),
    ),
    CommandSpec(
        "app_ledger_bienes_inversion",
        "app_ledger",
        "bienes-inversion",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.app.ledger.bienes_inversion.group_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=True, context_parameter=None),
        parameters=(),
        policy=POLICY_1,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        "app_ledger_categories",
        "app_ledger",
        "categories",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.ledger.categories.help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(),
        policy=POLICY_6,
        handler=LazyBinding.available(DeferredTarget(".ledger_read_commands", "ledger_categories", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "...application.reference_catalogue_contracts", "LedgerCategoriesResult", __package__
            ),
            identity="ledger.categories",
        ),
    ),
    CommandSpec(
        "app_ledger_check",
        "app_ledger",
        "check",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.ledger.check.help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            optional_text_option("bucket_id_option", ("--bucket-id",), "cli.ledger.check.bucket_id_help"),
            optional_text_option("period", ("--period",), "cli.ledger.check.period_help"),
            OPTIONAL_YEAR_OPTION,
        ),
        policy=POLICY_6,
        handler=LazyBinding.available(DeferredTarget(".ledger_read_commands", "ledger_check", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_diagnostic_results", "LedgerCheckResult", __package__),
            identity="ledger.check",
        ),
    ),
)

__all__ = ["LEDGER_FOUNDATION_COMMAND_SPECS"]
"""Authored CommandSpec declarations for the ledger foundation surface."""
"""Authored CommandSpec declarations for the ledger foundation surface."""
