"""A carry the caller already answers is not refused for an earlier return that cannot show it.

A Modelo 130 reads four boxes of the previous year's Modelo 100 (the net
income its minoración depends on), so a filer who completed the 130s holds a
stored Modelo 100 of that year showing those four boxes and nothing else. The
Modelo 100 of the next year carries the negative general base still pending
(Ley 35/2006 art. 50.3) from boxes that stored return does not show. Those
carries are unknown, never zero, so the resolver refuses to read them from it.
But when the filer has answered them in this declaration, the answer is the
value the calculation uses, and refusing the carry as unknown refused the
answer with it: the edit that held it could never be applied. A carry the
stored return does show still resolves, so an answer that differs from it
stays a disagreement the calculation records.

Real behaviour throughout: real encrypted-SQLite observation store, real
registry authority, the production resolver, every Modelo 100 year the
registry's support envelope admits.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.aggregation.source_mesh import CalculationSourceContext, CalculationSourceResolution
from .....application.calculations.multi_year import PreviousFilingSourceResolver
from .....application.calculations.observations_repository import ObservationSourceKind
from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.modelo import Modelo
from .....core.period import Period
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.bindings import RegistryModeloObservation
from .....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError, RegistryValidationError
from .....domain.calculations.registry.ids import BindingId
from .....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from .....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_observations,
    revision_id_for_observation,
)
from ...storage.sql.secure_objects import SecureObjectRepository
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..calculation_observations import CalculationObservationRepository
from ..iva_compensation_history import IvaCompensationHistoryRepository
from .published_authority_support import published_authority_operation
from .relation_prefill_support import empty_profile_read_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "10006042-0000-4000-8000-000000000100"
_T0 = datetime(1980, 1, 10, 10, 0, tzinfo=UTC)
_MODELO = Modelo("100").value
#: The prior-year Modelo 100 boxes a Modelo 130 reads, all a 130 filer's store shows of that return.
_M130_READS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(token, surface="_M130_READS") for token in ("0224", "1479", "1553", "1577")
)


def _years_with_a_prior_return() -> tuple[int, ...]:
    """The Modelo 100 years the envelope admits whose previous year it admits too, so its return can be stored."""
    support = published_supported_filing_years()
    assert support is not None
    admitted: list[int] = []
    for year in sorted(support.years):
        try:
            _snapshot_for(year)
        except FilingYearOutsideSupportEnvelopeError:
            continue
        admitted.append(year)
    return tuple(year for year in admitted if year - 1 in admitted)


def _snapshot_for(year: int):
    return published_authority_operation().snapshot(
        _MODELO, filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    )


def _store_the_returns_130_reads(objects: SecureObjectRepository, *, year: int) -> None:
    observation = RegistryModeloObservation(
        modelo=_MODELO,
        filing_year=year,
        period="0A",
        observations=registry_grounded_observations(
            modelo=_MODELO,
            filing_year=year,
            period="0A",
            casilla_values=dict.fromkeys(_M130_READS, Decimal("0")),
        ),
    )
    repository = CalculationObservationRepository(objects=objects)
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind=ObservationSourceKind.APP_FILING,
            captured_at=_T0,
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )


def _resolve(
    objects: SecureObjectRepository,
    *,
    year: int,
    operation: PinnedAuthorityOperation,
    caller_binding_values: dict[BindingId, Decimal] | None = None,
) -> CalculationSourceResolution:
    snapshot = _snapshot_for(year)
    resolver = PreviousFilingSourceResolver(
        operation=operation,
        repository=CalculationObservationRepository(objects=objects),
        registry_snapshot=snapshot,
        iva_history_repository=IvaCompensationHistoryRepository(),
        profile_read_ports=empty_profile_read_ports(),
    )
    return resolver.resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo=_MODELO,
            filing_year=year,
            period=Period.from_year_and_code(year, "0A"),
            revision=snapshot.revision,
            caller_binding_values=caller_binding_values or {},
        ),
    )


@pytest.mark.parametrize("year", _years_with_a_prior_return())
def test_answered_carries_are_not_refused_for_a_return_that_cannot_show_them(
    tmp_path: Path, year: int, *, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _store_the_returns_130_reads(profile.repository, year=year - 1)

        with pytest.raises(RegistryValidationError) as refused:
            _resolve(profile.repository, year=year, operation=operation)
        context = refused.value.context or {}
        assert refused.value.translated_message == "errors.calc.previous_filing_casillas_unobserved"
        assert context["source_filing_year"] == year - 1
        unknown = tuple(str(context["binding_ids"]).split(","))
        assert "renta-base-liquidable-negativa-general-anterior" in unknown

        answered = dict.fromkeys(unknown, Decimal("0"))
        resolution = _resolve(profile.repository, year=year, operation=operation, caller_binding_values=answered)

    # The store holds nothing for them: the caller's answers are the values the calculation uses.
    assert not set(answered) & set(resolution.binding_values)
    assert set(answered) <= set(resolution.unresolved_binding_ids)
