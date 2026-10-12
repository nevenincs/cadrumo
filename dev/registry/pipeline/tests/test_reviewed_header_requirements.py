"""A requirement a non-design official source states reaches the layout only cited and quoted.

Modelo 111's record design prints no Validación column, so the generator read
every identifying field as optional and the export wrote a return with no
declarant name. The instructions state the requirement instead. These tests
hold the reviewed requirement to its contract: it is cited, quoted from the
exact reviewed bytes, never a second spelling of a design requirement, and
it is what makes the generated field refuse a blank.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

from ..export_field_schema import _combined_requirement
from ..joined_record_design import JoinedRecordDesign, JoinedRecordDesignField, join_record_design_semantics
from ..record_design_intermediate import load_record_design_intermediate
from ..semantic_map import SemanticMap, SemanticMapEntry, SemanticMapRequirement, load_semantic_map
from ..semantic_map_validation import verify_requirement_statements
from ._generated_tree_test_support import bundled_revision_inspection

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MAPPINGS = Path(__file__).resolve().parents[2] / "mappings" / "modelo_111" / "2019"
_INSTRUCTIONS = "aeat-modelo-111-instructions"
_DESIGN = "aeat-dr-111-2019-v18"
_IDENTIFICATION = (
    "Introduzca el NIF del declarante y los apellidos y nombre o bien la razón social de la persona o entidad."
)


def _inspection() -> RegistryRevisionInspection:
    return bundled_revision_inspection("111", "2019-y-siguientes")


@cache
def _semantic_map() -> SemanticMap:
    return load_semantic_map(_MAPPINGS)


@cache
def _joined(semantic_map: SemanticMap | None = None) -> JoinedRecordDesign:
    inspection = _inspection()
    intermediate = load_record_design_intermediate(
        bundled_path(),
        inspection.sources,
        source_ref=_DESIGN,
        filing_year=2026,
        design_epoch="2019",
    )
    return join_record_design_semantics(semantic_map or _semantic_map(), intermediate, inspection)


def _field(export_field_id: str) -> JoinedRecordDesignField:
    return next(field for field in _joined().fields if field.semantic_entry.export_field_id == export_field_id)


def _with_requirement(entry: SemanticMapEntry, **changes: object) -> SemanticMapEntry:
    assert entry.requirement is not None
    return entry.model_copy(update={"requirement": entry.requirement.model_copy(update=changes)})


def _map_with_entry(replacement: SemanticMapEntry) -> SemanticMap:
    semantic_map = _semantic_map()
    entries = tuple(
        replacement if entry.export_field_id == replacement.export_field_id else entry for entry in semantic_map.entries
    )
    return semantic_map.model_copy(update={"entries": entries})


def _apellidos_entry() -> SemanticMapEntry:
    return next(entry for entry in _semantic_map().entries if entry.export_field_id == "modelo-111-page-01-apellidos")


def test_modelo_111_identifying_fields_carry_the_instructions_requirement() -> None:
    """NIF, apellidos o razón social, ejercicio and periodo are required; nombre only for a person."""
    requirements = {
        str(entry.export_field_id): entry.requirement.applies_to
        for entry in _semantic_map().entries
        if entry.requirement is not None
    }

    assert requirements == {
        "modelo-111-page-01-nif": "all_taxpayers",
        "modelo-111-page-01-apellidos": "all_taxpayers",
        "modelo-111-page-01-nombre": "natural_person",
        "modelo-111-page-01-ejercicio": "all_taxpayers",
        "modelo-111-page-01-periodo": "all_taxpayers",
    }
    assert "modelo-111-page-01-tipo-declaracion" not in requirements


def test_a_reviewed_requirement_fills_the_design_silence_it_cites() -> None:
    """The design states nothing for these slots, so the reviewed requirement decides them."""
    assert _field("modelo-111-page-01-apellidos").parser_field.validation is None
    assert _combined_requirement(_field("modelo-111-page-01-apellidos"), design_required=False) == (True, None)
    assert _combined_requirement(_field("modelo-111-page-01-ejercicio"), design_required=False) == (True, None)
    assert _combined_requirement(_field("modelo-111-page-01-nombre"), design_required=False) == (
        False,
        "natural_person",
    )
    assert _combined_requirement(_field("modelo-111-page-01-tipo-declaracion"), design_required=False) == (
        False,
        None,
    )


@pytest.mark.parametrize("validation", ["Obligatorio", "OBLIGATORIO (persona fisica)"])
def test_a_reviewed_requirement_restating_the_design_refuses(validation: str) -> None:
    """The design's own Validación is the requirement; a second spelling of it is refused."""
    field = _field("modelo-111-page-01-apellidos")
    restated = field.model_copy(
        update={"parser_field": field.parser_field.model_copy(update={"validation": validation})}
    )

    with pytest.raises(RegistryValidationError, match="design already states one"):
        _combined_requirement(restated, design_required=validation == "Obligatorio")


