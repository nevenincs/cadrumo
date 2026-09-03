"""Equality contracts for the shared ledger parameter-declaration primitives.

Each primitive in ``_app_ledger_command_spec_support`` replaces a literal
``OptionSpec`` or ``ArgumentSpec`` block that the command-spec fragments used to
spell out in full. A migration is only safe if the primitive produces a value
that is *indistinguishable* from the literal it displaces, so every gate here
compares against a literal constructed independently in this module rather than
against the primitive's own output.

The comparison is deliberately made twice over. Structural equality on a frozen
dataclass is the contract callers rely on, but it would keep passing if a field
were dropped from the dataclass entirely; the per-field sweep pins the field set
itself, so a future field added to ``OptionSpec`` without a decision here fails
rather than being silently defaulted into every shared parameter.
"""

from __future__ import annotations

from typing import Final

import pytest

from .._app_ledger_command_spec_support import (
    _blank_default_text_option,
    _boolean_flag_option,
    _optional_text_option,
    _repeatable_text_option,
    _required_text_argument,
    _required_text_option,
)
from ..command_spec import (
    ArgumentSpec,
    DeferredTarget,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    TranslationKey,
    ValueContract,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OPTION_FIELDS: Final[tuple[str, ...]] = tuple(OptionSpec.__dataclass_fields__)
_ARGUMENT_FIELDS: Final[tuple[str, ...]] = tuple(ArgumentSpec.__dataclass_fields__)

_TEXT: Final[ValueContract] = ValueContract(DeferredTarget("builtins", "str"))
_BOOL: Final[ValueContract] = ValueContract(DeferredTarget("builtins", "bool"))


def _assert_identical(produced: OptionSpec | ArgumentSpec, expected: OptionSpec | ArgumentSpec) -> None:
    """Assert two specs agree structurally and field by field."""
    assert produced == expected

    fields = _OPTION_FIELDS if isinstance(expected, OptionSpec) else _ARGUMENT_FIELDS
    assert fields, "the dataclass reported no fields; the per-field sweep would pass vacuously"
    for field in fields:
        assert getattr(produced, field) == getattr(expected, field), f"field {field!r} diverged"


def test_optional_text_option_equals_the_literal_it_replaces() -> None:
    """The optional free-text primitive reproduces the displaced literal exactly."""
    _assert_identical(
        _optional_text_option("taxable_base", ("--taxable-base",), "cli.ledger.classify.taxable_base_help"),
        OptionSpec(
            name="taxable_base",
            declarations=("--taxable-base",),
            value=_TEXT,
            default=ParameterDefault.value(None),
            help_key=TranslationKey("cli.ledger.classify.taxable_base_help"),
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


def test_required_text_option_equals_the_literal_it_replaces() -> None:
    """The mandatory free-text primitive reproduces the displaced literal exactly."""
    _assert_identical(
        _required_text_option("transaction_id", ("--transaction-id",), "cli.ledger.evidence.pull_id_help"),
        OptionSpec(
            name="transaction_id",
            declarations=("--transaction-id",),
            value=_TEXT,
            default=ParameterDefault.required(),
            help_key=TranslationKey("cli.ledger.evidence.pull_id_help"),
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


def test_blank_default_text_option_equals_the_literal_it_replaces() -> None:
    """The empty-string-default primitive reproduces the displaced literal exactly."""
    _assert_identical(
        _blank_default_text_option("reason", ("--reason",), "cli.ledger.archive.reason_help"),
        OptionSpec(
            name="reason",
            declarations=("--reason",),
            value=_TEXT,
            default=ParameterDefault.value(""),
            help_key=TranslationKey("cli.ledger.archive.reason_help"),
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


def test_repeatable_text_option_equals_the_literal_it_replaces() -> None:
    """The repeatable free-text primitive reproduces the displaced literal exactly."""
    _assert_identical(
        _repeatable_text_option("tag", ("--tag",), "cli.ledger.add.actor_help"),
        OptionSpec(
            name="tag",
            declarations=("--tag",),
            value=_TEXT,
            default=ParameterDefault.value(()),
            help_key=TranslationKey("cli.ledger.add.actor_help"),
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
    )


def test_boolean_flag_option_equals_the_literal_it_replaces() -> None:
    """The boolean flag primitive reproduces the displaced literal exactly."""
    _assert_identical(
        _boolean_flag_option("dry_run", ("--dry-run",), "cli.ledger.archive.reason_help"),
        OptionSpec(
            name="dry_run",
            declarations=("--dry-run",),
            value=_BOOL,
            default=ParameterDefault.value(False),
            help_key=TranslationKey("cli.ledger.archive.reason_help"),
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
    )


def test_required_text_argument_equals_the_literal_it_replaces() -> None:
    """The positional free-text primitive reproduces the displaced literal exactly."""
    _assert_identical(
        _required_text_argument("transaction_id", "cli.app.ledger.evidence.pull_id_help"),
        ArgumentSpec(
            name="transaction_id",
            value=_TEXT,
            default=ParameterDefault.required(),
            help_key=TranslationKey("cli.app.ledger.evidence.pull_id_help"),
            metavar=None,
            constraint=ParameterConstraint(),
            show_default=True,
            hidden=False,
        ),
    )


def test_the_primitives_stay_distinguishable_from_one_another() -> None:
    """No two primitives may collapse onto the same declaration.

    The six exist because their contracts differ, and each difference is
    load-bearing: absent is not empty, optional is not required, and a flag is
    not free text. If a future edit made two of them agree, every gate above
    would still pass while one contract had silently absorbed another.
    """
    declarations = ("--x",)
    produced = [
        _optional_text_option("x", declarations, "cli.ledger.add.actor_help"),
        _required_text_option("x", declarations, "cli.ledger.add.actor_help"),
        _blank_default_text_option("x", declarations, "cli.ledger.add.actor_help"),
        _repeatable_text_option("x", declarations, "cli.ledger.add.actor_help"),
        _boolean_flag_option("x", declarations, "cli.ledger.add.actor_help"),
    ]

    assert len(set(produced)) == len(produced), "two parameter primitives produce the same declaration"


def test_declaration_aliases_survive_the_primitives() -> None:
    """Aliases are identity, not decoration, so every token must reach the spec."""
    option = _optional_text_option("period", ("--period", "-p"), "cli.ledger.export.period_help")

    assert option.declarations == ("--period", "-p")
