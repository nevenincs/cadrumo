"""Only actual machine syntax is removed from the spelling surface."""

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.ledger.models import BULK_CLASSIFY_ALLOWED_COLUMNS
from cadrumo.application.modelo.local_observation_spreadsheet import parse_casilla_value_spreadsheet
from cadrumo.core.click_context import argv_requests_json
from cadrumo.domain.contribuyente.ccaa import CCAA
from cadrumo.domain.iva.prorrata import InputClassification
from cadrumo.domain.modelos.calculation_revision_amendment import M303RectificativaMotive
from cadrumo.entrypoints.cli.command_operation_table import COMMAND_OPERATION_ROWS
from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH
from cadrumo.entrypoints.tui.modelo.workbench.editor import CasillaEditorPanel
from cadrumo_client.commands.parameters import OptionSpec

from ..signal_command_paths import registered_operation_id_pattern
from ..signal_spelling_segments import translation_spelling_segments
from ..signal_tokens import _M303_MOTIVES_RE, _PRORRATA_INPUT_CHOICES_RE, _filter_rich_styles, filtered_translation_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("syntax", "misspelling"),
    [
        ("casilla_code,value", "casilla_code,valuu"),
        ("transaction_id, classification", "transaction_id, classificatioon"),
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


def test_bulk_headers_and_m303_motives_follow_their_source_contracts() -> None:
    assert {"transaction_id", "classification"} <= BULK_CLASSIFY_ALLOWED_COLUMNS
    correct = "rectificaciones or discrepancia_criterio_administrativo"
    assert {member.value for member in M303RectificativaMotive} == {
        "rectificaciones",
        "discrepancia_criterio_administrativo",
    }
    assert _M303_MOTIVES_RE.fullmatch(correct)
    assert not _M303_MOTIVES_RE.fullmatch(correct.replace("rectificaciones", "rectificacioness"))


@pytest.mark.usefixtures("operation")
def test_prorrata_choices_keep_glosses_and_admit_only_the_complete_source_list() -> None:
    choices = ("exclusively_deductible", "exclusively_non_deductible", "common")
    assert all(str(InputClassification.from_registry(value)) == value for value in choices)
    value = "exclusively_deductible first; exclusively_non_deductible typoedgloss; common proportion"
    filtered, _ = filtered_translation_text(value)
    assert "typoedgloss" in filtered and "proportion" in filtered and "common" not in filtered
    assert not _PRORRATA_INPUT_CHOICES_RE.search(value.replace("common", "commonn"))


def test_rich_style_keeps_visible_text_and_rejects_invalid_style_names() -> None:
    assert _filter_rich_styles("[blue]definitelywrong[/]") == ("definitelywrong", 1)
    assert _filter_rich_styles("[bluuue]definitelywrong[/]") == ("[bluuue]definitelywrong[/]", 0)
    assert filtered_translation_text("[blue]definitelywrong[/]")[0] == "definitelywrong"
    assert "bluuue" in filtered_translation_text("[bluuue]definitelywrong[/]")[0]
    assert "definitelywrong" in filtered_translation_text("[bluuue]definitelywrong[/]")[0]


def test_only_real_complete_operation_names_protect_their_span() -> None:
    pattern = registered_operation_id_pattern()
    assert any(operation == "modelo.requires" for _path, operation in COMMAND_OPERATION_ROWS)
    assert pattern.fullmatch("modelo.requires")
    assert not pattern.fullmatch("modelo.requirez")
    assert not pattern.search("modelo.requires_typo")
    assert not pattern.search("modelo.requires.typo")
    assert not pattern.search("modelo.requires..typo")
    assert pattern.search("modelo.requires. Next sentence") is not None
    correct = translation_spelling_segments("modelo.requires definitelywrong", "example", "ca")
    terminal = translation_spelling_segments("modelo.requires. definitelywrong", "example", "ca")
    wrong = translation_spelling_segments("modelo.requirez definitelywrong", "example", "ca")
    assert any("definitelywrong" in words for _language, words, _excluded in correct)
    assert any("definitelywrong" in words for _language, words, _excluded in terminal)
    assert not any("requires" in words for _language, words, _excluded in terminal)
    assert any("requirez" in words for _language, words, _excluded in wrong)


def test_keyboard_notation_matches_real_bindings_and_keeps_the_key_or_action() -> None:
    bindings = {binding.key for binding in CasillaEditorPanel.BINDINGS}
    assert {"escape", "ctrl+enter"} <= bindings
    assert filtered_translation_text("Ctrl+⏎ {save} definitelywrong")[0] == "⏎ definitelywrong"
    assert "kattintás" in filtered_translation_text("Ctrl+kattintás definitelywrong")[0]
    assert "Ctrll" in filtered_translation_text("Ctrll+⏎ {save} definitelywrong")[0]
