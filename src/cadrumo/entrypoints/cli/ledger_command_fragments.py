"""Shared constructors for declarative ledger command fragments."""

from __future__ import annotations

from typing import Final

from cadrumo_client.commands.parameters import ArgumentSpec, OptionSpec
from cadrumo_client.commands.shared_contracts import (
    TEXT_VALUE,
    DeferredTarget,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)

_REQUIRED: Final[ParameterDefault] = ParameterDefault.required()


def option(
    *, name: str, declaration: str, value: ValueContract, default: ParameterDefault, help_key: str
) -> OptionSpec:
    """Build one ordinary non-flag option."""
    return OptionSpec(
        name=name,
        declarations=(declaration,),
        value=value,
        default=default,
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


def argument(*, name: str, help_key: str) -> ArgumentSpec:
    """Build one required positional text argument."""
    return ArgumentSpec(
        name=name,
        value=TEXT_VALUE,
        default=_REQUIRED,
        help_key=TranslationKey(help_key),
        metavar=None,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    )


def result_schema(model: str, identity: str, *, result_module: str) -> ResultSchemaSpec:
    """Declare a deferred result model from its owning CLI module."""
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget(result_module, model, __package__),
        identity=identity,
    )
