"""The register as the year's last Modelo 303 leaves it, derived from the revision's own casillas.

The expected entries are stated from the law (LIVA art. 105.Cuatro: the definitive
percentage is the year's volume with the right to deduct over its total; RIVA art.
28.1.2º: an especial option stands for at least three years), never copied from a run.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import open_ended_revision

from ....application.calculations.tests.filing_evidence import general_m303_filing_evidence
from ....core.casilla_id import CasillaId
from ....core.period import Period
from ....core.prorrata_register import (
    ProrrataEspecialTransitionKind,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.prorrata_register.register import (
    ProrrataEspecialTransitionEvidence,
    ProrrataRegister,
    ProrrataRegisterEntry,
    SectorDefinition,
)
from ..settlement import (
    PRORRATA_PORCENTAJE_CASILLA,
    PRORRATA_SETTLEMENT_ESPECIAL_CONTINUATION_LOCALE_KEY,
    PRORRATA_VOLUMEN_CON_DERECHO_CASILLA,
    PRORRATA_VOLUMEN_TOTAL_CASILLA,
    ProrrataSettlementEspecialContinuationError,
    settled_prorrata_register,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEAR = open_ended_revision("303").valid_from.year
_BUCKET = "settlement-register-test"
_NOW = datetime(_YEAR, 1, 1, tzinfo=UTC)


def _work_unit(operation: PinnedAuthorityOperation, period_code: str) -> tuple[WorkUnit, RegistrySnapshotRef]:
    period = Period.from_year_and_code(_YEAR, period_code)
    snapshot = operation.snapshot("303", filing_year=_YEAR, period=period.registry_token)
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET, modelo="303", filing_year=_YEAR, period=period, revision_id=snapshot.revision.id
        ),
        bucket_id=_BUCKET,
        modelo=ModeloCode("303"),
        filing_year=_YEAR,
        period=period,
        revision_id=snapshot.revision.id,
        name=f"303-{_YEAR}-{period_code}",
        created_at=_NOW,
        updated_at=_NOW,
        current_calculation_revision_id=None,
    )
    ref = RegistrySnapshotRef(
        modelo="303", revision_id=snapshot.revision.id, modelo_year=_YEAR, period=period.registry_token
    )
    return unit, ref


def _revision(
    operation: PinnedAuthorityOperation, unit: WorkUnit, ref: RegistrySnapshotRef, values: dict[CasillaId, Decimal]
) -> CalculationRevision:
    evidence = general_m303_filing_evidence(unit.period, reference="test:settlement", operation=operation)
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values=values,
            source_transaction_ids=(),
            filing_instance_evidence=evidence,
            source_provenance=(),
        ),
        work_unit_id=unit.work_unit_id,
        registry_snapshot_ref=ref,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=values,
        observations=tuple(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                legal_refs=("ley-37-1992:art-104", "ley-37-1992:art-105"),
                source_refs=("modelo-303-prorrata-settlement-test",),
            )
            for casilla_id, value in values.items()
        ),
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="aeat.test.modelo.verify",
        filing_instance_evidence=evidence,
        source_provenance=(),
    )


def _settlement(total: str, con_derecho: str, percentage: str) -> dict[CasillaId, Decimal]:
    return {
        PRORRATA_VOLUMEN_TOTAL_CASILLA: Decimal(total),
        PRORRATA_VOLUMEN_CON_DERECHO_CASILLA: Decimal(con_derecho),
        PRORRATA_PORCENTAJE_CASILLA: Decimal(percentage),
    }


def _entry(
    year: int,
    regime: str,
    *,
    transition: ProrrataEspecialTransitionKind | None = None,
    sector_id: str | None = None,
) -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(
        ejercicio=year,
        regime=ProrrataRegisterRegime.from_registry(regime),
        especial_transition=None
        if transition is None
        else ProrrataEspecialTransitionEvidence(kind=transition, evidence_reference=f"test:settlement:{year}"),
        sector_id=sector_id,
        source_registry_snapshot_refs=(),
    )


@pytest.mark.parametrize(
    ("total", "con_derecho", "percentage", "regime", "sin_derecho"),
    [
        ("200000.00", "150000.00", "75", "general", "50000.00"),
        ("80000.00", "80000.00", "100", "ninguna", "0.00"),
    ],
)
def test_an_empty_register_gains_the_entry_the_return_states(
    operation: PinnedAuthorityOperation,
    total: str,
    con_derecho: str,
    percentage: str,
    regime: str,
    sin_derecho: str,
) -> None:
    unit, ref = _work_unit(operation, "4T")
    revision = _revision(operation, unit, ref, _settlement(total, con_derecho, percentage))

    settled = settled_prorrata_register(ProrrataRegister(), revision=revision, work_unit=unit, operation=operation)

    assert settled is not None
    (entry,) = settled.entries
    assert (entry.ejercicio, entry.sector_id) == (_YEAR, None)
    assert entry.regime == ProrrataRegisterRegime.from_registry(regime)
    assert entry.especial_transition is None
    assert entry.definitive_percentage == Decimal(percentage)
    assert entry.definitive_volume_con_derecho == Decimal(con_derecho)
    assert entry.definitive_volume_sin_derecho == Decimal(sin_derecho)
    assert entry.source_registry_snapshot_refs == (ref,)
    assert settled.has_complete_current_entry_coverage(_YEAR)


def test_the_entry_an_election_already_holds_keeps_its_regime_and_transition(
    operation: PinnedAuthorityOperation,
) -> None:
    unit, ref = _work_unit(operation, "4T")
    revision = _revision(operation, unit, ref, _settlement("200000.00", "150000.00", "75"))
    option = ProrrataEspecialTransitionKind.from_registry("opcion")
    other_year = _entry(_YEAR - 3, "general")
    register = ProrrataRegister(entries=(other_year, _entry(_YEAR, "especial", transition=option)))

    settled = settled_prorrata_register(register, revision=revision, work_unit=unit, operation=operation)

    assert settled is not None
    assert settled.entry_for(_YEAR - 3) == other_year
    entry = settled.entry_for(_YEAR)
    assert entry is not None
    assert entry.regime == ProrrataRegisterRegime.from_registry("especial")
    assert entry.especial_transition is not None
    assert entry.especial_transition.kind == option
    assert entry.definitive_percentage == Decimal("75")
    assert entry.definitive_volume_sin_derecho == Decimal("50000.00")
    assert entry.source_registry_snapshot_refs == (ref,)
    assert len(settled.entries) == len(register.entries)


def test_a_year_after_an_especial_year_is_not_settled_into_an_undeclared_general_entry(
    operation: PinnedAuthorityOperation,
) -> None:
    unit, ref = _work_unit(operation, "4T")
    revision = _revision(operation, unit, ref, _settlement("200000.00", "150000.00", "75"))
    register = ProrrataRegister(entries=(_entry(_YEAR - 1, "especial"),))

    with pytest.raises(ProrrataSettlementEspecialContinuationError) as refusal:
        settled_prorrata_register(register, revision=revision, work_unit=unit, operation=operation)

    assert str(refusal.value) == PRORRATA_SETTLEMENT_ESPECIAL_CONTINUATION_LOCALE_KEY
    assert refusal.value.context == {"filing_year": _YEAR, "prior_filing_year": _YEAR - 1}

    declared = ProrrataRegister(entries=(*register.entries, _entry(_YEAR, "especial")))
    settled = settled_prorrata_register(declared, revision=revision, work_unit=unit, operation=operation)
    assert settled is not None
    assert settled.entry_for(_YEAR) is not None


def test_a_sector_register_stays_uncovered_until_each_sector_declares_the_year(
    operation: PinnedAuthorityOperation,
) -> None:
    unit, ref = _work_unit(operation, "4T")
    revision = _revision(operation, unit, ref, _settlement("200000.00", "150000.00", "75"))
    sector = SectorDefinition(
        sector_id="retail", letra=SectorDiferenciadoLetra.from_registry("a"), member_activity_codes=("471",)
    )

    undeclared = settled_prorrata_register(
        ProrrataRegister(sector_definitions=(sector,)), revision=revision, work_unit=unit, operation=operation
    )
    declared = settled_prorrata_register(
        ProrrataRegister(entries=(_entry(_YEAR, "general", sector_id="retail"),), sector_definitions=(sector,)),
        revision=revision,
        work_unit=unit,
        operation=operation,
    )

    assert undeclared is not None
    assert not undeclared.has_complete_current_entry_coverage(_YEAR)
    assert declared is not None
    assert declared.has_complete_current_entry_coverage(_YEAR)


@pytest.mark.parametrize(
    "values",
    [
        {},
        {PRORRATA_PORCENTAJE_CASILLA: Decimal("75")},
        {
            PRORRATA_VOLUMEN_TOTAL_CASILLA: Decimal("200000.00"),
            PRORRATA_VOLUMEN_CON_DERECHO_CASILLA: Decimal("150000.00"),
        },
    ],
    ids=["no-casillas", "percentage-only", "volumes-only"],
)
def test_a_return_without_every_settlement_casilla_settles_nothing(
    operation: PinnedAuthorityOperation, values: dict[CasillaId, Decimal]
) -> None:
    unit, ref = _work_unit(operation, "4T")

    assert (
        settled_prorrata_register(
            ProrrataRegister(), revision=_revision(operation, unit, ref, values), work_unit=unit, operation=operation
        )
        is None
    )


def test_a_return_that_is_not_the_last_of_the_year_settles_nothing(operation: PinnedAuthorityOperation) -> None:
    unit, ref = _work_unit(operation, "1T")
    revision = _revision(operation, unit, ref, _settlement("200000.00", "150000.00", "75"))

    assert settled_prorrata_register(ProrrataRegister(), revision=revision, work_unit=unit, operation=operation) is None


def test_an_interrupted_year_is_left_as_declared(operation: PinnedAuthorityOperation) -> None:
    unit, ref = _work_unit(operation, "4T")
    revision = _revision(operation, unit, ref, _settlement("0.00", "0.00", "100"))
    interrupted = _entry(_YEAR, "ninguna").model_copy(update={"interrupted": True})

    assert (
        settled_prorrata_register(
            ProrrataRegister(entries=(interrupted,)), revision=revision, work_unit=unit, operation=operation
        )
        is None
    )
