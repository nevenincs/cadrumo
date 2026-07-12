"""Tests for Art. 84.2.2° LIRPF monoparental reducción €2,150 (casilla 0461).

Oracle grounding: Art. 84 LIRPF fixes the reducción amounts:
  - Art. 84.2.1°: €3,400 for matrimonio/pareja registrada (tipo 1)
  - Art. 84.2.2°: €2,150 for monoparental unidad familiar (tipo 2)

These values are listed in AEAT Manual Renta 2024, Parte 1, section on
«Reducción por tributación conjunta».

Verifier check:
  _check_monoparental_requires_hijos: WARNING when soltero/separado_divorciado
  requests conjunta without family_minor_children_in_unit=True.
"""

from __future__ import annotations

import pytest

from ....core.setup_answers import SetupAnswers
from ....domain.contribuyente import CCAA, SituacionFamiliar
from ....domain.deadlines import IVARegime
from .._verifier import (
    WizardCheckFinding,
    WizardCheckSeverity,
    verify_setup_answers,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_answers(**overrides: object) -> SetupAnswers:
    defaults: dict[str, object] = {
        "tax_id": "12345678Z",
        "activity": "consultora",
        "iva_regime": IVARegime.GENERAL,
        "tax_residence_ccaa": CCAA.MADRID,
    }
    defaults.update(overrides)
    return SetupAnswers.model_validate(defaults)


def _monoparental_finding(answers: SetupAnswers) -> WizardCheckFinding:
    report = verify_setup_answers(answers)
    return next(item for item in report.findings if item.name == "monoparental_requires_hijos")


# ---------------------------------------------------------------------------
# _check_monoparental_requires_hijos verifier
# ---------------------------------------------------------------------------


_MONOPARENTAL_CASES: tuple[
    tuple[str, dict[str, object], WizardCheckSeverity, str],
    ...,
] = (
    (
        "individual-taxation",
        {
            "taxation_type": "1",
            "situacion_familiar": SituacionFamiliar.SOLTERO,
        },
        WizardCheckSeverity.OK,
        "wizard.setup.verifier.monoparental_requires_hijos_ok",
    ),
    (
        "taxation-type-blank",
        {
            "taxation_type": "",
            "situacion_familiar": SituacionFamiliar.SOLTERO,
        },
        WizardCheckSeverity.OK,
        "wizard.setup.verifier.monoparental_requires_hijos_ok",
    ),
    (
        "situacion-blank",
        {
            "taxation_type": "2",
            "situacion_familiar": "",
            "spouse_tax_id": "87654321B",
        },
        WizardCheckSeverity.OK,
        "wizard.setup.verifier.monoparental_requires_hijos_ok",
    ),
    (
        "casado-conjunta-no-hijos",
        {
            "taxation_type": "2",
            "situacion_familiar": SituacionFamiliar.CASADO,
            "spouse_tax_id": "87654321B",
            "family_minor_children_in_unit": False,
        },
        WizardCheckSeverity.OK,
        "wizard.setup.verifier.monoparental_requires_hijos_ok",
    ),
    (
        "soltero-conjunta-with-hijos",
        {
            "taxation_type": "2",
            "situacion_familiar": SituacionFamiliar.SOLTERO,
            "spouse_tax_id": "87654321B",
            "family_minor_children_in_unit": True,
        },
        WizardCheckSeverity.OK,
        "wizard.setup.verifier.monoparental_requires_hijos_ok",
    ),
    (
        "soltero-conjunta-without-hijos",
        {
            "taxation_type": "2",
            "situacion_familiar": SituacionFamiliar.SOLTERO,
            "spouse_tax_id": "87654321B",
            "family_minor_children_in_unit": False,
        },
        WizardCheckSeverity.WARNING,
        "wizard.setup.verifier.monoparental_requires_hijos_warning",
    ),
    (
        "separado-divorciado-conjunta-without-hijos",
        {
            "taxation_type": "2",
            "situacion_familiar": SituacionFamiliar.SEPARADO_DIVORCIADO,
            "spouse_tax_id": "87654321B",
            "family_minor_children_in_unit": False,
        },
        WizardCheckSeverity.WARNING,
        "wizard.setup.verifier.monoparental_requires_hijos_warning",
    ),
    (
        "separado-divorciado-conjunta-with-hijos",
        {
            "taxation_type": "2",
            "situacion_familiar": SituacionFamiliar.SEPARADO_DIVORCIADO,
            "spouse_tax_id": "87654321B",
            "family_minor_children_in_unit": True,
        },
        WizardCheckSeverity.OK,
        "wizard.setup.verifier.monoparental_requires_hijos_ok",
    ),
)


def test_monoparental_requires_hijos_cases() -> None:
    for case_id, overrides, expected_severity, expected_message_key in _MONOPARENTAL_CASES:
        answers = _base_answers(**overrides)
        finding = _monoparental_finding(answers)
        assert finding.severity is expected_severity, case_id
        assert finding.message_key == expected_message_key, case_id


def test_with_vs_without_hijos_produces_different_severity() -> None:
    """If the check were tautological, both outcomes would match."""
    with_hijos = _base_answers(
        taxation_type="2",
        situacion_familiar=SituacionFamiliar.SOLTERO,
        spouse_tax_id="87654321B",
        family_minor_children_in_unit=True,
    )
    without_hijos = _base_answers(
        taxation_type="2",
        situacion_familiar=SituacionFamiliar.SOLTERO,
        spouse_tax_id="87654321B",
        family_minor_children_in_unit=False,
    )
    finding_with = _monoparental_finding(with_hijos)
    finding_without = _monoparental_finding(without_hijos)
    assert finding_with.severity is not finding_without.severity
