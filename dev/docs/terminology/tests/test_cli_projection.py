"""Real-behaviour conformance for the CLI-surface search-record emitter (ADR D4).

The emitter walks the LIVE materialised ``aeat`` command tree (the same
``typer.main.get_command(app)`` house walk the CLI reference generator uses)
four times, once per output language, and projects one
:class:`~dev.docs.terminology._cli_projection.CliSurfaceRecord` per leaf
command plus one
:class:`~dev.docs.terminology._cli_projection.CliOptionRecord` per option.
These gates assert the projection covers the live tree exactly (count parity
against the independent house walk), carries four-language help, and that
every target anchor resolves to the CLI-reference page shape.

No mocks: the tree walk is real (it spawns the actual CLI), the anchor oracle
is ``docutils.nodes.make_id`` (the same slugger Sphinx uses to build the
section ids in the generated CLI pages), so the gates are independent of the
emitter's own slug logic.
"""

from __future__ import annotations

import pytest
from docutils.nodes import make_id

from aeat.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, OutputLanguage
from dev.docs.terminology._cli_projection import CliOptionRecord, CliProjectionStats, CliSurfaceRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.docs]

_FOUR_LANGUAGES = frozenset(OutputLanguage(code) for code in SUPPORTED_OUTPUT_LANGUAGES)


@pytest.fixture(scope="module")
def projection() -> tuple[tuple[CliSurfaceRecord, ...], tuple[CliOptionRecord, ...], CliProjectionStats]:
    """Project the live CLI tree once for the whole module (4 subprocess walks)."""
    from dev.docs.terminology._cli_projection import project_cli_search_records

    return project_cli_search_records()


@pytest.fixture(scope="module")
def live_leaf_keys() -> set[str]:
    """The live leaf-command registry keys, from the independent house walk."""
    from dev.docs.cli_reference import collect_live_leaf_paths_in_subprocess

    return set(collect_live_leaf_paths_in_subprocess())


def test_command_records_cover_the_live_leaf_set(
    projection: tuple[tuple[CliSurfaceRecord, ...], tuple[CliOptionRecord, ...], CliProjectionStats],
    live_leaf_keys: set[str],
) -> None:
    """One command record per live leaf -- exact parity with the house walk.

    The emitter's command inventory (its ``registry_key`` set) must equal the
    independently-collected live leaf set. A surplus record means the emitter
    invented a command; a missing record means it dropped one.
    """
    commands, _options, _stats = projection
    emitted_keys = {record.registry_key for record in commands}

    assert emitted_keys == live_leaf_keys, (
        "CLI command records diverge from the live leaf set:\n"
        f"  missing from emitter: {sorted(live_leaf_keys - emitted_keys)}\n"
        f"  surplus in emitter:   {sorted(emitted_keys - live_leaf_keys)}"
    )
    # No duplicate command records (parity above already implies it, but make
    # the no-duplication invariant explicit).
    assert len(commands) == len(emitted_keys)


def test_every_command_record_carries_a_spanish_description(
    projection: tuple[tuple[CliSurfaceRecord, ...], tuple[CliOptionRecord, ...], CliProjectionStats],
) -> None:
    """Spanish is the invariant: every command record carries an ``es`` help string.

    The other three languages are present only where the help text is
    genuinely translated (a non-Spanish string identical to the Spanish is
    omitted as untranslated), so the contract is ``es`` always plus any
    distinct translations.
    """
    commands, _options, _stats = projection
    for record in commands:
        descriptions = record.descriptions
        assert OutputLanguage.ES in descriptions, f"{record.command_path}: no es description"
        assert set(descriptions).issubset(_FOUR_LANGUAGES)
        assert descriptions[OutputLanguage.ES].strip()


def test_prorrata_relevant_command_is_fully_translated(
    projection: tuple[tuple[CliSurfaceRecord, ...], tuple[CliOptionRecord, ...], CliProjectionStats],
) -> None:
    """A core command (``aeat app ledger add``) carries all four languages.

    Documents the translated-help expectation with a concrete, stable
    command whose help is curated in every locale -- the four-language
    coverage a palette card relies on.
    """
    commands, _options, _stats = projection
    add = next(
        (r for r in commands if r.command_path == "aeat app ledger add"),
        None,
    )
    assert add is not None, "expected the stable 'aeat app ledger add' command in the projection"
    assert set(add.descriptions) == _FOUR_LANGUAGES, (
        f"'aeat app ledger add' missing translations: {_FOUR_LANGUAGES - set(add.descriptions)}"
    )


def test_every_target_anchor_resolves_to_the_cli_reference_shape(
    projection: tuple[tuple[CliSurfaceRecord, ...], tuple[CliOptionRecord, ...], CliProjectionStats],
) -> None:
    """Every command target is ``cli/<family>.html#<docutils-slug-of-path>``.

    The anchor is verified against ``docutils.nodes.make_id`` -- the slugger
    Sphinx itself uses to build the section ids in the generated CLI-reference
    pages -- so a target either matches the real built anchor or fails. This
    is the non-tautological proof: the oracle is independent of the emitter's
    slug code.
    """
    commands, _options, _stats = projection
    for record in commands:
        expected_anchor = make_id(record.command_path)
        expected_target = f"cli/{record.family}.html#{expected_anchor}"
        assert record.target == expected_target, (
            f"{record.command_path}: target {record.target!r} != expected {expected_target!r}"
        )
        assert record.family in {"app", "config"}


def test_option_records_attach_to_their_command_and_carry_help(
    projection: tuple[tuple[CliSurfaceRecord, ...], tuple[CliOptionRecord, ...], CliProjectionStats],
) -> None:
    """Every option record names its command, shares its target, and has es help.

    The option's ``target`` must equal its owning command's target (options
    render inside the command section), every option carries at least one
    surface name and a Spanish description, and the language set stays within
    the four supported languages.
    """
    commands, options, _stats = projection
    command_target = {r.command_path: r.target for r in commands}

    assert options, "expected option records for a CLI with parameterised commands"
    for option in options:
        assert option.command_path in command_target, (
            f"option {option.option_names} attaches to unknown command {option.command_path!r}"
        )
        assert option.target == command_target[option.command_path]
        assert option.option_names, f"{option.command_path}: option with no surface name"
        assert OutputLanguage.ES in option.descriptions
        assert set(option.descriptions).issubset(_FOUR_LANGUAGES)


def test_required_amount_option_is_marked_required(
    projection: tuple[tuple[CliSurfaceRecord, ...], tuple[CliOptionRecord, ...], CliProjectionStats],
) -> None:
    """The ``--amount`` option of ``aeat app ledger add`` is a required option.

    A concrete, stable assertion that required/argument flags survive the
    projection (drawn from the live tree, not hand-asserted shape).
    """
    _commands, options, _stats = projection
    amount = next(
        (o for o in options if o.command_path == "aeat app ledger add" and "--amount" in o.option_names),
        None,
    )
    assert amount is not None, "expected the --amount option on 'aeat app ledger add'"
    assert amount.required is True
    assert amount.is_argument is False


def test_records_are_frozen(
    projection: tuple[tuple[CliSurfaceRecord, ...], tuple[CliOptionRecord, ...], CliProjectionStats],
) -> None:
    """The strict-frozen contract: a projected record rejects mutation."""
    from pydantic import ValidationError

    commands, options, _stats = projection
    with pytest.raises(ValidationError):
        commands[0].family = "mutated"  # type: ignore[attr-defined,misc]
    with pytest.raises(ValidationError):
        options[0].required = True  # type: ignore[attr-defined,misc]
