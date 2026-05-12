"""Post-persistence verification for wizard flows.

After ``persist_answers`` writes a flow's answers into ``ProfileRecord``,
the verifier runs a closed set of :class:`WizardCheck` records against
the typed projection and emits one :class:`WizardCheckFinding` per
check. Findings carry a severity and a translation key so renderers
can localise the outcome.

The check shape replaces the legacy ``Verifier`` orchestrator. Each
check is a pure function ``(BaseModel) -> WizardCheckFinding``; the
verifier accumulates the per-check findings into a
:class:`WizardCheckReport` and returns it as a frozen record.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ._setup_answers import SetupAnswers


class WizardCheckSeverity(StrEnum):
    """Severity classification for one ``WizardCheckFinding``."""

    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"


class WizardCheckFinding(BaseModel):
    """One verdict produced by a single :class:`WizardCheck`."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    severity: WizardCheckSeverity
    message_key: str = Field(min_length=1)


class WizardCheckReport(BaseModel):
    """The closed verifier outcome for one flow."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    findings: tuple[WizardCheckFinding, ...]

    @property
    def has_errors(self) -> bool:
        """True when any finding is an ``ERROR``."""
        return any(item.severity is WizardCheckSeverity.ERROR for item in self.findings)


class WizardCheck(BaseModel):
    """One declarative check the verifier runs against the typed projection."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

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
    if answers.declaration_type == "2" and not answers.spouse_tax_id:
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


def _check_residence_ccaa(answers: SetupAnswers) -> WizardCheckFinding:
    del answers
    return WizardCheckFinding(
        name="residence_ccaa",
        severity=WizardCheckSeverity.OK,
        message_key="wizard.setup.verifier.residence_ccaa_ok",
    )


def _check_iva_regime(answers: SetupAnswers) -> WizardCheckFinding:
    del answers
    return WizardCheckFinding(
        name="iva_regime",
        severity=WizardCheckSeverity.OK,
        message_key="wizard.setup.verifier.iva_regime_ok",
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


_SETUP_CHECKS: tuple[Callable[[SetupAnswers], WizardCheckFinding], ...] = (
    _check_tax_id_present,
    _check_activity_present,
    _check_spouse_consistency,
    _check_eu_eea_country_consistency,
    _check_residence_ccaa,
    _check_iva_regime,
    _check_obligations_consistency,
)


def verify_setup_answers(answers: SetupAnswers) -> WizardCheckReport:
    """Run the closed setup-flow check set against ``answers``."""

    findings = tuple(check(answers) for check in _SETUP_CHECKS)
    return WizardCheckReport(findings=findings)


__all__ = [
    "WizardCheck",
    "WizardCheckFinding",
    "WizardCheckReport",
    "WizardCheckSeverity",
    "verify_setup_answers",
]
