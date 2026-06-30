"""Modelo 100 Comunitat Valenciana semantic-role registry tests."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from ._modelo_100_registry_support import (
    _AUTONOMIC_DEDUCTION_ART_77_REF,
    _C_VALENCIANA_DEDUCTION_SECTION,
    _modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ExpectedRows = Mapping[str, tuple[str, str]]

_VA35_ACCIONES_PARTICIPACIONES_ROLE = "irpf_deduccion_c_valenciana_acciones_participaciones"
_VA35_ACCIONES_PARTICIPACIONES_GENERADO_ROLE = (
    "irpf_deduccion_c_valenciana_acciones_participaciones_generado"
)
_VA35_ACCIONES_PARTICIPACIONES_GENERADO_PENDIENTE_1_ROLE = (
    "irpf_deduccion_c_valenciana_acciones_participaciones_generado_pendiente_1"
)
_VA35_ACCIONES_PARTICIPACIONES_GENERADO_PENDIENTE_2_ROLE = (
    "irpf_deduccion_c_valenciana_acciones_participaciones_generado_pendiente_2"
)
_VA35_ACCIONES_PARTICIPACIONES_GENERADO_PENDIENTE_3_ROLE = (
    "irpf_deduccion_c_valenciana_acciones_participaciones_generado_pendiente_3"
)
_VA35_ACCIONES_PARTICIPACIONES_APLICADO_EJERCICIO_ANTERIOR_ROLE = (
    "irpf_deduccion_c_valenciana_acciones_participaciones_aplicado_ejercicio_anterior"
)
_VA35_ACCIONES_PARTICIPACIONES_APLICADO_EJERCICIO_ROLE = (
    "irpf_deduccion_c_valenciana_acciones_participaciones_aplicado_ejercicio"
)
_VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_ROLE = (
    "irpf_deduccion_c_valenciana_acciones_participaciones_pendiente"
)
_VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_1_ROLE = (
    "irpf_deduccion_c_valenciana_acciones_participaciones_pendiente_1"
)
_VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_2_ROLE = (
    "irpf_deduccion_c_valenciana_acciones_participaciones_pendiente_2"
)
_VA39_AUTOCONSUMO_ROLE = "irpf_deduccion_c_valenciana_autoconsumo_desde_2023"
_VA39_AUTOCONSUMO_GENERADO_ROLE = "irpf_deduccion_c_valenciana_autoconsumo_generado"
_VA39_AUTOCONSUMO_GENERADO_PENDIENTE_1_ROLE = (
    "irpf_deduccion_c_valenciana_autoconsumo_generado_pendiente_1"
)
_VA39_AUTOCONSUMO_GENERADO_PENDIENTE_2_ROLE = (
    "irpf_deduccion_c_valenciana_autoconsumo_generado_pendiente_2"
)
_VA39_AUTOCONSUMO_PENDIENTE_ROLE = "irpf_deduccion_c_valenciana_autoconsumo_pendiente"
_VA39_AUTOCONSUMO_PENDIENTE_1_ROLE = "irpf_deduccion_c_valenciana_autoconsumo_pendiente_1"
_VA39_AUTOCONSUMO_PENDIENTE_2_ROLE = "irpf_deduccion_c_valenciana_autoconsumo_pendiente_2"
_VA42_DANOS_VIVIENDA_DANA_ROLE = "irpf_deduccion_c_valenciana_danos_vivienda_dana"
_VA42_DANOS_VIVIENDA_DANA_GENERADO_ROLE = "irpf_deduccion_c_valenciana_danos_vivienda_dana_generado"
_VA42_DANOS_VIVIENDA_DANA_GENERADO_PENDIENTE_1_ROLE = (
    "irpf_deduccion_c_valenciana_danos_vivienda_dana_generado_pendiente_1"
)
_VA42_DANOS_VIVIENDA_DANA_PENDIENTE_ROLE = "irpf_deduccion_c_valenciana_danos_vivienda_dana_pendiente"
_VA42_DANOS_VIVIENDA_DANA_PENDIENTE_1_ROLE = (
    "irpf_deduccion_c_valenciana_danos_vivienda_dana_pendiente_1"
)
_VA43_APORTACIONES_FONDOS_PROPIOS_ROLE = "irpf_deduccion_c_valenciana_aportaciones_fondos_propios"
_VA43_APORTACIONES_FONDOS_PROPIOS_GENERADO_ROLE = (
    "irpf_deduccion_c_valenciana_aportaciones_fondos_propios_generado"
)
_VA43_APORTACIONES_FONDOS_PROPIOS_GENERADO_PENDIENTE_1_ROLE = (
    "irpf_deduccion_c_valenciana_aportaciones_fondos_propios_generado_pendiente_1"
)
_VA43_APORTACIONES_FONDOS_PROPIOS_PENDIENTE_ROLE = (
    "irpf_deduccion_c_valenciana_aportaciones_fondos_propios_pendiente"
)
_VA43_APORTACIONES_FONDOS_PROPIOS_PENDIENTE_1_ROLE = (
    "irpf_deduccion_c_valenciana_aportaciones_fondos_propios_pendiente_1"
)

_LEGACY_VALENCIANA_FAMILY_ROLES = frozenset(
    {
        "irpf_deduccion_c_valenciana_aplicado_ejercicio",
        "irpf_deduccion_c_valenciana_autoconsumo_2024_pendiente",
        "irpf_deduccion_c_valenciana_autoconsumo_2025_generado",
        "irpf_deduccion_c_valenciana_autoconsumo_2025_pendiente",
        "irpf_deduccion_c_valenciana_generado_2023_pendiente",
        "irpf_deduccion_c_valenciana_generado_2023_pendiente_2",
        "irpf_deduccion_c_valenciana_generado_2023_pendiente_3",
        "irpf_deduccion_c_valenciana_generado_2024_pendiente_2",
        "irpf_deduccion_c_valenciana_generado_2024_pendiente_3",
        "irpf_deduccion_c_valenciana_generado_2024_pendiente_4",
        "irpf_deduccion_c_valenciana_generado_2025_aplicado",
        "irpf_deduccion_c_valenciana_generado_2025_pendiente_2",
        "irpf_deduccion_c_valenciana_generado_ejercicio_pendiente",
        "irpf_deduccion_c_valenciana_generado_pendiente",
        "irpf_deduccion_c_valenciana_linea_6_importe_pendiente",
        "irpf_deduccion_c_valenciana_pendiente_2023_linea_4",
        "irpf_deduccion_c_valenciana_pendiente_2024_linea_4",
        "irpf_deduccion_c_valenciana_pendiente_aplicacion",
        "irpf_deduccion_c_valenciana_pendiente_linea_5",
    }
)

_VA35_PARENT_LABEL = (
    "Por inversión en adquisición de acciones o participaciones sociales "
    "en entidades nuevas o de reciente creación"
)
_VA35_EXPECTED_ROWS: Mapping[int, _ExpectedRows] = {
    2021: {
        "1182": ("Importe generado en 2021", _VA35_ACCIONES_PARTICIPACIONES_GENERADO_ROLE),
        "1183": ("Importe de la deducción", _VA35_ACCIONES_PARTICIPACIONES_ROLE),
        "1184": ("Importe generado en 2021 pendiente de aplicación", _VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_ROLE),
    },
    2022: {
        "0807": (
            "Importe generado en 2021 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_GENERADO_PENDIENTE_1_ROLE,
        ),
        "0808": (
            "Importe aplicado en el ejercicio",
            _VA35_ACCIONES_PARTICIPACIONES_APLICADO_EJERCICIO_ANTERIOR_ROLE,
        ),
        "1117": (
            "Importe aplicado en el ejercicio",
            _VA35_ACCIONES_PARTICIPACIONES_APLICADO_EJERCICIO_ROLE,
        ),
        "1182": (
            "Importe generado en 2022(importe de la casilla [1136] del anexo B.8 )",
            _VA35_ACCIONES_PARTICIPACIONES_GENERADO_ROLE,
        ),
        "1183": (
            f"{_VA35_PARENT_LABEL} (suma de las casillas [0808] + [1117])",
            _VA35_ACCIONES_PARTICIPACIONES_ROLE,
        ),
        "1184": (
            "Importe generado en 2022 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_ROLE,
        ),
        "1210": (
            "Importe generado en 2021 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_1_ROLE,
        ),
    },
    2023: {
        "0807": (
            "Importe generado en 2021 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_GENERADO_PENDIENTE_1_ROLE,
        ),
        "1182": (
            "Importe generado en 2023 pendiente de aplicación (importe de la casilla [1136] del anexo B.8 )",
            _VA35_ACCIONES_PARTICIPACIONES_GENERADO_PENDIENTE_3_ROLE,
        ),
        "1183": (_VA35_PARENT_LABEL, _VA35_ACCIONES_PARTICIPACIONES_ROLE),
        "1184": (
            "Importe generado en 2022 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_2_ROLE,
        ),
        "1210": (
            "Importe generado en 2021 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_1_ROLE,
        ),
        "1961": (
            "Importe generado en 2022 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_GENERADO_PENDIENTE_2_ROLE,
        ),
        "1964": (
            "Importe generado en 2023 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_ROLE,
        ),
    },
    2024: {
        "0807": (
            "Importe generado en 2021 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_GENERADO_PENDIENTE_1_ROLE,
        ),
        "1182": (
            "Importe generado en 2024 (importe de la casilla [1136] del anexo B.9 )",
            _VA35_ACCIONES_PARTICIPACIONES_GENERADO_ROLE,
        ),
        "1183": (_VA35_PARENT_LABEL, _VA35_ACCIONES_PARTICIPACIONES_ROLE),
        "1184": (
            "Importe generado en 2023 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_2_ROLE,
        ),
        "1209": (
            "Importe generado en 2023 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_GENERADO_PENDIENTE_3_ROLE,
        ),
        "1210": (
            "Importe generado en 2022 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_1_ROLE,
        ),
        "1961": (
            "Importe generado en 2022 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_GENERADO_PENDIENTE_2_ROLE,
        ),
        "1964": (
            "Importe generado en 2024 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_ROLE,
        ),
    },
    2025: {
        "0807": (
            "Importe generado en 2024 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_GENERADO_PENDIENTE_3_ROLE,
        ),
        "1182": (
            "Importe generado en 2025 (importe de la casilla [1136] del anexo B.11 )",
            _VA35_ACCIONES_PARTICIPACIONES_GENERADO_ROLE,
        ),
        "1183": (_VA35_PARENT_LABEL, _VA35_ACCIONES_PARTICIPACIONES_ROLE),
        "1184": (
            "Importe generado en 2024 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_2_ROLE,
        ),
        "1209": (
            "Importe generado en 2023 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_GENERADO_PENDIENTE_2_ROLE,
        ),
        "1210": (
            "Importe generado en 2023 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_1_ROLE,
        ),
        "1961": (
            "Importe generado en 2022 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_GENERADO_PENDIENTE_1_ROLE,
        ),
        "1964": (
            "Importe generado en 2025 pendiente de aplicación",
            _VA35_ACCIONES_PARTICIPACIONES_PENDIENTE_ROLE,
        ),
    },
}

_VA39_PARENT_LABEL = (
    "Por cantidades invertidas a partir de 2023 en instalaciones de autoconsumo "
    "o de generación de energía eléctrica o térmica a través de fuentes renovables"
)
_VA39_EXPECTED_ROWS: Mapping[int, _ExpectedRows] = {
    2023: {
        "1962": (_VA39_PARENT_LABEL, _VA39_AUTOCONSUMO_ROLE),
        "1963": ("Importe generado en 2023", _VA39_AUTOCONSUMO_GENERADO_ROLE),
        "1965": ("Importe generado en 2023 pendiente de aplicación", _VA39_AUTOCONSUMO_PENDIENTE_ROLE),
    },
    2024: {
        "0848": ("Importe generado en 2024 pendiente de aplicación", _VA39_AUTOCONSUMO_PENDIENTE_ROLE),
        "1186": (
            "Importe generado en 2023 pendiente de aplicación",
            _VA39_AUTOCONSUMO_GENERADO_PENDIENTE_1_ROLE,
        ),
        "1962": (
            f"{_VA39_PARENT_LABEL} (importe de la casilla [2001] del anexo B.10)",
            _VA39_AUTOCONSUMO_ROLE,
        ),
        "1963": ("Importe generado en 2024", _VA39_AUTOCONSUMO_GENERADO_ROLE),
        "1965": ("Importe generado en 2023 pendiente de aplicación", _VA39_AUTOCONSUMO_PENDIENTE_1_ROLE),
    },
    2025: {
        "0848": ("Importe generado en 2025 pendiente de aplicación", _VA39_AUTOCONSUMO_PENDIENTE_ROLE),
        "1186": (
            "Importe generado en 2024 pendiente de aplicación",
            _VA39_AUTOCONSUMO_GENERADO_PENDIENTE_1_ROLE,
        ),
        "1958": (
            "Importe generado en 2023 pendiente de aplicación",
            _VA39_AUTOCONSUMO_GENERADO_PENDIENTE_2_ROLE,
        ),
        "1962": (
            f"{_VA39_PARENT_LABEL} (importe de la casilla [2001] del anexo B.12)",
            _VA39_AUTOCONSUMO_ROLE,
        ),
        "1963": ("Importe generado en 2025", _VA39_AUTOCONSUMO_GENERADO_ROLE),
        "1965": ("Importe generado en 2024 pendiente de aplicación", _VA39_AUTOCONSUMO_PENDIENTE_1_ROLE),
        "2013": ("Importe generado en 2023 pendiente de aplicación", _VA39_AUTOCONSUMO_PENDIENTE_2_ROLE),
    },
}

_VA42_PARENT_LABEL = (
    "Por destinar cantidades a paliar los daños materiales sobre la vivienda habitual "
    "derivados del temporal"
)
_VA43_PARENT_LABEL_BY_YEAR = {
    2024: (
        "Por aportaciones a los fondos propios de entidades que desarrollen actividades económicas "
        "(casilla [2148] del anexo B.12)"
    ),
    2025: (
        "Por aportaciones a los fondos propios de entidades que desarrollen actividades económicas "
        "(casilla [2148] del anexo B.14)"
    ),
}
_VA42_VA43_EXPECTED_ROWS: Mapping[int, _ExpectedRows] = {
    2024: {
        "1690": ("Importe generado en 2024 pendiente de aplicación", _VA42_DANOS_VIVIENDA_DANA_PENDIENTE_ROLE),
        "1691": (
            "Importe generado en 2024 pendiente de aplicación",
            _VA43_APORTACIONES_FONDOS_PROPIOS_PENDIENTE_ROLE,
        ),
        "1702": (_VA42_PARENT_LABEL, _VA42_DANOS_VIVIENDA_DANA_ROLE),
        "1703": ("Importe generado en 2024", _VA42_DANOS_VIVIENDA_DANA_GENERADO_ROLE),
        "1704": (_VA43_PARENT_LABEL_BY_YEAR[2024], _VA43_APORTACIONES_FONDOS_PROPIOS_ROLE),
        "1705": ("Importe generado en 2024", _VA43_APORTACIONES_FONDOS_PROPIOS_GENERADO_ROLE),
    },
    2025: {
        "1185": (
            "Importe generado en 2024 pendiente de aplicación",
            _VA42_DANOS_VIVIENDA_DANA_GENERADO_PENDIENTE_1_ROLE,
        ),
        "1690": ("Importe generado en 2025 pendiente de aplicación", _VA42_DANOS_VIVIENDA_DANA_PENDIENTE_ROLE),
        "1702": (_VA42_PARENT_LABEL, _VA42_DANOS_VIVIENDA_DANA_ROLE),
        "1703": ("Importe generado en 2025", _VA42_DANOS_VIVIENDA_DANA_GENERADO_ROLE),
        "2014": (
            "Importe generado en 2024 pendiente de aplicación",
            _VA42_DANOS_VIVIENDA_DANA_PENDIENTE_1_ROLE,
        ),
        "2012": (
            "Importe generado en 2024 pendiente de aplicación",
            _VA43_APORTACIONES_FONDOS_PROPIOS_GENERADO_PENDIENTE_1_ROLE,
        ),
        "1691": (
            "Importe generado en 2025 pendiente de aplicación",
            _VA43_APORTACIONES_FONDOS_PROPIOS_PENDIENTE_ROLE,
        ),
        "1704": (_VA43_PARENT_LABEL_BY_YEAR[2025], _VA43_APORTACIONES_FONDOS_PROPIOS_ROLE),
        "1705": ("Importe generado en 2025", _VA43_APORTACIONES_FONDOS_PROPIOS_GENERADO_ROLE),
        "2015": (
            "Importe generado en 2024 pendiente de aplicación",
            _VA43_APORTACIONES_FONDOS_PROPIOS_PENDIENTE_1_ROLE,
        ),
    },
}
_INTENTIONAL_SINGLETON_ROWS = (
    (
        2022,
        "0808",
        _VA35_ACCIONES_PARTICIPACIONES_APLICADO_EJERCICIO_ANTERIOR_ROLE,
        "2022-only VA35 prior-year acciones-participaciones applied-in-exercise slot.",
    ),
    (
        2022,
        "1117",
        _VA35_ACCIONES_PARTICIPACIONES_APLICADO_EJERCICIO_ROLE,
        "2022-only VA35 current-year acciones-participaciones applied-in-exercise slot.",
    ),
    (
        2025,
        "1185",
        _VA42_DANOS_VIVIENDA_DANA_GENERADO_PENDIENTE_1_ROLE,
        "2025-only VA42 DANA 2024 generated carry-forward amount slot.",
    ),
    (
        2025,
        "2012",
        _VA43_APORTACIONES_FONDOS_PROPIOS_GENERADO_PENDIENTE_1_ROLE,
        "2025-only VA43 fondos propios 2024 generated carry-forward amount slot.",
    ),
    (
        2025,
        "2014",
        _VA42_DANOS_VIVIENDA_DANA_PENDIENTE_1_ROLE,
        "2025-only VA42 DANA 2024 pending carry-forward amount slot.",
    ),
    (
        2025,
        "2015",
        _VA43_APORTACIONES_FONDOS_PROPIOS_PENDIENTE_1_ROLE,
        "2025-only VA43 fondos propios 2024 pending carry-forward amount slot.",
    ),
)


def _assert_c_valenciana_rows(filing_year: int, expected_rows: _ExpectedRows) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_rows}
    legacy_rows = {
        casilla.id: casilla.semantic_role
        for casilla in casillas_by_id.values()
        if casilla.semantic_role in _LEGACY_VALENCIANA_FAMILY_ROLES
    }

    assert not legacy_rows
    assert set(casillas_by_id) == set(expected_rows)
    for casilla_id, (expected_label, expected_role) in expected_rows.items():
        casilla = casillas_by_id[casilla_id]
        assert casilla.label == expected_label
        assert tuple(casilla.section) == _C_VALENCIANA_DEDUCTION_SECTION
        assert casilla.semantic_role == expected_role
        assert _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs


@pytest.mark.parametrize("filing_year", [2021, 2022, 2023, 2024, 2025])
def test_modelo_100_c_valenciana_va35_roles_follow_acciones_participaciones_family(filing_year: int) -> None:
    _assert_c_valenciana_rows(filing_year, _VA35_EXPECTED_ROWS[filing_year])


@pytest.mark.parametrize("filing_year", [2023, 2024, 2025])
def test_modelo_100_c_valenciana_va39_roles_follow_autoconsumo_family(filing_year: int) -> None:
    _assert_c_valenciana_rows(filing_year, _VA39_EXPECTED_ROWS[filing_year])


@pytest.mark.parametrize("filing_year", [2024, 2025])
def test_modelo_100_c_valenciana_va42_va43_roles_follow_official_families(filing_year: int) -> None:
    _assert_c_valenciana_rows(filing_year, _VA42_VA43_EXPECTED_ROWS[filing_year])


@pytest.mark.parametrize("filing_year", [2021, 2022, 2023, 2024, 2025])
def test_modelo_100_c_valenciana_registry_does_not_use_legacy_generated_pending_roles(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    legacy_rows = {
        casilla.id: casilla.semantic_role
        for casilla in revision.casillas
        if tuple(casilla.section) == _C_VALENCIANA_DEDUCTION_SECTION
        and casilla.semantic_role in _LEGACY_VALENCIANA_FAMILY_ROLES
    }

    assert not legacy_rows


@pytest.mark.parametrize(("filing_year", "casilla_id", "expected_role", "expected_reason"), _INTENTIONAL_SINGLETON_ROWS)
def test_modelo_100_c_valenciana_reviewed_singletons_are_marked(
    filing_year: int,
    casilla_id: str,
    expected_role: str,
    expected_reason: str,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casilla = next(item for item in revision.casillas if item.id == casilla_id)

    assert casilla.semantic_role == expected_role
    assert casilla.semantic_role_cardinality == "intentional_singleton"
    assert casilla.semantic_role_cardinality_reason == expected_reason
