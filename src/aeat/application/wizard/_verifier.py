"""Post-persistence verification for wizard flows.

After ``persist_answers`` writes a flow's answers into ``ProfileRecord``,
the verifier runs a closed set of :class:`WizardCheck` records against
the typed projection and emits one :class:`WizardCheckFinding` per
check. Findings carry a severity and a translation key so renderers
can localise the outcome.

Each check is a pure function ``(BaseModel) -> WizardCheckFinding``;
the verifier accumulates the per-check findings into a
:class:`WizardCheckReport` and returns it as a frozen record.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...core.setup_answers import SetupAnswers


class WizardCheckSeverity(StrEnum):
    """Severity classification for one ``WizardCheckFinding``."""

    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"


class WizardCheckFinding(BaseModel):
    """One verdict produced by a single :class:`WizardCheck`."""

    model_config = STRICT_FROZEN_CONFIG

    name: str = Field(min_length=1)
    severity: WizardCheckSeverity
    message_key: str = Field(min_length=1)


class WizardCheckReport(BaseModel):
    """The closed verifier outcome for one flow."""

    model_config = STRICT_FROZEN_CONFIG

    findings: tuple[WizardCheckFinding, ...]

    @property
    def has_errors(self) -> bool:
        """True when any finding is an ``ERROR``."""
        return any(item.severity is WizardCheckSeverity.ERROR for item in self.findings)


class WizardCheck(BaseModel):
    """One declarative check the verifier runs against the typed projection."""

    model_config = STRICT_FROZEN_CONFIG

    name: str = Field(min_length=1)
    message_key: str = Field(min_length=1)


def _check_tax_id_present(answers: SetupAnswers) -> WizardCheckFinding:
    severity = WizardCheckSeverity.OK if answers.tax_id else WizardCheckSeverity.ERROR
    return WizardCheckFinding(
        name="tax_id_present",
        severity=severity,
        message_key="wizard.setup.verifier.tax_id_present",
    )


def _check_activity_present(answers: SetupAnswers) -> WizardCheckFinding:
    severity = WizardCheckSeverity.OK if answers.activity else WizardCheckSeverity.ERROR
    return WizardCheckFinding(
        name="activity_present",
        severity=severity,
        message_key="wizard.setup.verifier.activity_present",
    )


def _check_spouse_consistency(answers: SetupAnswers) -> WizardCheckFinding:
    if answers.taxation_type == "2" and not answers.spouse_tax_id:
        return WizardCheckFinding(
            name="spouse_consistency",
            severity=WizardCheckSeverity.ERROR,
            message_key="wizard.setup.verifier.spouse_consistency_missing",
        )
    return WizardCheckFinding(
        name="spouse_consistency",
        severity=WizardCheckSeverity.OK,
        message_key="wizard.setup.verifier.spouse_consistency_ok",
    )


def _check_eu_eea_country_consistency(answers: SetupAnswers) -> WizardCheckFinding:
    if answers.spouse_eu_eea_resident and not answers.spouse_eu_eea_country:
        return WizardCheckFinding(
            name="eu_eea_country_consistency",
            severity=WizardCheckSeverity.ERROR,
            message_key="wizard.setup.verifier.eu_eea_country_missing",
        )
    return WizardCheckFinding(
        name="eu_eea_country_consistency",
        severity=WizardCheckSeverity.OK,
        message_key="wizard.setup.verifier.eu_eea_country_ok",
    )


def _check_obligations_consistency(answers: SetupAnswers) -> WizardCheckFinding:
    if answers.professional_income_withholding_ge_70pct and not answers.pays_professionals_with_retencion:
        return WizardCheckFinding(
            name="obligations_consistency",
            severity=WizardCheckSeverity.WARNING,
            message_key="wizard.setup.verifier.obligations_inconsistent",
        )
    return WizardCheckFinding(
        name="obligations_consistency",
        severity=WizardCheckSeverity.OK,
        message_key="wizard.setup.verifier.obligations_consistency_ok",
    )


# Art. 82.1.2° LIRPF: conjunta requires marriage or a registered pareja de
# hecho. An unregistered pareja de hecho, soltero without hijos, and
# separado/divorciado without hijos a cargo are ineligible for conjunta via
# the cónyuge path. Monoparental conjunta (soltero/separado with hijos) is
# not blocked here — the tax engine handles the variant routing, so the
# verifier issues a WARNING rather than an ERROR when the monoparental path
# may apply, and only hard-ERRORs for the clearly-ineligible case.
def _check_joint_taxation_situacion_familiar(answers: SetupAnswers) -> WizardCheckFinding:
    # Skip when conjunta is not requested or situacion_familiar is undeclared.
    if answers.taxation_type != "2" or not answers.situacion_familiar:
        return WizardCheckFinding(
            name="joint_taxation_situacion_familiar",
            severity=WizardCheckSeverity.OK,
            message_key="wizard.setup.verifier.joint_taxation_situacion_familiar_ok",
        )
    sf = answers.situacion_familiar
    if not sf.conjunta_eligible():
        return WizardCheckFinding(
            name="joint_taxation_situacion_familiar",
            severity=WizardCheckSeverity.ERROR,
            message_key="wizard.setup.verifier.joint_taxation_situacion_familiar_refused",
        )
    return WizardCheckFinding(
        name="joint_taxation_situacion_familiar",
        severity=WizardCheckSeverity.OK,
        message_key="wizard.setup.verifier.joint_taxation_situacion_familiar_ok",
    )


def _check_monoparental_requires_hijos(answers: SetupAnswers) -> WizardCheckFinding:
    # Art. 82.1.2° LIRPF: monoparental unidad familiar requires hijos a cargo.
    # A soltero/separado/divorciado requesting conjunta without minor children in
    # the unit cannot form the monoparental unidad familiar — issue a WARNING so
    # the operator can correct the declaration before filing.
    if answers.taxation_type != "2" or not answers.situacion_familiar:
        return WizardCheckFinding(
            name="monoparental_requires_hijos",
            severity=WizardCheckSeverity.OK,
            message_key="wizard.setup.verifier.monoparental_requires_hijos_ok",
        )
    sf = answers.situacion_familiar
    if sf.monoparental_required() and not answers.family_minor_children_in_unit:
        return WizardCheckFinding(
            name="monoparental_requires_hijos",
            severity=WizardCheckSeverity.WARNING,
            message_key="wizard.setup.verifier.monoparental_requires_hijos_warning",
        )
    return WizardCheckFinding(
        name="monoparental_requires_hijos",
        severity=WizardCheckSeverity.OK,
        message_key="wizard.setup.verifier.monoparental_requires_hijos_ok",
    )


_SETUP_CHECKS: tuple[Callable[[SetupAnswers], WizardCheckFinding], ...] = (
    _check_tax_id_present,
    _check_activity_present,
    _check_spouse_consistency,
    _check_eu_eea_country_consistency,
    _check_obligations_consistency,
    _check_joint_taxation_situacion_familiar,
    _check_monoparental_requires_hijos,
)


def verify_setup_answers(answers: SetupAnswers) -> WizardCheckReport:
    """Run the closed setup-flow check set against ``answers``.

    Returns a :class:`WizardCheckReport` with the per-check finding
    verdicts for all registered setup checks.
    """
    findings = tuple(check(answers) for check in _SETUP_CHECKS)
    return WizardCheckReport(findings=findings)


__all__ = [
    "WizardCheck",
    "WizardCheckFinding",
    "WizardCheckReport",
    "WizardCheckSeverity",
    "verify_setup_answers",
]
