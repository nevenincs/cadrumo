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

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.ready_profile_support import seed_ready_profile
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.calculations.tests.filing_evidence import general_m303_filing_evidence
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.iva_compensation.reconciliation import (
    IvaCompensationAuthoritySource,
    IvaCompensationReconciliationDecision,
)
from .file_flow_test_support import calculation_ports_for_test
from .ready_profile_taxpayer import ready_profile_tax_id

_YEAR = filing_year_envelope().horizon
_FLOOR_YEAR = filing_year_envelope().floor

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLOCK = datetime(_YEAR, 5, 21, 9, 0, 0, tzinfo=UTC)
_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_TAXPAYER_NIF = ready_profile_tax_id()
_DECL_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "decl.ejercicio",
    surface="_DECL_EJERCICIO_CASILLA",
)
_DECL_PERIODO_CASILLA: CasillaId = validated_casilla_id(
    "decl.periodo",
    surface="_DECL_PERIODO_CASILLA",
)


@contextmanager
def _secure_backend(tmp_path: Path) -> Generator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_ready_profile(bucket_id=_BUCKET_ID, at=_CLOCK)
        yield


def _repositories():
    return (
        WorkUnitCatalogueRepository(),
        CalculationRevisionCatalogueRepository(),
        BucketEventHistoryRepository(),
    )


def _iva_compensation_zero_decision(*, filing_year: int, period: str) -> IvaCompensationReconciliationDecision:
    """Return a zero-amount IVA compensation decision so the new
    ``modelo-303-compensacion-pendiente-anteriores`` binding clears the
    wallet-reconciliation gate added by peer registry work without
    fabricating prior-period compensation that AEAT did not record."""
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=_TAXPAYER_NIF,
        target_year=filing_year,
        target_period=Period.from_year_and_code(filing_year, period),
        target_registry_snapshot_ref=published_authority_operation()
        .snapshot("303", filing_year=filing_year, period=period)
        .snapshot_ref,
        source_registry_snapshot_refs=(),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("0"),
        wallet_amount=Decimal("0"),
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason_identity="first_period_zero_aeat_wallet",
        authority_sources=(
            IvaCompensationAuthoritySource(
                source_kind="aeat_wallet",
                amount=Decimal("0"),
                source_locator="aeat-wallet:synthetic-fixture",
                captured_at=_CLOCK,
                registry_snapshot_refs=(),
            ),
        ),
        wallet_captured_at=_CLOCK,
        decided_at=_CLOCK,
    )


def _calculate_303(
    *, filing_year: int, period: str, period_date: date, tmp_path: Path, operation: PinnedAuthorityOperation
):
    with _secure_backend(tmp_path):
        snapshot = published_authority_operation().snapshot("303", filing_year=filing_year, period=period)
        typed_period = Period.from_year_and_code(filing_year, period)
        work_repo, calc_repo, event_repo = _repositories()
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=filing_year,
            period=typed_period,
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=work_repo,
                bucket_event_repository=BucketEventHistoryRepository(),
            ),
            clock=_CLOCK,
            operation=operation,
        )
        # Persist a zero-amount wallet-reconciliation decision so the new
        # ``modelo-303-compensacion-pendiente-anteriores`` binding clears the
        # gate added by peer registry work without fabricating prior-period
        # compensation that AEAT did not record.
        decision = _iva_compensation_zero_decision(filing_year=filing_year, period=period)
        IvaWalletDecisionRepository().save_decision(decision)
        with calculation_ports_for_test(
            bucket_id=work_repo.bucket_id,
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
        ) as _calculation_ports_174:
            return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                # The quarter's cuotas come from the bucket's IVA ledger, here empty.
                binding_values={},
                iva_compensation_decision=decision,
                filing_period_date=period_date,
                ports=_calculation_ports_174,
                clock=_CLOCK,
                filing_instance_evidence=general_m303_filing_evidence(
                    work_unit.period, reference="test:m303-declaration-period-binding", operation=operation
                ),
            ).revision


