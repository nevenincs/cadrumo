"""An export serves the limits its calculation disclosed, in the filer's words, from the verification's own marker.

The verification of the exported revision decides which findings are limitations; the export
words exactly those, from the latest run, in the language asked, and invents none.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    VerificationReportCatalogue,
    derive_verification_report_id,
)
from ..export_disclosure import export_disclosure
from ..finding_message_text import finding_message_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REVISION = "a" * 64
_OTHER_REVISION = "b" * 64
_YEAR = filing_year_envelope().horizon
_LEAD_KEY = "application.modelo.export_disclosure.lead"
_LANGUAGES = tuple(OutputLanguage)


def _deduction_limitation() -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.trabajo_deduction_not_computed",
        legal_refs=("ley-35-2006:art-19",),
        disclosed_limitation=True,
    )


def _stated_figure_limitation() -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.cross_period_dependency_operator_attested",
        message_facts={
            "source_modelo": "100",
            "source_filing_year": _YEAR - 1,
            "source_period": "0A",
            "binding_id": "irpf.previous_year_economic_activity_net_income",
            "value": "12846.3",
            "target_modelo": "130",
            "target_filing_year": _YEAR,
            "target_period": "1T",
        },
        legal_refs=("ley-35-2006:art-19",),
        disclosed_limitation=True,
    )


def _ordinary_warning() -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.dt12a_reduccion_possible",
        legal_refs=("ley-35-2006:art-19",),
    )


def _report(
    findings: tuple[ModeloVerificationFinding, ...], *, revision: str = _REVISION, minute: int = 0
) -> VerificationReport:
    actor = f"verifier-{minute}"
    return VerificationReport(
        verification_report_id=derive_verification_report_id(
            calculation_revision_id=revision,
            completeness_status=VerificationCompletenessStatus.COMPLETE,
            findings=findings,
            verified_by=actor,
        ),
        calculation_revision_id=revision,
        registry_snapshot_ref=RegistrySnapshotRef(modelo="100", revision_id=str(_YEAR), modelo_year=_YEAR, period="0A"),
        completeness_status=VerificationCompletenessStatus.COMPLETE,
        findings=findings,
        run_at=datetime(2027, 1, 2, 9, minute, tzinfo=UTC),
        verified_by=actor,
        granted_verificado_completo=True,
    )


def _catalogue(*reports: VerificationReport) -> VerificationReportCatalogue:
    return VerificationReportCatalogue(reports={report.verification_report_id: report for report in reports})


@pytest.mark.parametrize("language", _LANGUAGES)
def test_only_the_marked_findings_are_served_in_the_asked_language(language: OutputLanguage) -> None:
    deduction = _deduction_limitation()
    stated = _stated_figure_limitation()
    catalogue = _catalogue(_report((_ordinary_warning(), deduction, stated)))

    disclosure = export_disclosure(catalogue, calculation_revision_id=_REVISION, language=language)

    assert disclosure is not None
    assert disclosure.lead_words == tr(_LEAD_KEY, locale=language.value)
    assert [item.message_locale_key for item in disclosure.limitations] == [
        deduction.message_locale_key,
        stated.message_locale_key,
    ]
    assert [item.words for item in disclosure.limitations] == [
        finding_message_text(deduction, language),
        finding_message_text(stated, language),
    ]
    for item in disclosure.limitations:
        assert "%{" not in item.words and "{count}" not in item.words
        assert item.message_locale_key not in item.words
    # The stated figure is written with the language's marks, and the period by its name, not its registry token.
    assert "128463" in re.sub(r"\D", "", disclosure.limitations[1].words)
    assert "12846.3" not in disclosure.limitations[1].words
    assert "1T" not in disclosure.limitations[1].words


def test_the_words_are_the_languages_own_and_the_lead_is_never_the_key() -> None:
    disclosures = {
        language: export_disclosure(
            _catalogue(_report((_deduction_limitation(),))), calculation_revision_id=_REVISION, language=language
        )
        for language in _LANGUAGES
    }

    leads = {language: item.lead_words for language, item in disclosures.items() if item is not None}
    assert len(leads) == len(_LANGUAGES)
    assert len(set(leads.values())) == len(_LANGUAGES)
    assert all(_LEAD_KEY not in lead and "%{" not in lead for lead in leads.values())
    sentences = {item.limitations[0].words for item in disclosures.values() if item is not None}
    assert len(sentences) == len(_LANGUAGES)


def test_a_verification_without_a_marked_finding_discloses_nothing() -> None:
    catalogue = _catalogue(_report((_ordinary_warning(),)))

    assert export_disclosure(catalogue, calculation_revision_id=_REVISION, language=OutputLanguage.EN) is None
    assert export_disclosure(_catalogue(), calculation_revision_id=_REVISION, language=OutputLanguage.EN) is None


def test_only_the_latest_run_of_the_exported_revision_counts() -> None:
    earlier = _report((_deduction_limitation(),), minute=1)
    latest = _report((_ordinary_warning(),), minute=2)
    elsewhere = _report((_stated_figure_limitation(),), revision=_OTHER_REVISION, minute=3)

    assert (
        export_disclosure(
            _catalogue(earlier, latest, elsewhere), calculation_revision_id=_REVISION, language=OutputLanguage.EN
        )
        is None
    )
    only_earlier = export_disclosure(_catalogue(earlier), calculation_revision_id=_REVISION, language=OutputLanguage.EN)
    assert only_earlier is not None
    assert len(only_earlier.limitations) == 1
