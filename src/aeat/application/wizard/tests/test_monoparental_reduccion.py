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
from ....domain.contribuyente._ccaa import CCAA
from ....domain.contribuyente._renta_codes import SituacionFamiliar
from ....domain.deadlines._models import IVARegime
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


class TestMonoparentalRequiresHijosVerifier:
    """Verifier emits WARNING when soltero/separado conjunta lacks hijos a cargo."""

    def test_ok_when_individual_taxation(self) -> None:
        """Individual taxation never triggers this check."""
        answers = _base_answers(
            taxation_type="1",
            situacion_familiar=SituacionFamiliar.SOLTERO,
        )
        finding = _monoparental_finding(answers)
        assert finding.severity is WizardCheckSeverity.OK

    def test_ok_when_taxation_type_blank(self) -> None:
        """Blank taxation type passes — check is undeclared."""
        answers = _base_answers(
            taxation_type="",
            situacion_familiar=SituacionFamiliar.SOLTERO,
        )
        finding = _monoparental_finding(answers)
        assert finding.severity is WizardCheckSeverity.OK

    def test_ok_when_situacion_familiar_blank(self) -> None:
        """Blank situacion_familiar passes even for conjunta."""
        answers = _base_answers(
            taxation_type="2",
            situacion_familiar="",
            spouse_tax_id="87654321B",
        )
        finding = _monoparental_finding(answers)
        assert finding.severity is WizardCheckSeverity.OK

    def test_ok_when_casado_conjunta_no_hijos(self) -> None:
        """Casado conjunta without hijos is tipo-1 — monoparental check does not apply."""
        answers = _base_answers(
            taxation_type="2",
            situacion_familiar=SituacionFamiliar.CASADO,
            spouse_tax_id="87654321B",
            family_minor_children_in_unit=False,
        )
        finding = _monoparental_finding(answers)
        assert finding.severity is WizardCheckSeverity.OK

    def test_ok_when_soltero_conjunta_with_hijos(self) -> None:
        """Soltero + conjunta + hijos is valid monoparental path — no warning."""
        answers = _base_answers(
            taxation_type="2",
            situacion_familiar=SituacionFamiliar.SOLTERO,
            spouse_tax_id="87654321B",
            family_minor_children_in_unit=True,
        )
        finding = _monoparental_finding(answers)
        assert finding.severity is WizardCheckSeverity.OK
        assert finding.message_key == "wizard.setup.verifier.monoparental_requires_hijos_ok"

    def test_warning_when_soltero_conjunta_without_hijos(self) -> None:
        """Art. 82.1.2° LIRPF: soltero conjunta without hijos cannot form monoparental unit."""
        answers = _base_answers(
            taxation_type="2",
            situacion_familiar=SituacionFamiliar.SOLTERO,
            spouse_tax_id="87654321B",
            family_minor_children_in_unit=False,
        )
        finding = _monoparental_finding(answers)
        assert finding.severity is WizardCheckSeverity.WARNING
        assert finding.message_key == "wizard.setup.verifier.monoparental_requires_hijos_warning"

    def test_warning_when_separado_divorciado_conjunta_without_hijos(self) -> None:
        """Separado/divorciado conjunta without hijos cannot form monoparental unit."""
        answers = _base_answers(
            taxation_type="2",
            situacion_familiar=SituacionFamiliar.SEPARADO_DIVORCIADO,
            spouse_tax_id="87654321B",
            family_minor_children_in_unit=False,
        )
        finding = _monoparental_finding(answers)
        assert finding.severity is WizardCheckSeverity.WARNING

    def test_ok_when_separado_divorciado_conjunta_with_hijos(self) -> None:
        """Separado/divorciado + conjunta + hijos is valid monoparental path."""
        answers = _base_answers(
            taxation_type="2",
            situacion_familiar=SituacionFamiliar.SEPARADO_DIVORCIADO,
            spouse_tax_id="87654321B",
            family_minor_children_in_unit=True,
        )
        finding = _monoparental_finding(answers)
        assert finding.severity is WizardCheckSeverity.OK


class TestMonoparentalAntiTautology:
    """Changing family_minor_children_in_unit must change verifier outcome."""

    def test_with_vs_without_hijos_produces_different_severity(self) -> None:
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
        # The two outcomes must differ — proof the formula is evaluated.
        assert finding_with.severity is not finding_without.severity
