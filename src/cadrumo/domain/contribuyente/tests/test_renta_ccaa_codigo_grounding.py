"""Ground the Modelo 100 CCAA código table in the bundled AEAT record-design XSD.

Every número asserted here is read out of the ``tipo_CCAA`` simpleType of the
bundled Modelo 100 XSDs. The test declares only which AEAT *name* denotes each
community; it never restates a código, so a transcription error in the
production table surfaces as a mismatch instead of being asserted back at
itself.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

import pytest
from defusedxml import ElementTree as DefusedElementTree

from ....core.directory_scan import scan_directory
from ....core.resources._boundary import bundled_path
from ..ccaa import CCAA
from ..renta_codes import RENTA_MODELO100_CCAA_CODIGOS, modelo100_ccaa_codigo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_XS = "{http://www.w3.org/2001/XMLSchema}"
_M100_FILES = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_100", "files")
_CODIGO_ENTRY = re.compile(r'"(\d{2})"\s*=\s*([^,\]]+)')

# Which AEAT name denotes each community. This is an identity statement -- that
# "ILLES BALEARS" is the Balearic Islands and "C. VALENCIANA" the Valencian
# Community -- and deliberately carries no números: the códigos come from the
# XSD, so this binding cannot launder a wrong one.
_AEAT_NOMBRE: dict[CCAA, str] = {
    CCAA.ANDALUCIA: "ANDALUCIA",
    CCAA.ARAGON: "ARAGÓN",
    CCAA.ASTURIAS: "ASTURIAS",
    CCAA.BALEARES: "ILLES BALEARS",
    CCAA.CANARIAS: "CANARIAS",
    CCAA.CANTABRIA: "CANTABRIA",
    CCAA.CASTILLA_LA_MANCHA: "CASTILLA Y LA MANCHA",
    CCAA.CASTILLA_Y_LEON: "CASTILLA Y LEÓN",
    CCAA.CATALUNA: "CATALUÑA",
    CCAA.EXTREMADURA: "EXTREMADURA",
    CCAA.GALICIA: "GALICIA",
    CCAA.MADRID: "MADRID",
    CCAA.MURCIA: "REGIÓN DE MURCIA",
    CCAA.LA_RIOJA: "LA RIOJA",
    CCAA.COMUNIDAD_VALENCIANA: "C. VALENCIANA",
}


class _CommunityWithoutCodigo(StrEnum):
    """A community outside :class:`CCAA`'s ordinary common-regime catalogue.

    Ceuta is a real AEAT código (18) that :class:`CCAA` deliberately excludes, so
    this stands in for the case the mapper must refuse: something community-shaped
    that carries no Modelo 100 código reachable from the enum.
    """

    CEUTA = "ceuta"


def _bundled_xsds() -> tuple[Path, ...]:
    """Return every bundled Modelo 100 record-design XSD."""
    return scan_directory(_M100_FILES, pattern="*esquema-xsd*.xsd")


def _tipo_ccaa(xsd: Path) -> tuple[frozenset[str], dict[str, str]]:
    """Return the ``tipo_CCAA`` enumeration and its documented código table.

    The código table is an ``xs:documentation`` annotation inside the same
    simpleType that carries the ``xs:enumeration`` constraining
    ``codigoCADeclaracion``, so the two cannot disagree with each other or with
    AEAT's own validator.
    """
    root = DefusedElementTree.parse(xsd).getroot()
    assert root is not None, f"{xsd.name} parsed to an empty document"
    for simple_type in root.iter(f"{_XS}simpleType"):
        if simple_type.get("name") != "tipo_CCAA":
            continue
        enumeration = frozenset(
            value for node in simple_type.iter(f"{_XS}enumeration") if (value := node.get("value")) is not None
        )
        documented: dict[str, str] = {}
        for node in simple_type.iter(f"{_XS}documentation"):
            for codigo, nombre in _CODIGO_ENTRY.findall(node.text or ""):
                documented[codigo] = nombre.strip()
        return enumeration, documented
    raise AssertionError(f"{xsd.name} declares no tipo_CCAA simpleType")


def _authoritative_table() -> dict[str, str]:
    """Return the código -> nombre table the bundled exercises agree on."""
    _, documented = _tipo_ccaa(
        _M100_FILES / "29-100-esquema-xsd-ejercicio-2024-actualizado-19-01-2026-747-kb-ejecutable.xsd",
    )
    return documented


def test_the_bundled_record_design_xsds_are_readable() -> None:
    """The corpus the rest of this module reads is present and parses.

    Without this, a corpus that failed to resolve would make every grounding
    assertion below pass vacuously over an empty table.
    """
    xsds = _bundled_xsds()

    assert len(xsds) == 6, f"expected six bundled Modelo 100 XSDs, found {[p.name for p in xsds]}"
    for xsd in xsds:
        enumeration, documented = _tipo_ccaa(xsd)
        assert enumeration, f"{xsd.name} declares an empty tipo_CCAA enumeration"
        assert documented, f"{xsd.name} documents no código table"


def test_every_bundled_exercise_declares_the_same_codigo_table() -> None:
    """All six exercises agree, so grounding on one is not a single-revision pin."""
    tables = {xsd.name: _tipo_ccaa(xsd) for xsd in _bundled_xsds()}
    distinct_enumerations = {enumeration for enumeration, _ in tables.values()}
    distinct_documented = {tuple(sorted(documented.items())) for _, documented in tables.values()}

    assert len(distinct_enumerations) == 1, f"tipo_CCAA enumeration diverges across exercises: {tables.keys()}"
    assert len(distinct_documented) == 1, f"tipo_CCAA código table diverges across exercises: {tables.keys()}"


def _mismatches_against_xsd(table: Mapping[CCAA, str], documented: Mapping[str, str]) -> list[str]:
    """Return one message per community whose código differs from AEAT's."""
    nombre_to_codigo = {nombre: codigo for codigo, nombre in documented.items()}
    found: list[str] = []
    for community, nombre in _AEAT_NOMBRE.items():
        assert nombre in nombre_to_codigo, (
            f"AEAT documents no entry named {nombre!r}; documented: {sorted(documented.values())}"
        )
        expected = nombre_to_codigo[nombre]
        actual = table.get(community)
        if actual != expected:
            found.append(f"{community.value}: table says {actual!r}, AEAT assigns {expected!r} to {nombre!r}")
    return found


