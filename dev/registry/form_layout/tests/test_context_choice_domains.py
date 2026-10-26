"""Context labels require exact declared header domains, without code guessing."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.form_context import form_context_choice, resolve_form_context_field
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock

from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _source():
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/353")).revisions["2026-desde-02"]
    block = next(
        block
        for page in revision.form_layouts[0].pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormContextFieldBlock) and block.id == "avanzado"
    )
    return revision, block


@pytest.mark.parametrize("value,heading", [("1", "Sí"), ("2", "No"), (1, "Sí"), (2, "No")])
def test_declared_codes_select_their_human_meaning(value: str | int, heading: str) -> None:
    revision, block = _source()
    resolve_form_context_field(revision, block)
    choice = form_context_choice(block, value)
    assert choice is not None and choice.official_heading == heading


@pytest.mark.parametrize("value", ["", "0", "3", "01", True, False])
def test_unexpected_values_are_not_silently_coerced(value: object) -> None:
    _, block = _source()
    with pytest.raises(RegistryValidationError, match="outside"):
        form_context_choice(block, value)


def test_absence_is_not_a_negative_answer() -> None:
    _, block = _source()
    assert form_context_choice(block, None) is None


def test_incomplete_choice_domain_is_refused() -> None:
    revision, block = _source()
    with pytest.raises(RegistryValidationError, match="exact closed domain"):
        resolve_form_context_field(revision, block.model_copy(update={"choices": block.choices[:1]}))


def test_duplicate_choice_codes_are_refused() -> None:
    _, block = _source()
    with pytest.raises((ValidationError, RegistryValidationError), match="duplicate"):
        FormContextFieldBlock.model_validate({**block.model_dump(), "choices": (block.choices[0],) * 2})