def test_modelo_303_declaration_year_resolves_from_work_unit_filing_year(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """``decl.ejercicio`` carries the work unit's filing year, not ``0``."""
    revision = _calculate_303(
        filing_year=_YEAR,
        period="1T",
        period_date=date(_YEAR, 3, 31),
        tmp_path=tmp_path,
        operation=operation,
    )
    assert revision.casilla_values[_DECL_EJERCICIO_CASILLA] == Decimal(_YEAR)


@pytest.mark.parametrize(
    ("period", "period_date", "expected_token"),
    [
        ("1T", date(_YEAR, 3, 31), "1T"),
        ("2T", date(_YEAR, 6, 30), "2T"),
        ("3T", date(_YEAR, 9, 30), "3T"),
        ("4T", date(_YEAR, 12, 31), "4T"),
    ],
)
def test_modelo_303_declaration_period_resolves_from_work_unit_period(
    period: str, period_date: date, expected_token: str, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """``decl.periodo`` carries the AEAT period token, on the string channel.

    ``decl.periodo`` is declared ``data_type = "period_code"``, whose registry
    validator accepts exactly the AEAT forms (``1T``-``4T`` here). The token is
    therefore persisted on ``input_values_by_casilla_id``, the strictly
    string-valued replay channel.

    The flat ``casilla_values`` projection remains Decimal-only, while the
    canonical observation envelope carries the real text scalar.
    """
    revision = _calculate_303(
        filing_year=_YEAR,
        period=period,
        period_date=period_date,
        tmp_path=tmp_path,
        operation=operation,
    )
    assert revision.input_values_by_casilla_id[_DECL_PERIODO_CASILLA] == expected_token
    assert _DECL_PERIODO_CASILLA not in revision.casilla_values
    observations = {obs.casilla_id: obs for obs in revision.observations}
    assert observations[_DECL_PERIODO_CASILLA].value == expected_token


def test_modelo_303_declaration_casillas_carry_registry_provenance(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The informational casillas land as grounded, value-faithful observations.

    A populated value with empty ``legal_refs`` / ``source_refs``
    would be a provenance-loss regression: the audit surface
    depends on every casilla carrying its registry grounding.

    ``decl.periodo`` keeps its grounded observation row and the real AEAT token;
    the Decimal-only flat projection intentionally omits it.
    """
    revision = _calculate_303(
        filing_year=_YEAR,
        period="2T",
        period_date=date(_YEAR, 6, 30),
        tmp_path=tmp_path,
        operation=operation,
    )
    observations = {obs.casilla_id: obs for obs in revision.observations}
    for casilla_id in (_DECL_EJERCICIO_CASILLA, _DECL_PERIODO_CASILLA):
        observation = observations[casilla_id]
        assert observation.formula_id is None
        assert observation.legal_refs
        assert observation.source_refs
    assert observations[_DECL_EJERCICIO_CASILLA].value == Decimal(_YEAR)
    assert observations[_DECL_PERIODO_CASILLA].value == "2T"
    assert _DECL_PERIODO_CASILLA not in revision.casilla_values
    assert revision.input_values_by_casilla_id[_DECL_PERIODO_CASILLA] == "2T"


def test_modelo_303_declaration_year_distinguishes_two_filing_years(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Two work units differing only by filing year resolve distinct ejercicio values.

    Anti-tautology: the value is read off the work unit, so a
    different work unit must yield a different ``decl.ejercicio``.
    """
    revision_floor = _calculate_303(
        filing_year=_FLOOR_YEAR,
        period="1T",
        period_date=date(_FLOOR_YEAR, 3, 31),
        tmp_path=tmp_path / "floor",
        operation=operation,
    )
    revision_horizon = _calculate_303(
        filing_year=_YEAR,
        period="1T",
        period_date=date(_YEAR, 3, 31),
        tmp_path=tmp_path / "horizon",
        operation=operation,
    )
    assert revision_floor.casilla_values[_DECL_EJERCICIO_CASILLA] == Decimal(_FLOOR_YEAR)
    assert revision_horizon.casilla_values[_DECL_EJERCICIO_CASILLA] == Decimal(_YEAR)
    assert (
        revision_floor.casilla_values[_DECL_EJERCICIO_CASILLA]
        != revision_horizon.casilla_values[_DECL_EJERCICIO_CASILLA]
    )
