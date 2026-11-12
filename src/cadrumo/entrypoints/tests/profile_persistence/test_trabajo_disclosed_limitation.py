"""The uncomputed work-income deduction is served as a disclosed limitation, apart from an ordinary check.

The marker comes from the producer that leaves the deduction out, on a real payer record in an
isolated encrypted profile and the bundled authority, and it never blocks.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.tests.retencion_soportada_seed import seed_payer_certificate
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
)
from ....application.modelo.trabajo_income_findings import trabajo_income_findings
from ....application.modelo.verification_projection import ModeloFindingSnapshot
from ....application.modelo.verification_report_public_facts import ModeloVerificationFindingProjection
from ....application.modelo.work_review_contracts import ModeloWorkReviewFindingSnapshot
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.retencion_soportada import RetencionSoportadaClase
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ....domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from ....domain.user_profile.values import UserProfileFact
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import seeded_operator_work

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FACTS = (UserProfileFact(path="tax_residence.ccaa", value="madrid"), *RENTA_UNMARRIED_TAXPAYER_FACTS)
_CARRIES = (
    "renta-base-liquidable-negativa-general-anterior",
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
)
_LIMITATION_SUFFIX = "trabajo_deduction_not_computed"


def _attest(binding_id: str) -> ModeloBindingEditIntentV1:
    return ModeloBindingEditIntentV1(
        address=ModeloEditBindingAddressV1(binding_id=binding_id), kind=ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT
    )


def _findings(tmp_path: Path) -> tuple[ModeloVerificationFinding, ...]:
    year = newest_authored_edition("100")
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as work,
    ):
        seed_payer_certificate(
            operation=work.operation,
            taxpayer_tax_id="00000000T",
            ejercicio=year,
            payer_tax_id="B00000001",
            income_class=RetencionSoportadaClase.TRABAJO,
            retencion=Decimal("1200.00"),
            importe_integro_dinerario=Decimal("20300.00"),
            gastos_deducibles=Decimal("610.00"),
        )
        assert work.apply(binding=tuple(_attest(binding_id) for binding_id in _CARRIES)).refusal is None
        unit = work.work_unit
        revision = work.operation.snapshot(
            "100", filing_year=unit.filing_year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
        ).revision
        return trabajo_income_findings(
            str(unit.modelo),
            revision,
            work.require_head(),
            profile_values={},
            effective_date=date(unit.filing_year, 12, 31),
            operation=work.operation,
        )


def test_the_uncomputed_deduction_is_marked_and_nothing_else_is(tmp_path: Path) -> None:
    findings = _findings(tmp_path)
    limitations = [f for f in findings if f.message_locale_key.endswith(_LIMITATION_SUFFIX)]
    assert len(limitations) == 1
    assert limitations[0].disclosed_limitation is True
    assert limitations[0].severity is ModeloVerificationFindingSeverity.WARNING
    # The statement boxes the filer must state still block, and are ordinary checks.
    blocking = [f for f in findings if f.severity is ModeloVerificationFindingSeverity.BLOCKING]
    assert blocking
    assert all(not f.disclosed_limitation for f in findings if f not in limitations)


def test_every_served_mirror_carries_the_marker(tmp_path: Path) -> None:
    limitation = next(f for f in _findings(tmp_path) if f.message_locale_key.endswith(_LIMITATION_SUFFIX))
    for mirror in (
        ModeloFindingSnapshot.from_finding(limitation),
        ModeloWorkReviewFindingSnapshot.from_finding(limitation),
        ModeloVerificationFindingProjection.from_finding(limitation),
    ):
        assert mirror.disclosed_limitation is True
        assert mirror.model_dump(mode="json")["disclosed_limitation"] is True
        assert mirror.to_finding() == limitation


def test_an_ordinary_advisory_is_unmarked_in_every_mirror() -> None:
    ordinary = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.dt12a_reduccion_possible",
        legal_refs=("ley-35-2006:art-19",),
    )
    for mirror in (
        ModeloFindingSnapshot.from_finding(ordinary),
        ModeloWorkReviewFindingSnapshot.from_finding(ordinary),
        ModeloVerificationFindingProjection.from_finding(ordinary),
    ):
        assert mirror.disclosed_limitation is False
        assert "disclosed_limitation" not in mirror.model_dump(mode="json")
        assert mirror.to_finding() == ordinary