def test_every_modelo_111_quotation_is_found_in_the_cited_instructions() -> None:
    inspection = _inspection()

    verify_requirement_statements(_semantic_map(), source_root=bundled_path(), sources=inspection.sources)


def test_a_quotation_the_source_does_not_contain_refuses() -> None:
    """Positive control: an invented sentence is not a citation."""
    inspection = _inspection()
    invented = _with_requirement(_apellidos_entry(), statement="Los apellidos son opcionales.")

    with pytest.raises(RegistryValidationError, match="does not contain"):
        verify_requirement_statements(_map_with_entry(invented), source_root=bundled_path(), sources=inspection.sources)


def test_a_requirement_citing_the_record_design_refuses() -> None:
    """The design states requirements in its Validación column, which the generator already reads."""
    design_sha = _semantic_map().source_sha256
    entry = _with_requirement(_apellidos_entry(), source_ref=_DESIGN, source_sha256=design_sha)

    with pytest.raises(RegistryValidationError, match="cites the record design"):
        _joined(_map_with_entry(entry))


def test_a_requirement_reviewed_against_other_bytes_refuses() -> None:
    entry = _with_requirement(_apellidos_entry(), source_sha256="0" * 64)

    with pytest.raises(RegistryValidationError, match="review the quotation against the new bytes"):
        _joined(_map_with_entry(entry))


def _load_edited(tmp_path: Path, old: str, new: str) -> SemanticMap:
    """Load the real Modelo 111 map with one exact edit to its page fragment."""
    fragment = (_MAPPINGS / "0002-page-01.toml").read_text(encoding="utf-8")
    assert fragment.count(old) == 1, old
    (tmp_path / "0001-records.toml").write_text(
        (_MAPPINGS / "0001-records.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "0002-page-01.toml").write_text(fragment.replace(old, new), encoding="utf-8")
    return load_semantic_map(tmp_path)


def test_an_uncited_requirement_refuses_when_the_map_loads(tmp_path: Path) -> None:
    """Positive control: a requirement whose source the field does not cite never reaches a layout."""
    old = (
        'source_refs = ["aeat-dr-111-2019-v18", "aeat-modelo-111-instructions"]\nproducer_key = "taxpayer.given_name"\n'
    )
    new = 'source_refs = ["aeat-dr-111-2019-v18"]\nproducer_key = "taxpayer.given_name"\n'

    with pytest.raises(RegistryValidationError, match="not among its source_refs"):
        _load_edited(tmp_path, old, new)


def test_a_requirement_with_no_source_cannot_be_declared() -> None:
    with pytest.raises(ValueError, match="source_ref"):
        SemanticMapRequirement.model_validate(
            {"applies_to": "all_taxpayers", "source_sha256": "0" * 64, "statement": _IDENTIFICATION}
        )


def test_a_requirement_refuses_on_a_field_whose_requirement_has_another_owner(tmp_path: Path) -> None:
    """A casilla's requirement comes from its design and block anchor, not a reviewed quotation."""
    old = 'source_refs = ["aeat-dr-111-2019-v18"]\ncasilla_id = "01"\n'
    new = (
        f'source_refs = ["aeat-dr-111-2019-v18", "{_INSTRUCTIONS}"]\ncasilla_id = "01"\n\n'
        "[entries.requirement]\n"
        'applies_to = "all_taxpayers"\n'
        f'source_ref = "{_INSTRUCTIONS}"\n'
        f'source_sha256 = "{"0" * 64}"\n'
        f'statement = "{_IDENTIFICATION}"\n'
    )

    with pytest.raises(RegistryValidationError, match="header or draft field"):
        _load_edited(tmp_path, old, new)


def test_a_natural_person_requirement_refuses_on_a_draft_field(tmp_path: Path) -> None:
    old = (
        'applies_to = "all_taxpayers"\n'
        f'source_ref = "{_INSTRUCTIONS}"\n'
        'source_sha256 = "baaabd139e1dcff461b0c9b70e3ceb90d2287001fc8be3abb0a7a219fde6f19e"\n'
        'statement = "Ejercicio:'
    )
    new = old.replace("all_taxpayers", "natural_person")

    with pytest.raises(RegistryValidationError, match="natural-person requirement"):
        _load_edited(tmp_path, old, new)
