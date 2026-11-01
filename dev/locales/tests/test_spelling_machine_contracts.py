"""Only actual machine syntax is removed from the spelling surface."""

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.modelo.local_observation_spreadsheet import parse_casilla_value_spreadsheet
from cadrumo.core.click_context import argv_requests_json
from cadrumo.domain.contribuyente.ccaa import CCAA
from cadrumo.entrypoints.cli.command_operation_table import COMMAND_OPERATION_ROWS
from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH
from cadrumo.entrypoints.tui.modelo.workbench.editor import CasillaEditorPanel
from cadrumo_client.commands.parameters import OptionSpec

from ..signal_command_paths import registered_operation_id_pattern
from ..signal_spelling_segments import translation_spelling_segments
from ..signal_tokens import filtered_translation_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("syntax", "misspelling"),
    [
        ("casilla_code,value", "casilla_code,valuu"),
        ("--format json", "--format jsno"),
        ("--tax-residence-ccaa madrid", "--tax-residence-ccaa madridd"),
        ("cataluna, comunidad-valenciana", "cataluna, comunidad-valencianaa"),
        ("Esc {back}", "Esc {wrong}"),
    ],
)
def test_complete_syntax_keeps_neighbouring_errors_visible(syntax: str, misspelling: str) -> None:
    actual, _ = filtered_translation_text(f"{syntax} definitelywrong")
    invalid, _ = filtered_translation_text(f"{misspelling} definitelywrong")
    assert "definitelywrong" in actual and "definitelywrong" in invalid
    assert len(actual) < len(invalid)


def test_csv_header_is_the_actual_spreadsheet_input(tmp_path: Path) -> None:
    path = tmp_path / "values.csv"
    path.write_text("casilla_code,value\n01,42.50\n", encoding="utf-8")
    assert parse_casilla_value_spreadsheet(path) == {"01": Decimal("42.50")}


@pytest.mark.usefixtures("operation")
def test_residence_examples_are_accepted_profile_values() -> None:
    create = next(node for node in COMMAND_GRAPH.nodes() if node.path == ("aeat", "config", "profile", "create"))
    assert any(
        isinstance(parameter, OptionSpec) and "--tax-residence-ccaa" in parameter.declarations
        for parameter in create.spec.parameters
    )
    assert CCAA.from_label("madrid") == CCAA.MADRID
    assert CCAA.from_label("cataluna") == CCAA.CATALUNA
    assert CCAA.from_label("comunidad-valenciana") == CCAA.COMUNIDAD_VALENCIANA


def test_json_example_is_the_real_option_and_not_a_misspelling() -> None:
    assert argv_requests_json(["--format", "json"])
    assert argv_requests_json(["--format=json"])
    assert not argv_requests_json(["--format", "jsno"])


def test_only_real_complete_operation_names_protect_their_span() -> None:
    pattern = registered_operation_id_pattern()
    assert any(operation == "modelo.requires" for _path, operation in COMMAND_OPERATION_ROWS)
    assert pattern.fullmatch("modelo.requires")
    assert not pattern.fullmatch("modelo.requirez")
    assert not pattern.search("modelo.requires_typo")
    correct = translation_spelling_segments("modelo.requires definitelywrong", "example", "ca")
    wrong = translation_spelling_segments("modelo.requirez definitelywrong", "example", "ca")
    assert any("definitelywrong" in words for _language, words, _excluded in correct)
    assert any("requirez" in words for _language, words, _excluded in wrong)


def test_keyboard_notation_matches_real_bindings_and_keeps_the_key_or_action() -> None:
    bindings = {binding.key for binding in CasillaEditorPanel.BINDINGS}
    assert {"escape", "ctrl+enter"} <= bindings
    assert filtered_translation_text("Ctrl+⏎ {save} definitelywrong")[0] == "⏎ definitelywrong"
    assert "kattintás" in filtered_translation_text("Ctrl+kattintás definitelywrong")[0]
    assert "Ctrll" in filtered_translation_text("Ctrll+⏎ {save} definitelywrong")[0]
