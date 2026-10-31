"""The Renta profile vocabularies read their codes from the fact the record design grounds.

Every expected code is read out of the bundled Modelo 100 XSD, so a transcription error
in the fact surfaces as a mismatch instead of being asserted back at itself.
"""

from __future__ import annotations

import re
from xml.etree.ElementTree import Element

import pytest
from defusedxml import ElementTree as DefusedElementTree

from ....core.directory_scan import scan_directory
from ....core.resources.bundled_data import bundled_path
from ...calculations.registry.descendant_disability_catalogue import accepted_descendant_disability_grades
from ...calculations.registry.form_codes import resolve_form_codes
from ..descendant import DescendantInfo
from ..renta_codes import (
    RentaDeclaracionType,
    RentaDisabilityGrade,
    RentaMaritalStatus,
    RentaSexCode,
    modelo100_ecivil_export_code,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_XS = "{http://www.w3.org/2001/XMLSchema}"
_M100_FILES = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_100", "files")


def _xsd_simple_type(type_name: str) -> Element:
    """Return a simpleType of the newest bundled Modelo 100 XSD."""
    newest = sorted(entry for entry in scan_directory(_M100_FILES) if entry.name.endswith(".xsd"))[0]
    root = DefusedElementTree.parse(newest).getroot()
    assert root is not None
    for simple_type in root.iter(f"{_XS}simpleType"):
        if simple_type.get("name") == type_name:
            return simple_type
    raise AssertionError(f"the bundled Modelo 100 XSD declares no {type_name}")


def _xsd_enumeration(type_name: str) -> frozenset[str]:
    return frozenset(str(item.get("value")) for item in _xsd_simple_type(type_name).iter(f"{_XS}enumeration"))


def _xsd_documented_codes(type_name: str) -> frozenset[str]:
    """Return the codes of a type the design documents as ``code = name`` and bounds by a pattern."""
    documentation = "".join(_xsd_simple_type(type_name).itertext())
    return frozenset(str(match.group(1)) for match in re.finditer(r"(\d+)\s*=", documentation))


@pytest.mark.usefixtures("operation")
@pytest.mark.parametrize(
    ("vocabulary", "type_name"),
    [
        (RentaSexCode, "tipo_Sexo"),
        (RentaDisabilityGrade, "tipo_GradoDiscapacidad"),
    ],
)
def test_a_vocabulary_declares_the_codes_of_its_record_design_type(
    vocabulary: type[RentaSexCode] | type[RentaDisabilityGrade],
    type_name: str,
) -> None:
    assert set(vocabulary.form_codes().values()) == _xsd_enumeration(type_name)


@pytest.mark.usefixtures("operation")
def test_the_export_members_are_the_codes_the_record_design_accepts() -> None:
    declared = resolve_form_codes("modelo-100-profile-form-codes")
    exported = {
        declared.code(f"marital_status.{member}") for member in declared.ordered_codes("marital_status_export.members")
    }

    assert exported == _xsd_documented_codes("tipo_EstadoCivil")
    for code in exported:
        assert modelo100_ecivil_export_code(code) == code


@pytest.mark.usefixtures("operation")
def test_the_profile_only_partnership_marker_is_refused_on_export() -> None:
    with pytest.raises(ValueError, match="profile-only pareja de hecho"):
        modelo100_ecivil_export_code(RentaMaritalStatus.PAREJA_HECHO.code)
    with pytest.raises(ValueError, match="must be one of"):
        modelo100_ecivil_export_code("not-a-code")


@pytest.mark.usefixtures("operation")
def test_a_stored_answer_reads_as_the_member_it_declares() -> None:
    for member, code in RentaDeclaracionType.form_codes().items():
        assert RentaDeclaracionType.from_code(code) is member
    with pytest.raises(ValueError, match="not a RentaDeclaracionType code"):
        RentaDeclaracionType.from_code("joint")


@pytest.mark.usefixtures("operation")
def test_a_descendant_grade_is_held_to_the_governed_catalogue() -> None:
    accepted = accepted_descendant_disability_grades()
    assert accepted, "the governed catalogue declares no grade"
    grade = max(accepted)

    assert DescendantInfo(birth_date="2020-01-01", discapacidad_grado=grade).discapacidad_grado == grade
    with pytest.raises(ValueError, match="grade the governed catalogue accepts"):
        DescendantInfo(birth_date="2020-01-01", discapacidad_grado=grade + 1)
