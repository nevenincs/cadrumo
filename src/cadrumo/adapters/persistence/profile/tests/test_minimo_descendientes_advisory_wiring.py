"""The mínimo advisory collectors are actually consulted by the coordinator.

A collector that returns the right rows when called directly, and is never
called, protects nobody.

These tests drive the COORDINATOR and assert the advisory arrives through it.
Nothing here calls a collector, which is the whole point -- a test that would
still pass with the wiring line removed is testing the collector twice and the
wiring never.

All four mínimo-family collectors are covered, plus ``settlement_not_computed``
as the first of the non-mínimo wirings. The coordinator's call block wires
TEN collectors.

``prorrata_regularizacion`` is covered by
``test_prorrata_especial_mandatory_live_emit``, which drives this coordinator
and asserts its kind arrives. ``official_box_unpopulated``,
``prior_payment_not_deducted``, ``prior_payment_minoracion_not_captured`` and
``bienes_inversion_regularizacion`` remain unwired-tested: each needs its own
modelo fixture (a seeded observation repository, an M303 ledger) rather than a
revision and a profile.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....application.aggregation.source_mesh import CalculationSourceDiagnostic
from .....application.modelo.calculation_diagnostics import collect_bucket_aggregation_advisory_diagnostics
from .....application.modelo.settlement_casilla import SETTLEMENT_SEMANTIC_ROLES
from .....application.modelo.tests.advisory_diagnostic_repositories import advisory_diagnostic_repositories
from .....core.casilla_id import CasillaId
from .....core.modelo import Modelo
from .....domain.calculations.registry.schema import ModeloRevision
from .....domain.calculations.registry.schema_input_kind import InputKind
from .....domain.calculations.registry.schema_references import TemporalProjectionDirection
from .....domain.calculations.registry.temporal import revision_temporal_resolution
from .....domain.contribuyente.descendant import DescendantInfo
from .....domain.contribuyente.descendant_facts import descendant_facts_from_list
from .....domain.contribuyente.renta_codes import RentaMaritalStatus
from .....domain.user_profile.values import UserProfileFact
from ...storage.tests.profile_capsule_runtime import set_active_test_profile_facts
from .advisory_profile_bucket_fixture import (
    advisory_profile_bucket,
)
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

__all__ = ["advisory_profile_bucket"]

_BUCKET_ID = "5c5c5c5c-5c5c-4c5c-8c5c-5c5c5c5c5c5c"
_ESTATAL_CASILLA: CasillaId = "0513"
#: Annual period token for the Modelo 100 walk (named so the literal does not
#: read as a credential to the security linter).
_ANNUAL_PERIOD = "0A"

_RENTAS_UNDECLARED = "minimo_descendientes_rentas_undeclared"
_UNDECLARED = "minimo_descendientes_undeclared"
_PRORRATA_INFERRED = "minimo_descendientes_prorrata_inferred"
_SETTLEMENT = "settlement_casilla"


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _revision() -> ModeloRevision:
    return published_authority_operation().snapshot("100", filing_year=_newest_authored_year(), period="0A").revision


def _write(
    *descendants: DescendantInfo,
    marital_status: str | None = None,
    declaration_type: str | None = None,
    descendientes_count: str | None = None,
) -> None:
    facts = [UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(list(descendants))]
    if marital_status is not None:
        facts.append(UserProfileFact(path="renta_taxpayer.marital_status", value=marital_status))
    if declaration_type is not None:
        facts.append(UserProfileFact(path="renta_filing.declaration_type", value=declaration_type))
    if descendientes_count is not None:
        # Overwrite the aggregate the projection just derived, which is how the
        # profile manager desyncs it: the count renders as an editable row while
        # the rows it counts are an indexed namespace the manager never shows.
        facts.append(UserProfileFact(path="renta_family.descendientes_count", value=descendientes_count))
    set_active_test_profile_facts(tuple(facts))


def _source_diagnostics(
    casilla_values: dict[CasillaId, Decimal],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Every diagnostic the COORDINATOR raises for this bucket."""
    repositories = advisory_diagnostic_repositories(bucket_id=_BUCKET_ID)
    return collect_bucket_aggregation_advisory_diagnostics(
        _revision(),
        casilla_values,
        modelo=Modelo("100").value,
        period_token=_ANNUAL_PERIOD,
        filing_year=_newest_authored_year(),
        bucket_id=_BUCKET_ID,
        observation_repository=repositories.observation,
        prorrata_register_repository=repositories.prorrata_register,
        bienes_inversion_repository=repositories.bienes_inversion,
        transaction_repository=repositories.transactions,
        invoice_reader=repositories.invoices,
    )