def test_production_codigos_match_the_xsd_documented_table() -> None:
    """Each community's código equals the one AEAT documents under its name."""
    assert _mismatches_against_xsd(RENTA_MODELO100_CCAA_CODIGOS, _authoritative_table()) == []


def test_the_accessor_and_the_table_agree() -> None:
    """The exported accessor returns exactly what the grounded table holds."""
    for community in CCAA:
        assert modelo100_ccaa_codigo(community) == RENTA_MODELO100_CCAA_CODIGOS[community]


def test_the_grounding_detects_a_swapped_codigo() -> None:
    """Proof the grounding above has teeth rather than passing vacuously.

    Madrid and Murcia are the pair the competing numberings actually confuse --
    Modelo 763 assigns 13 to Madrid where Modelo 100 assigns it to Región de
    Murcia -- so a table carrying that swap must be reported as two mismatches.
    A grounding check that stayed silent here would certify a declaration naming
    the wrong comunidad.
    """
    documented = _authoritative_table()
    swapped = dict(RENTA_MODELO100_CCAA_CODIGOS)
    swapped[CCAA.MADRID], swapped[CCAA.MURCIA] = (
        RENTA_MODELO100_CCAA_CODIGOS[CCAA.MURCIA],
        RENTA_MODELO100_CCAA_CODIGOS[CCAA.MADRID],
    )

    reported = _mismatches_against_xsd(swapped, documented)

    assert len(reported) == 2
    assert any(message.startswith("madrid:") for message in reported)
    assert any(message.startswith("murcia:") for message in reported)


def test_every_ccaa_member_carries_a_codigo() -> None:
    """No community may fall out of the table and export as a default."""
    assert set(RENTA_MODELO100_CCAA_CODIGOS) == set(CCAA)
    assert set(_AEAT_NOMBRE) == set(CCAA)


def test_production_codigos_are_accepted_by_the_xsd_enumeration() -> None:
    """Every exported código passes the constraint AEAT's validator applies."""
    enumeration, _ = _tipo_ccaa(
        _M100_FILES / "29-100-esquema-xsd-ejercicio-2024-actualizado-19-01-2026-747-kb-ejecutable.xsd",
    )

    assert set(RENTA_MODELO100_CCAA_CODIGOS.values()) <= enumeration


def test_codigos_reachable_from_the_enum_exclude_the_non_comunidad_entries() -> None:
    """18, 19 and 20 are AEAT códigos that no :class:`CCAA` member may claim.

    Ceuta and Melilla are autonomous cities and "no residente" is not a comunidad;
    all three are outside the ordinary common-regime catalogue the enum models.
    """
    documented = _authoritative_table()
    exported = set(RENTA_MODELO100_CCAA_CODIGOS.values())

    assert documented["18"] == "CIUDAD DE CEUTA"
    assert documented["19"] == "CIUDAD DE MELILLA"
    assert documented["20"] == "NO RESIDENTE"
    assert exported.isdisjoint({"18", "19", "20"})


def test_codigos_14_and_15_are_assigned_to_nothing() -> None:
    """AEAT's table skips 14 and 15; neither the enumeration nor the docs use them."""
    enumeration, documented = _tipo_ccaa(
        _M100_FILES / "29-100-esquema-xsd-ejercicio-2024-actualizado-19-01-2026-747-kb-ejecutable.xsd",
    )

    assert enumeration.isdisjoint({"14", "15"})
    assert "14" not in documented
    assert "15" not in documented


def test_modelo100_ccaa_codigo_refuses_a_community_with_no_codigo() -> None:
    """An unmappable community fails the export instead of defaulting.

    The control the grounding needs: a community-shaped value carrying no Modelo
    100 código must raise rather than return a fallback, because a declaration
    naming the wrong comunidad still validates against AEAT's schema.
    """
    with pytest.raises(ValueError, match="no Modelo 100 CCAA código is assigned"):
        modelo100_ccaa_codigo(_CommunityWithoutCodigo.CEUTA)


@pytest.mark.parametrize("token", ["pais_vasco", "navarra", "ceuta", "melilla", "no_residente", "", "MADRID"])
def test_modelo100_ccaa_codigo_refuses_tokens_outside_the_catalogue(token: str) -> None:
    """Foral regimes, the autonomous cities, and non-canonical spellings refuse."""
    with pytest.raises(ValueError, match="no Modelo 100 CCAA código is assigned"):
        modelo100_ccaa_codigo(token)


def test_canonical_tokens_resolve_the_same_as_their_enum_member() -> None:
    """The join may hold either the member or its canonical token."""
    for community in CCAA:
        assert modelo100_ccaa_codigo(community.value) == modelo100_ccaa_codigo(community)
