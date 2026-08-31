"""Shared real-behavior setup for overview calendar tests."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ....adapters.inbound.pdf.source_provenance import source_pdf_reference_path
from ....application.user_profile.censo_sync import CENSO_SOURCE_TAG
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.justificante.schema import Justificante
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ....domain.user_profile.values import UserProfileFact
from ....tests.aeat_literal_fixtures import aeat_url, justificante_cotejo_url
from ....tests.profile_capsule import load_test_profile_record, open_test_profile_session, replace_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

__all__ = ["_isolated_backend"]

_SOURCE_URL = AnyHttpUrl(aeat_url("sede", "/"))
_WORK_UNIT_ID = "a" * 64
_CALCULATION_REVISION_ID = "b" * 64

#: Canonical bucket id the calendar fixtures register and open a storage
#: span for. Every direct repository/service call in this module and in
#: ``test_overview_calendar_verb.py`` must address this same bucket id, or
#: the strict per-bucket route binding (D10) refuses the call with
#: ``the primary database route does not match the active bucket session``.
PRIMARY_PROFILE_ID = "11111111-1111-4111-8111-111111111111"


#: Calendar strict-mode completeness gating reads these profile-fact paths
#: (``_gating_fields`` in ``application.overview.calendar_warnings``) off
#: every registered modelo applicability rule and deadline window. A minimal
#: profile that leaves them unset makes every calendar fixture refuse with
#: "comprobaciones de perfil sin resolver" before the scenario under test is
#: even reached. Resolve them here to an explicit "false" so the calendar
#: fixtures exercise their own scenario-specific warnings, not this generic
#: completeness gate. ``iva.regime`` and ``irpf.estimation_regime`` are the
#: two other gating keys; ``register_minimal_profile`` already sets both.
_CALENDAR_GATING_FACT_OVERRIDES: dict[str, str] = {
    "withholding.has_employees": "false",
    "withholding.pays_professionals_with_retencion": "false",
    "irpf.art109_activity_income_withholding_ge_70pct": "false",
    "withholding.pays_rent_with_retencion": "false",
    "withholding.pays_capital_income_with_retencion": "false",
    "iva.does_intracomunitario": "false",
    "obligations.third_party_transactions_above_347_threshold": "false",
}


@contextmanager
def isolated_calendar_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session(PRIMARY_PROFILE_ID),
    ):
        register_minimal_profile(
            profile_id=PRIMARY_PROFILE_ID,
            display_name="operator",
            overrides=_CALENDAR_GATING_FACT_OVERRIDES,
        )
        yield


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_calendar_backend(tmp_path):
        yield


@contextmanager
def calendar_backend_omitting_gating_facts(tmp_path: Path, *omitted: str) -> Iterator[None]:
    """Isolated calendar backend whose profile leaves the named gating facts unanswered.

    The default backend answers every completeness gating fact, deliberately,
    so scenario fixtures see only their own warnings. That makes it unable to
    express the case where an operator simply has not answered a gating
    question yet - which is the case the completeness warning exists for.

    Each name in ``omitted`` is a profile fact path. It is overridden to the
    empty string, which ``register_minimal_profile`` drops rather than stores,
    so the fact is genuinely ABSENT rather than present-and-false. The two are
    different states and only absence raises the warning.
    """
    unknown = tuple(path for path in omitted if path not in _CALENDAR_GATING_FACT_OVERRIDES)
    if unknown:
        raise AssertionError(
            f"not gating facts this fixture answers, so omitting them changes nothing: {list(unknown)}",
        )
    overrides = dict(_CALENDAR_GATING_FACT_OVERRIDES)
    for path in omitted:
        overrides[path] = ""
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session(PRIMARY_PROFILE_ID),
    ):
        register_minimal_profile(profile_id=PRIMARY_PROFILE_ID, display_name="operator", overrides=overrides)
        yield


_OBSERVED_CASILLA: CasillaId = validated_casilla_id("01")


def _observed_casilla_observations(value: Decimal):
    return registry_grounded_observations(
        modelo="303",
        filing_year=2025,
        period="1T",
        casilla_values={_OBSERVED_CASILLA: value},
    )


def _modelo_record_with_external_justificante(
    *,
    csv: str,
    bucket_id: str = PRIMARY_PROFILE_ID,
    evidence_kind: ExternalEvidenceKind = ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
) -> ModeloRecord:
    filed_at = datetime(2025, 4, 16, 12, 0, tzinfo=UTC)
    return ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=_WORK_UNIT_ID,
            calculation_revision_id=_CALCULATION_REVISION_ID,
            filed_by="aeat-import",
        ),
        work_unit_id=_WORK_UNIT_ID,
        calculation_revision_id=_CALCULATION_REVISION_ID,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        filed_at=filed_at,
        filed_by="aeat-import",
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=evidence_kind,
            reference_id=csv,
            imported_at=filed_at,
        ),
    )


def _justificante_metadata(*, csv: str, tax_id: str = "X1234567L") -> Justificante:
    body = f"{csv}-pdf".encode()
    source_pdf_sha256 = hashlib.sha256(body).hexdigest()
    return Justificante(
        csv=csv,
        modelo="303",
        period=Period.from_year_and_code(2025, "1T"),
        ejercicio="2025",
        presentation_id=None,
        presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
        tax_id=tax_id,
        total_a_ingresar=None,
        total_a_devolver=None,
        verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
        source_pdf_path=source_pdf_reference_path(source_pdf_sha256),
        source_pdf_sha256=source_pdf_sha256,
        parsed_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
    )


def _stamp_calendar_enrolment_from_censo() -> None:
    with open_test_profile_session(PRIMARY_PROFILE_ID):
        record = load_test_profile_record(PRIMARY_PROFILE_ID)
        censo_paths = {
            "iva.regime": CENSO_SOURCE_TAG,
            "taxpayer_type.entity_type": CENSO_SOURCE_TAG,
            "taxpayer_type.irpf_income_categories": CENSO_SOURCE_TAG,
        }
        facts = [
            fact.model_copy(update={"source": censo_paths[fact.path]}) if fact.path in censo_paths else fact
            for fact in record.facts
        ]
        if not any(fact.path == "activities.iae_epigraph" for fact in facts):
            facts.append(
                UserProfileFact(
                    path="activities.iae_epigraph",
                    value="763",
                    source=CENSO_SOURCE_TAG,
                ),
            )
        replace_test_profile_record(record.model_copy(update={"facts": tuple(facts)}))