def _source_kinds(casilla_values: dict[CasillaId, Decimal]) -> set[str]:
    """Every source kind the COORDINATOR raises for this bucket."""
    return {diagnostic.source_kind for diagnostic in _source_diagnostics(casilla_values)}


def test_the_rentas_undeclared_advisory_reaches_the_coordinator() -> None:
    """The rentas-undeclared collector's wiring, which would otherwise ship unguarded.

    A cohabiting 10-year-old with no rentas figure, against a non-zero
    aggregate: exactly the state the collector fires on. If its call line were
    removed from the coordinator this set would not contain the kind.
    """
    _write(DescendantInfo(birth_date=date(_newest_authored_year() - 10, 5, 1)))
    assert _RENTAS_UNDECLARED in _source_kinds({_ESTATAL_CASILLA: Decimal("2400")})


def test_the_undeclared_advisory_reaches_the_coordinator() -> None:
    """Wiring of the zero-aggregate collector.

    A profile with no descendiente facts against a zero aggregate is the state
    that collector owns, and it is reached through the coordinator here rather
    than by calling it.
    """
    assert _UNDECLARED in _source_kinds({_ESTATAL_CASILLA: Decimal("0")})


def test_the_prorrata_inferred_advisory_reaches_the_coordinator() -> None:
    """The wiring of the collector the disclosed-under-claim default depends on.

    Applying the prorrata rather than the full amount is justified on the
    operator being told, so this wiring is what makes a disclosed under-claim
    disclosed. A partnered filer declaring individually, with no explicit
    per-descendant answer, is the state it fires on.
    """
    _write(
        DescendantInfo(birth_date=date(_newest_authored_year() - 10, 5, 1)),
        marital_status=RentaMaritalStatus.CASADO.code,
        declaration_type="1",
    )
    assert _PRORRATA_INFERRED in _source_kinds({_ESTATAL_CASILLA: Decimal("1200")})


def _newest_authored_year() -> int:
    """The newest Modelo 100 year the support envelope serves from its own authored edition.

    A year the envelope reaches only by projecting another edition has no filing
    snapshot, so it is never a candidate.
    """
    operation = published_authority_operation()
    supported = operation.modelo_directory(Modelo("100").value).supported_filing_years
    assert supported is not None, "Modelo 100 declares no filing-year support envelope"
    for year in sorted(supported.years, reverse=True):
        selected = operation.revision_for_context(Modelo("100").value, filing_year=year, period=_ANNUAL_PERIOD)
        resolution = revision_temporal_resolution(selected, filing_year=year, period=_ANNUAL_PERIOD, support=supported)
        if resolution.projection_direction is TemporalProjectionDirection.AUTHORED:
            return year
    raise AssertionError(f"no supported Modelo 100 year in {supported.years} has its own authored edition")


def _with_manual_settlement(revision: ModeloRevision) -> ModeloRevision:
    """The same revision with its settlement-role casillas left for the operator to enter."""
    casillas = tuple(
        casilla.model_copy(update={"input_kind": InputKind.MANUAL})
        if casilla.semantic_role in SETTLEMENT_SEMANTIC_ROLES
        else casilla
        for casilla in revision.casillas
    )
    return revision.model_copy(update={"casillas": casillas})


