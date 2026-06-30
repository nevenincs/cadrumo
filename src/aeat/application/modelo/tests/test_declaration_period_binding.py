"""Declaration-period casilla resolution from work-unit metadata.

``decl.ejercicio`` / ``decl.periodo`` are ``informational`` casillas:
AEAT requires them on the filed declaration, but they are neither
operator-entered figures nor formula outputs. Their values come
entirely from the work unit's ``(filing_year, period)`` axes.

These tests prove the calculate path projects the work unit's
metadata onto the matching semantic-role casillas, so a Modelo 303
calculation no longer leaves ``ejercicio``/``periodo`` at ``0``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....core.resources import resources
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.calculations.registry import BindingId
from ....domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations._observations_repository import IvaWalletDecisionRepository
from ...user_profile import UserProfileLifecycleRepository
from .. import calculate_modelo_revision, create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 5, 21, 9, 0, 0, tzinfo=UTC)
_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_TAXPAYER_NIF = "12345678Z"
_DECL_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "decl.ejercicio",
    surface="_DECL_EJERCICIO_CASILLA",
)
_DECL_PERIODO_CASILLA: CasillaId = validated_casilla_id(
    "decl.periodo",
    surface="_DECL_PERIODO_CASILLA",
)


@contextmanager
def _secure_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        _seed_taxpayer_profile(runtime.repository)
        yield


def _seed_taxpayer_profile(objects: SecureObjectRepository) -> None:
    """Seed the bucket profile with the taxpayer NIF so the IVA wallet
    reconciliation gate added to ``calculate_modelo_revision`` resolves
    the work-unit taxpayer identity."""
    record = UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Test runtime profile",
        facts=(
            UserProfileFact(path="identity.tax_id", value=_TAXPAYER_NIF),
            UserProfileFact(path="identity.name", value="Test"),
            UserProfileFact(path="identity.surnames", value="Operator"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID, objects=objects).save(record)


def _repositories():
    return (
        WorkUnitCatalogueRepository(),
        CalculationRevisionCatalogueRepository(),
        BucketEventHistoryRepository(),
    )


def _modelo_303_engine_inputs() -> dict[BindingId, Decimal]:
    return {
        "modelo-303-iva-repercutido-general-cuota": Decimal("1000.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
        "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
    }


def _iva_compensation_zero_decision(*, filing_year: int, period: str) -> IvaCompensationReconciliationDecision:
    """Return a zero-amount IVA compensation decision so the new
    ``modelo-303-compensacion-pendiente-anteriores`` binding clears the
    wallet-reconciliation gate added by peer registry work without
    fabricating prior-period compensation that AEAT did not record."""
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=_TAXPAYER_NIF,
        target_year=filing_year,
        target_period=Period.from_year_and_code(filing_year, period),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("0"),
        wallet_amount=Decimal("0"),
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason="test fixture: zero prior compensation per AEAT wallet match",
        decided_at=_CLOCK,
    )


def _calculate_303(*, filing_year: int, period: str, period_date: date, tmp_path: Path):
    with _secure_backend(tmp_path):
        snapshot = resources().modelos.authority.snapshot("303", filing_year=filing_year, period=period)
        typed_period = Period.from_year_and_code(filing_year, period)
        work_repo, calc_repo, event_repo = _repositories()
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=filing_year,
            period=typed_period,
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_CLOCK,
        )
        # Persist a zero-amount wallet-reconciliation decision so the new
        # ``modelo-303-compensacion-pendiente-anteriores`` binding clears the
        # gate added by peer registry work without fabricating prior-period
        # compensation that AEAT did not record.
        decision = _iva_compensation_zero_decision(filing_year=filing_year, period=period)
        IvaWalletDecisionRepository().save_decision(decision)
        return calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values=_modelo_303_engine_inputs(),
            iva_compensation_decision=decision,
            filing_period_date=period_date,
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_CLOCK,
        )


def test_modelo_303_declaration_year_resolves_from_work_unit_filing_year(tmp_path: Path) -> None:
    """``decl.ejercicio`` carries the work unit's filing year, not ``0``."""
    revision = _calculate_303(
        filing_year=2025,
        period="1T",
        period_date=date(2025, 3, 31),
        tmp_path=tmp_path,
    )
    assert revision.casilla_values[_DECL_EJERCICIO_CASILLA] == Decimal("2025")


@pytest.mark.parametrize(
    ("period", "period_date", "expected_ordinal"),
    [
        ("1T", date(2026, 3, 31), Decimal("1")),
        ("2T", date(2026, 6, 30), Decimal("2")),
        ("3T", date(2026, 9, 30), Decimal("3")),
        ("4T", date(2026, 12, 31), Decimal("4")),
    ],
)
def test_modelo_303_declaration_period_resolves_from_work_unit_period(
    period: str,
    period_date: date,
    expected_ordinal: Decimal,
    tmp_path: Path,
) -> None:
    """``decl.periodo`` carries the work unit's quarter ordinal, not ``0``."""
    revision = _calculate_303(
        filing_year=2026,
        period=period,
        period_date=period_date,
        tmp_path=tmp_path,
    )
    assert revision.casilla_values[_DECL_PERIODO_CASILLA] == expected_ordinal


def test_modelo_303_declaration_casillas_carry_registry_provenance(tmp_path: Path) -> None:
    """The informational casillas land as typed observations with legal grounding.

    A populated value with empty ``legal_refs`` / ``source_refs``
    would be a provenance-loss regression: the audit surface
    depends on every casilla carrying its registry grounding.
    """
    revision = _calculate_303(
        filing_year=2025,
        period="2T",
        period_date=date(2025, 6, 30),
        tmp_path=tmp_path,
    )
    observations = {obs.casilla_id: obs for obs in revision.observations}
    for casilla_id in (_DECL_EJERCICIO_CASILLA, _DECL_PERIODO_CASILLA):
        observation = observations[casilla_id]
        assert observation.formula_id is None
        assert observation.legal_refs
        assert observation.source_refs
    assert observations[_DECL_EJERCICIO_CASILLA].value == Decimal("2025")
    assert observations[_DECL_PERIODO_CASILLA].value == Decimal("2")


def test_modelo_303_declaration_year_distinguishes_two_filing_years(tmp_path: Path) -> None:
    """Two work units differing only by filing year resolve distinct ejercicio values.

    Anti-tautology: the value is read off the work unit, so a
    different work unit must yield a different ``decl.ejercicio``.
    """
    revision_2024 = _calculate_303(
        filing_year=2024,
        period="1T",
        period_date=date(2024, 3, 31),
        tmp_path=tmp_path / "y2024",
    )
    revision_2026 = _calculate_303(
        filing_year=2026,
        period="1T",
        period_date=date(2026, 3, 31),
        tmp_path=tmp_path / "y2026",
    )
    assert revision_2024.casilla_values[_DECL_EJERCICIO_CASILLA] == Decimal("2024")
    assert revision_2026.casilla_values[_DECL_EJERCICIO_CASILLA] == Decimal("2026")
    assert (
        revision_2024.casilla_values[_DECL_EJERCICIO_CASILLA] != revision_2026.casilla_values[_DECL_EJERCICIO_CASILLA]
    )
