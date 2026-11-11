"""The dependency read judges a stated prior figure exactly as verification does.

A first-quarter Modelo 130 reads the previous ejercicio's net activity income from
that year's Modelo 100 (RIRPF art. 110.3.c). When the filer states that figure for a
Modelo 100 the profile holds nowhere, verification admits the dependency on the
statement; the registered dependency read must show the same dependency clean. A
figure merely typed over the carry is no statement, and the dependency stays open.

Real behaviour throughout: an isolated encrypted profile, the bundled authority, the
production edit executor, the production dependency composition and executor, with
every year taken from the published support envelope.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from ....application.modelo.dependency_operation import ModeloDependencyExecutor, ModeloDependencyRequest
from ....application.modelo.dependency_projection import DependencyEvidenceSnapshot
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
)
from ....application.operations.public_period import PublicPeriod
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ...adapter_composition import profile_adapter_composition
from ...modelo_dependency_composition import build_dependency_read_ports
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BINDING = "irpf.previous_year_economic_activity_net_income"


def _year_inside_the_envelope() -> int:
    support = published_supported_filing_years()
    assert support is not None
    # The year after the floor reads a Modelo 100 of the floor, which the envelope admits.
    return support.floor + 1


def _apply(work: SeededOperatorWork, kind: ModeloEditBindingIntentKind) -> None:
    intent = ModeloBindingEditIntentV1(
        address=ModeloEditBindingAddressV1(binding_id=_BINDING), kind=kind, value=Decimal("12846.30")
    )
    assert work.apply(binding=(intent,)).refusal is None


def _prior_renta_dependency(work: SeededOperatorWork) -> DependencyEvidenceSnapshot:
    """Read the declaration's dependencies through the registered read, and return its Modelo 100 one."""
    unit = work.work_unit
    request = ModeloDependencyRequest(
        profile_id=UUID(unit.bucket_id),
        filing_year=unit.filing_year,
        modelo="130",
        period=PublicPeriod(filing_year=unit.filing_year, code=unit.period.registry_token),
    )
    result = ModeloDependencyExecutor(build_dependency_read_ports)._capture(request, work.operation)
    clean_state = result.snapshot.clean_state
    assert clean_state is not None
    (dependency,) = [item for item in clean_state.dependencies if item.source_modelo == "100"]
    return dependency


def test_a_stated_figure_reads_clean_in_the_dependency_read(tmp_path: Path) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=_year_inside_the_envelope(), period_code="1T") as work,
    ):
        _apply(work, ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE)
        dependency = _prior_renta_dependency(work)

    assert dependency.clean is True
    assert dependency.blockers == ()


def test_a_figure_merely_typed_stays_open_in_the_dependency_read(tmp_path: Path) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=_year_inside_the_envelope(), period_code="1T") as work,
    ):
        _apply(work, ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE)
        dependency = _prior_renta_dependency(work)

    assert dependency.clean is False
    assert dependency.blockers