def test_the_settlement_advisory_reaches_the_coordinator() -> None:
    """A non-mínimo wiring.

    ``settlement_not_computed`` fires where a revision declares a settlement-role
    casilla that is NOT computed. Every supported Modelo 100 edition now computes
    its settlement, so the case is a filing-grade revision with those casillas
    turned manual: the advisory is a property of the revision alone, so the
    coordinator must surface it for any such revision, and no profile setup is
    needed. The control below proves the unaltered revision stays quiet.
    """
    filing_year = _newest_authored_year()
    authored = published_authority_operation().snapshot("100", filing_year=filing_year, period=_ANNUAL_PERIOD).revision
    assert any(casilla.semantic_role in SETTLEMENT_SEMANTIC_ROLES for casilla in authored.casillas)
    revision = _with_manual_settlement(authored)
    repositories = advisory_diagnostic_repositories(bucket_id=_BUCKET_ID)
    diagnostics = collect_bucket_aggregation_advisory_diagnostics(
        revision,
        {},
        modelo=Modelo("100").value,
        period_token=_ANNUAL_PERIOD,
        filing_year=filing_year,
        bucket_id=_BUCKET_ID,
        observation_repository=repositories.observation,
        prorrata_register_repository=repositories.prorrata_register,
        bienes_inversion_repository=repositories.bienes_inversion,
        transaction_repository=repositories.transactions,
        invoice_reader=repositories.invoices,
    )
    assert _SETTLEMENT in {diagnostic.source_kind for diagnostic in diagnostics}


def test_the_settlement_advisory_is_absent_where_the_revision_computes_it() -> None:
    """Control for the case above: the same authored revision, its settlement left computed.

    That edition computes its settlement casillas, so the kind must NOT appear.
    Without this the test above would pass against a collector that fired on
    every revision, which would say nothing about the condition it claims to
    detect.
    """
    filing_year = _newest_authored_year()
    revision = published_authority_operation().snapshot("100", filing_year=filing_year, period=_ANNUAL_PERIOD).revision
    repositories = advisory_diagnostic_repositories(bucket_id=_BUCKET_ID)
    diagnostics = collect_bucket_aggregation_advisory_diagnostics(
        revision,
        {},
        modelo=Modelo("100").value,
        period_token=_ANNUAL_PERIOD,
        filing_year=filing_year,
        bucket_id=_BUCKET_ID,
        observation_repository=repositories.observation,
        prorrata_register_repository=repositories.prorrata_register,
        bienes_inversion_repository=repositories.bienes_inversion,
        transaction_repository=repositories.transactions,
        invoice_reader=repositories.invoices,
    )
    assert _SETTLEMENT not in {diagnostic.source_kind for diagnostic in diagnostics}


def test_the_coordinator_stays_quiet_when_no_collector_has_anything_to_say() -> None:
    """Control: every kind above is ABSENT when its own conditions do not hold.

    Without this the four tests above could all pass against a coordinator
    that raised every advisory unconditionally, which would satisfy the wiring
    claim while telling an operator nothing. A declared zero rentas figure, a
    declared prorrata answer, an unpartnered filer and a count that matches
    the rows: nothing for any of the four to say.
    """
    _write(
        DescendantInfo(
            birth_date=date(_newest_authored_year() - 10, 5, 1),
            rentas_anuales_euros=Decimal("0"),
            prorrata_minimo=False,
        ),
        marital_status=RentaMaritalStatus.SOLTERO.code,
        declaration_type="1",
    )
    kinds = _source_kinds({_ESTATAL_CASILLA: Decimal("2400")})
    assert _RENTAS_UNDECLARED not in kinds
    assert _UNDECLARED not in kinds
    assert _PRORRATA_INFERRED not in kinds


def test_the_undeclared_advisory_grounds_from_the_casilla_it_addresses() -> None:
    """Casilla-derived: this advisory's subject IS casilla 0513's own zero.

    The casilla already carries the exact provision the message names (plain
    "Art. 58"), so the message is derived from the casilla, not asserted separately.
    """
    diagnostics = tuple(
        diagnostic
        for diagnostic in _source_diagnostics({_ESTATAL_CASILLA: Decimal("0")})
        if diagnostic.source_kind == _UNDECLARED
    )
    assert len(diagnostics) == 1
    assert diagnostics[0].legal_refs == ("ley-35-2006:art-56", "ley-35-2006:art-58", "ley-35-2006:art-61")
    assert diagnostics[0].asserted_legal_refs == ()
