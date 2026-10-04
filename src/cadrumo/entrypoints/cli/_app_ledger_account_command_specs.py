"""Authored CommandSpec declarations for the ``app ledger account`` own-account surface."""

from __future__ import annotations

from cadrumo.application.operator_surface.command_ports import CommandNodeKind

from ._app_ledger_command_spec_policies import _POLICY_1, _POLICY_4, _POLICY_5
from ._app_ledger_command_spec_support import (
    _GROUP_INVOCATION,
    _LEAF_INVOCATION,
    _NO_RESULT_SCHEMA,
    _optional_text_option,
    _required_text_argument,
    _required_text_option,
)
from ._command_secret_contracts import (
    MachineSecretFieldSpec,
    MachineSecretSpec,
    MachineSecretVariantSpec,
)
from .command_parameter_contracts import OptionSpec, ParameterSpec
from .command_shared_contracts import (
    DeferredTarget,
    LazyBinding,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from .command_spec import CommandSpec, ExecutionPolicySpec
from .machine_secret_command_parameters import MACHINE_SECRET_FD_OPTION, MACHINE_SECRET_STDIN_OPTION

_GROUP = "app_ledger_account"
_ACCOUNT_ID = _required_text_argument("own_account_id", "cli.app.ledger.account.account_id_help")
_SECRET_FIELDS = ("iban", "swift_bic", "bank_name", "bank_address", "bank_city", "bank_country_code")


def _choice_option(name: str, declarations: tuple[str, ...], choices: tuple[str, ...], *, required: bool) -> OptionSpec:
    return OptionSpec(
        name=name,
        declarations=declarations,
        value=ValueContract(DeferredTarget("builtins", "str"), choices=choices),
        default=ParameterDefault.required() if required else ParameterDefault.value(None),
        help_key=TranslationKey(f"cli.app.ledger.account.{name}_help"),
    )


def _secrets(model: str) -> MachineSecretSpec:
    return MachineSecretSpec(
        (
            MachineSecretVariantSpec(
                "account",
                tuple(MachineSecretFieldSpec(field) for field in _SECRET_FIELDS),
                DeferredTarget("._ledger_account_cli", model, __package__),
            ),
        ),
    )


def _leaf(
    verb: str,
    parameters: tuple[ParameterSpec, ...],
    *,
    policy: ExecutionPolicySpec,
    result: str,
    machine_secret: MachineSecretSpec | None = None,
) -> CommandSpec:
    return CommandSpec(
        f"{_GROUP}_{verb}",
        _GROUP,
        verb,
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey(f"cli.app.ledger.account.{verb}_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=parameters,
        policy=policy,
        handler=LazyBinding.available(DeferredTarget("._ledger_account_cli", f"account_{verb}", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("._ledger_account_payloads", result, __package__),
            identity=f"ledger.account.{verb}",
        ),
        machine_secret=machine_secret,
    )


_HOLDINGS = ("titular", "cotitular")
_ROLES = ("charge", "refund")

LEDGER_ACCOUNT_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        _GROUP,
        "app_ledger",
        "account",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.app.ledger.account.group_help"),
        short_help_key=None,
        invocation=_GROUP_INVOCATION,
        parameters=(),
        policy=_POLICY_1,
        handler=None,
        result_schema=_NO_RESULT_SCHEMA,
    ),
    _leaf(
        "add",
        (
            _required_text_argument("label", "cli.app.ledger.account.label_help"),
            _choice_option("holding", ("--holding",), _HOLDINGS, required=True),
            _optional_text_option("currency", ("--currency",), "cli.app.ledger.account.currency_help"),
            _optional_text_option("opened_on", ("--opened-on",), "cli.app.ledger.account.opened_on_help"),
            MACHINE_SECRET_STDIN_OPTION,
            MACHINE_SECRET_FD_OPTION,
        ),
        policy=_POLICY_4,
        result="OwnAccountChangeResult",
        machine_secret=_secrets("OwnAccountAddSecrets"),
    ),
    _leaf("list", (), policy=_POLICY_5, result="OwnAccountListResult"),
    _leaf("show", (_ACCOUNT_ID,), policy=_POLICY_5, result="OwnAccountShowResult"),
    _leaf(
        "update",
        (
            _ACCOUNT_ID,
            _optional_text_option("label", ("--label",), "cli.app.ledger.account.new_label_help"),
            _choice_option("holding", ("--holding",), _HOLDINGS, required=False),
            _optional_text_option("currency", ("--currency",), "cli.app.ledger.account.currency_help"),
            _optional_text_option("opened_on", ("--opened-on",), "cli.app.ledger.account.opened_on_help"),
            MACHINE_SECRET_STDIN_OPTION,
            MACHINE_SECRET_FD_OPTION,
        ),
        policy=_POLICY_4,
        result="OwnAccountChangeResult",
        machine_secret=_secrets("OwnAccountUpdateSecrets"),
    ),
    _leaf(
        "close",
        (_ACCOUNT_ID, _required_text_option("closed_on", ("--on",), "cli.app.ledger.account.closed_on_help")),
        policy=_POLICY_4,
        result="OwnAccountChangeResult",
    ),
    _leaf("remove", (_ACCOUNT_ID,), policy=_POLICY_4, result="OwnAccountChangeResult"),
    _leaf(
        "designate",
        (
            _ACCOUNT_ID,
            _choice_option("role", ("--role",), _ROLES, required=True),
            _optional_text_option("modelo", ("--modelo",), "cli.app.ledger.account.modelo_help"),
        ),
        policy=_POLICY_4,
        result="OwnAccountChangeResult",
    ),
    _leaf(
        "undesignate",
        (
            _choice_option("role", ("--role",), _ROLES, required=True),
            _optional_text_option("modelo", ("--modelo",), "cli.app.ledger.account.modelo_help"),
        ),
        policy=_POLICY_4,
        result="OwnAccountChangeResult",
    ),
)

__all__ = ["LEDGER_ACCOUNT_COMMAND_SPECS"]
