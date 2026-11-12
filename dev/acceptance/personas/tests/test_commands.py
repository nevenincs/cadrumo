"""The persona journey's CLI arguments, checked against the live command graph and the catalogue."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.entrypoints.tests.persona_materialisation import patch_answers
from cadrumo.tests.personas import FieldValue

from .. import commands
from .catalogue_support import envelope, persona

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


#: A verb the live graph does not hold, named outside the argv literal so the harness argv gate, which checks every
#: literal argv against the live CLI, does not read the deliberately dead path as a harness command.
_ABSENT_VERB = "no-such-verb"


def _option_names(args: tuple[str, ...]) -> list[str]:
    return [token for token in args if token.startswith("--")]


def test_every_command_the_journey_runs_is_an_executable_leaf_of_the_live_graph() -> None:
    paths = (
        commands.PROFILE_EDIT,
        commands.DESCENDANT_ADD,
        ("app", "ledger", "classify"),
        ("app", "ledger", "invoice", "add"),
        ("app", "ledger", "retencion-soportada", "record"),
        ("app", "modelo", "aggregate"),
        ("app", "modelo", "work", "attest-m303-exonerado-390"),
        ("app", "modelo", "iva-wallet", "seed"),
        ("app", "modelo", "filing-record", "observe-local"),
        ("app", "ledger", "inventory", "create"),
    )
    assert all(commands.command_exists(path) for path in paths)
    assert not commands.command_exists(("app", "ledger", _ABSENT_VERB))


def test_profile_answers_render_flags_lists_and_values_the_edit_declares() -> None:
    fontanero = persona("autonomo-fontanero")
    args, missing = commands.profile_edit_arguments(patch_answers(fontanero, envelope()), fontanero.fields)
    declared = commands.declared_options(commands.PROFILE_EDIT)
    assert args[: len(commands.PROFILE_EDIT)] == commands.PROFILE_EDIT
    assert all(name in declared for name in _option_names(args))
    assert not missing


def test_an_undeclared_answer_is_a_missing_route_not_an_option() -> None:
    args, missing = commands.profile_edit_arguments((("no-such-question", "x"),), ())
    assert "--no-such-question" not in args
    assert [route.step for route in missing] == ["profile.no-such-question"]


def test_a_boolean_answer_on_a_flag_option_becomes_its_positive_or_negative_spelling() -> None:
    yes, _ = commands.profile_edit_arguments((("has-employees", "true"),), ())
    no, _ = commands.profile_edit_arguments((("has-employees", "false"),), ())
    assert "--has-employees" in yes
    assert "--no-has-employees" in no


def test_a_field_with_no_command_is_a_missing_route() -> None:
    routed = commands.field_arguments(FieldValue(path="identity.email", value="a@example.invalid"))
    assert isinstance(routed, commands.MissingRoute)
    assert routed.step == "fields.identity.email"


def test_a_stated_empty_descendant_family_is_a_gap_and_runs_no_command() -> None:
    fontanero = persona("autonomo-fontanero")
    rendered, missing = commands.household_arguments(fontanero, envelope())
    assert "descendants" in fontanero.household_families
    assert not fontanero.descendants
    assert rendered == ()
    assert {route.step for route in missing} >= {"household.descendants"}


def test_a_descendant_row_names_only_flag_keys_the_add_command_takes() -> None:
    asalariada = persona("asalariada-familia")
    rendered, _ = commands.household_arguments(asalariada, envelope())
    flags = [rendered[0][index + 1] for index, argument in enumerate(rendered[0]) if argument == "--descendiente"]
    assert len(flags) == len(asalariada.descendants)
    keys = {part.split("=", 1)[0] for flag in flags for part in flag.split(",")}
    assert keys <= set(commands.DESCENDANT_FLAG_KEYS.values())


def test_classification_uses_only_declared_classify_options() -> None:
    fontanero = persona("autonomo-fontanero")
    declared = commands.declared_options(("app", "ledger", "classify"))
    assert not commands.unmapped_classify_fields(fontanero)
    for row in fontanero.ledger:
        args = commands.classify_arguments(fontanero, row, "tx-1", "operator:persona")
        assert args[:4] == ("app", "ledger", "classify", "tx-1")
        assert all(name in declared for name in _option_names(args))


def test_an_invoice_takes_its_rate_as_a_percentage_and_its_retention_rate_as_a_fraction() -> None:
    fontanero = persona("autonomo-fontanero")
    row = next(item for item in fontanero.ledger if item.iva_rate is not None and item.retencion_rate is not None)
    args = commands.invoice_arguments(fontanero, row, envelope())
    assert args is not None
    assert row.iva_rate is not None and row.retencion_rate is not None
    assert Decimal(args[args.index("--iva-rate") + 1]) == row.iva_rate * 100
    assert Decimal(args[args.index("--retention-rate") + 1]) == row.retencion_rate
    declared = commands.declared_options(("app", "ledger", "invoice", "add"))
    assert all(name in declared for name in _option_names(args))


def test_rows_correlate_by_date_magnitude_direction_and_concept_and_ambiguity_stays_unmatched() -> None:
    fontanero = persona("autonomo-fontanero")
    first, second = fontanero.ledger[0], fontanero.ledger[1]
    day, amount, direction, concept = commands.statement_key(first, envelope())
    listed = [
        {"transaction_id": "t-1", "date": day, "amount": str(amount), "direction": direction, "description": concept}
    ]
    mapped, unmatched = commands.correlate_rows((first, second), listed, envelope())
    assert mapped == {first.ref: "t-1"}
    assert unmatched == (second.ref,)
    doubled, ambiguous = commands.correlate_rows(
        (first,), [*listed, {**listed[0], "transaction_id": "t-2"}], envelope()
    )
    assert doubled == {}
    assert ambiguous == (first.ref,)


def test_a_fourth_quarter_303_calculates_with_its_attestation_and_no_joint_return() -> None:
    args = commands.calculate_arguments("wu-1", modelo="303", attestation=("att-1", "f" * 64), actor="operator:x")
    assert "--no-joint-return-elected" in args
    assert args[args.index("--m303-exonerado-390-attachment-id") + 1] == "att-1"
    other = commands.calculate_arguments("wu-1", modelo="130", attestation=None, actor="operator:x")
    assert "--no-joint-return-elected" not in other
