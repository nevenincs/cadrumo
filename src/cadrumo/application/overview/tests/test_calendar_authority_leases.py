"""The calendar judges every obligation against the operation it was given.

Leasing the bundled authority once per modelo per period made a calendar cost
about a thousand leases, each re-hashing the authority descriptor. The lease
counter observes the real lease entry point without replacing it.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import date
from types import CodeType, FrameType

import pytest

from ....domain.calculations.registry.applicability import (
    REGISTRY_RESOLVED_APPLICABILITY_MODELOS,
    derive_modelo_applicability,
    iter_modelo_applicability_rules,
)
from ....domain.calculations.registry.authority import IndexedRegistryAuthority, PinnedAuthorityOperation
from ....domain.contribuyente.entity_type import EntityType
from ....domain.deadlines.models import IrpfEstimationRegime, IrpfIncomeCategory, IVARegime, TaxpayerProfile
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendarRange
from ..calendar_warnings import _derive_gating_fields
from ..coverage import build_obligation_coverage

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RANGE = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
_TODAY = date(2026, 4, 1)


def _lease_code() -> CodeType:
    wrapped = getattr(IndexedRegistryAuthority.operation, "__wrapped__", None)
    code = getattr(wrapped, "__code__", None)
    assert isinstance(code, CodeType), "the authority lease is no longer a generator context manager"
    return code


_LEASE_CODE = _lease_code()


def _autonomo() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.from_registry("natural_person"),
        irpf_income_categories=frozenset({IrpfIncomeCategory.from_registry("actividad_economica")}),
        irpf_estimation_regime=IrpfEstimationRegime.from_registry("directa_normal"),
        iva_regime=IVARegime("GENERAL"),
    )


class _LeaseCount:
    def __init__(self) -> None:
        self.entries = 0

    @property
    def leases(self) -> int:
        # The lease is a generator context manager: opening it enters the
        # generator once and closing it resumes the generator once more.
        return self.entries // 2


@contextmanager
def _counting_leases() -> Generator[_LeaseCount]:
    """Count entries into the authority lease, observing calls without altering them."""
    count = _LeaseCount()
    previous = sys.getprofile()

    def observe(frame: FrameType, event: str, arg: object) -> None:
        del arg
        if event == "call" and frame.f_code is _LEASE_CODE:
            count.entries += 1

    sys.setprofile(observe)
    try:
        yield count
    finally:
        sys.setprofile(previous)


def _leases_during(action: Callable[[], object]) -> int:
    with _counting_leases() as count:
        action()
    return count.leases


def test_a_calendar_does_not_lease_the_authority_per_obligation(operation: PinnedAuthorityOperation) -> None:
    profile = _autonomo()
    leases = _leases_during(
        lambda: build_overview_calendar(profile, _RANGE, today=_TODAY, operation=operation, show_suppressed=True)
    )

    # Every applicability helper the calendar reaches takes the held operation.
    assert leases == 0, f"{leases} authority leases for one calendar"


def test_the_counter_detects_a_lease_per_applicability_decision(operation: PinnedAuthorityOperation) -> None:
    del operation  # scopes the profile's tax-id vocabulary; the decisions below deliberately take none
    profile = _autonomo()
    # Only registry-resolved rules reach the authority; a seed-table rule needs no lease.
    modelos = tuple(sorted(REGISTRY_RESOLVED_APPLICABILITY_MODELOS))[:5]

    leases = _leases_during(lambda: [derive_modelo_applicability(profile, modelo, today=_TODAY) for modelo in modelos])

    assert len(modelos) == 5
    assert leases >= len(modelos), "an unpinned decision must show up as its own lease"


def test_the_held_operation_decides_exactly_as_a_fresh_lease_does(operation: PinnedAuthorityOperation) -> None:
    profile = _autonomo()
    calendar = build_overview_calendar(profile, _RANGE, today=_TODAY, operation=operation, show_suppressed=True)
    decided = {entry.modelo for entry in calendar.entries} | {row.modelo for row in calendar.suppressed_entries}

    assert decided
    for modelo in sorted(decided):
        held = derive_modelo_applicability(profile, modelo, operation=operation)
        leased = derive_modelo_applicability(profile, modelo)
        assert held == leased, modelo
    for row in calendar.suppressed_entries:
        assert row.verdict == derive_modelo_applicability(profile, row.modelo).verdict
    assert calendar.coverage == build_obligation_coverage(
        profile, {entry.modelo for entry in calendar.entries} | set(calendar.coverage.surfaced), today=_TODAY
    )


def test_the_rule_table_is_read_under_one_lease() -> None:
    """TEETH: resolving the applicability table must not lease the authority per modelo."""
    rules: list[object] = []
    leases = _leases_during(lambda: rules.extend(iter_modelo_applicability_rules()))

    assert len([rule for rule in rules if getattr(rule, "modelo", None) in REGISTRY_RESOLVED_APPLICABILITY_MODELOS]) > 1
    assert leases == 1


def test_a_held_operation_reads_the_rule_table_and_gating_keys_without_leasing(
    operation: PinnedAuthorityOperation,
) -> None:
    leases = _leases_during(
        lambda: (iter_modelo_applicability_rules(operation=operation), _derive_gating_fields(operation=operation))
    )

    assert leases == 0
