"""Live source resolver tests for ``prorrata_regularizacion``.

These tests exercise the source-mesh resolver without enrolling it in the mesh:
the resolver consumes current-year registry values supplied by the
materialisation seam and reads the real encrypted prorrata register, filed
Modelo 303 observations and transaction ledger. The AEAT manual's full
regularisation, which needs a real ledger across four quarters, is proven end
to end in ``entrypoints/tests/profile_persistence``; here each refusal and the
Modelo 390 restatement are pinned in isolation.

See Also:
    :class:`~application.calculations.prorrata_regularizacion.ProrrataRegularizacionSourceResolver`
        Live resolver under test for the prorrata regularización source.
    :class:`~adapters.persistence.profile.prorrata_register.ProrrataRegisterRepository`
        Encrypted profile-scoped carry store used by the register-backed branch.
    :class:`~application.aggregation.CalculationSourceContext`
        Source-mesh context passed into resolver execution.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from .....application.aggregation.source_mesh import CalculationSourceContext, CalculationSourceResolution
from .....application.calculations.observations_repository import ResultDispositionProjection
from .....application.calculations.prorrata_regularizacion import ProrrataRegularizacionSourceResolver
from .....core.aggregation import BindingSourceKind
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.i18n.render import tr as render_tr
from .....core.modelo import Modelo
from .....core.period import Period
from .....core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from .....core.result_disposition import ResultDisposition
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.binding_targets import sole_bound_casilla
from .....domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_RESULTADO_CASILLA as M303_RESULTADO_CASILLA,
)
from .....domain.calculations.registry.schema import RegistrySnapshot
from .....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_modelo_observation,
    revision_id_for_observation,
)
from .....domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry
from ...storage.tests.secure_sql import isolated_runtime_profile, isolated_two_bucket_runtime
from ..calculation_observations import CalculationObservationRepository
from ..prorrata_register import ProrrataRegisterRepository
from ..transactions import TransactionCatalogueRepository
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "ca06894b-1eb7-4f25-b325-531f43bc0e48"
_FILING_YEAR = 2025
_PRIOR_YEAR = _FILING_YEAR - 1
_CAPTURED_AT = datetime(2026, 1, 20, 10, 0, tzinfo=UTC)
_KEY = "application.calculations.prorrata_regularizacion.unresolved"

_VOLUMEN_CON_DERECHO_ID: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="test casilla id",
)
_VOLUMEN_TOTAL_ID: CasillaId = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")
_PORCENTAJE_ID: CasillaId = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")
_SOPORTADO_INTERIORES_ID: CasillaId = validated_casilla_id("iva.soportado.interiores", surface="test casilla id")
_REGULARIZACION_ID: CasillaId = validated_casilla_id("44", surface="test casilla id")
#: Every deducible cuota box of the 2025 Modelo 303 design, in declaration
#: order, as a filed liquidation records it. A local filing persists every casilla, so a quarter
#: with no input IVA files each of these as zero.
_DEDUCIBLE_CUOTA_IDS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(raw, surface="test casilla id")
    for raw in (
        "35",
        "39",
        "iva.soportado.interiores",
        "iva.autorepercutido.interior.deducible",
        "iva.autorepercutido.intracomunitaria.deducible",
        "iva.soportado.importaciones",
        "iva.soportado.interiores.bienes-inversion",
        "iva.autorepercutido.interior.deducible.bienes-inversion",
        "iva.rectificacion-deducciones.interiores",
        "iva.rectificacion-deducciones.importaciones",
        "iva.rectificacion-deducciones.inversion-sujeto-pasivo",
    )
)

#: Manual práctico de IVA 2025, pp. 137-138: provisional 73%; 25.000 con
#: derecho over 45.000 total give a definitive 56% (art. 104.Dos rounds 55,56
#: up); the box the manual files is -217,60.
_MANUAL_PROVISIONAL_PERCENTAGE = Decimal("73")
_MANUAL_CON_DERECHO = Decimal("25000.00")
_MANUAL_TOTAL = Decimal("45000.00")
_MANUAL_DEFINITIVE_PERCENTAGE = Decimal("56")
_MANUAL_CASILLA_44_REGULARIZACION = Decimal("-217.60")
_M303_BINDING_ID = "modelo-303-prorrata-regularizacion-casilla-44"
_M390_BINDING_ID = "modelo-390-prorrata-regularizacion-anual"


def _current_year_values() -> dict[CasillaId, Decimal]:
    return {
        _VOLUMEN_CON_DERECHO_ID: _MANUAL_CON_DERECHO,
        _VOLUMEN_TOTAL_ID: _MANUAL_TOTAL,
        _PORCENTAJE_ID: _MANUAL_DEFINITIVE_PERCENTAGE,
    }


def _snapshot(modelo: str, period: str) -> RegistrySnapshot:
    return published_authority_operation().snapshot(modelo, filing_year=_FILING_YEAR, period=period)


def _context(
    snapshot: RegistrySnapshot,
    *,
    modelo: str,
    period: str,
    bucket_id: str = _BUCKET_ID,
) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, period),
        revision=snapshot.revision,
    )


def _register_with_carried_prior() -> ProrrataRegister:
    return ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(
                ejercicio=_FILING_YEAR,
                regime=ProrrataRegisterRegime.from_registry("general"),
                especial_transition=None,
                provisional_percentage=_MANUAL_PROVISIONAL_PERCENTAGE,
                provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
                source_observation_ref=f"{Modelo('303').value}:{_PRIOR_YEAR}:4T",
                source_registry_snapshot_refs=(
                    published_authority_operation().snapshot("303", filing_year=_PRIOR_YEAR, period="4T").snapshot_ref,
                ),
            ),
        ),
    )


def _save_m303_observation(
    repository: CalculationObservationRepository,
    *,
    period: str,
    casilla_values: dict[CasillaId, Decimal],
) -> None:
    observation = registry_grounded_modelo_observation(
        modelo=Modelo("303").value,
        filing_year=_FILING_YEAR,
        period=period,
        casilla_values={**casilla_values, M303_RESULTADO_CASILLA: Decimal("1")},
    )
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind="app_filing",
            captured_at=_CAPTURED_AT,
            result_disposition=ResultDispositionProjection(
                disposition=ResultDisposition.INGRESO,
                provenance_kind="app_filing",
                provenance_locator="test:prorrata-local-filing:declaration-type",
            ),
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )


def _resolve(
    profile_repository: Any,
    *,
    modelo: str,
    period: str,
    authority_operation: PinnedAuthorityOperation,
    register: ProrrataRegister | None = None,
    current_year_values: dict[CasillaId, Decimal] | None = None,
    undeclared: tuple[CasillaId, ...] = (),
    filed: dict[str, dict[CasillaId, Decimal]] | None = None,
    bucket_id: str = _BUCKET_ID,
) -> tuple[CalculationSourceResolution, RegistrySnapshot]:
    register_repository = ProrrataRegisterRepository(bucket_id=bucket_id, objects=profile_repository)
    observation_repository = CalculationObservationRepository(objects=profile_repository)
    if register is not None:
        register_repository.save(register)
    for filed_period, casilla_values in (filed or {}).items():
        _save_m303_observation(observation_repository, period=filed_period, casilla_values=casilla_values)
    snapshot = _snapshot(modelo, period)
    resolution = ProrrataRegularizacionSourceResolver(
        current_year_values=_current_year_values() if current_year_values is None else current_year_values,
        undeclared_current_year_casilla_ids=undeclared,
        prorrata_register_repository=register_repository,
        observation_repository=observation_repository,
        transaction_repository=TransactionCatalogueRepository(bucket_id=bucket_id, objects=profile_repository),
        registry_snapshot=snapshot,
        operation=authority_operation,
    ).resolve(_context(snapshot, modelo=modelo, period=period, bucket_id=bucket_id))
    return resolution, snapshot


def _sole_unresolved_message(resolution: CalculationSourceResolution, binding_id: str) -> str:
    assert resolution.binding_values == {}
    assert resolution.unresolved_binding_ids == (binding_id,)
    assert len(resolution.diagnostics) == 1
    diagnostic = resolution.diagnostics[0]
    assert diagnostic.reason == "unresolved_binding"
    assert diagnostic.binding_source is BindingSourceKind.PRORRATA_REGULARIZACION
    assert diagnostic.binding_id == binding_id
    return diagnostic.message


def test_resolver_refuses_construction_without_an_explicit_prorrata_repository() -> None:
    """The dependency is mandatory; callers cannot re-enter a hidden default path."""
    with pytest.raises(TypeError, match="prorrata_register_repository"):
        cast(Any, ProrrataRegularizacionSourceResolver)(current_year_values=_current_year_values())


def test_resolver_refuses_construction_without_an_explicit_transaction_repository(tmp_path: Path) -> None:
    """The earlier liquidations' gross cuotas cannot come from an implicit active ledger."""
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile,
        pytest.raises(TypeError, match="transaction_repository"),
    ):
        cast(Any, ProrrataRegularizacionSourceResolver)(
            current_year_values=_current_year_values(),
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=profile.repository),
            observation_repository=CalculationObservationRepository(objects=profile.repository),
        )


def test_a_non_settlement_quarter_is_a_structural_zero(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The AEAT instructions fill the box only in the 4T or month 12; 3T carries a proven zero."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_3t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="3T",
            authority_operation=authority_operation,
            register=_register_with_carried_prior(),
        )

    assert resolution.binding_values == {_M303_BINDING_ID: Decimal("0.00")}
    assert resolution.unresolved_binding_ids == ()
    assert resolution.diagnostics == ()
    assert {row.source_ref for row in resolution.provenance} == {"303:2025:3T:prorrata-regularizacion-settlement-only"}


def test_settlement_without_a_provisional_source_is_unresolved(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Declared exempt volumes with no register value and no prior settlement stay unresolved."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    assert message == render_tr(f"{_KEY}.provisional_missing", year=_FILING_YEAR)


def test_settlement_with_a_missing_definitive_percentage_names_it(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A missing current-year value blocks resolution before any zero can be inferred."""
    current_year_values = _current_year_values()
    del current_year_values[_PORCENTAJE_ID]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_carried_prior(),
            current_year_values=current_year_values,
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    assert message == render_tr(f"{_KEY}.current_year_inputs", casillas=str(_PORCENTAJE_ID))


def test_undeclared_volumes_under_an_active_register_are_unresolved_not_zero(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The engine's default for an unsupplied volume is not a fact; prorrata applies, so refuse."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_carried_prior(),
            current_year_values={
                _VOLUMEN_CON_DERECHO_ID: Decimal("0"),
                _VOLUMEN_TOTAL_ID: Decimal("0"),
                _PORCENTAJE_ID: Decimal("100"),
            },
            undeclared=(_VOLUMEN_CON_DERECHO_ID, _VOLUMEN_TOTAL_ID),
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    assert message == render_tr(
        f"{_KEY}.volumes_undeclared",
        year=_FILING_YEAR,
        casillas=f"{_VOLUMEN_CON_DERECHO_ID}, {_VOLUMEN_TOTAL_ID}",
    )


def test_undeclared_volumes_without_prorrata_evidence_resolve_a_proven_zero(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """No register and no declared exempt volume: prorrata does not apply (LIVA art. 102.Uno)."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            current_year_values={
                _VOLUMEN_CON_DERECHO_ID: Decimal("0"),
                _VOLUMEN_TOTAL_ID: Decimal("0"),
                _PORCENTAJE_ID: Decimal("100"),
            },
            undeclared=(_VOLUMEN_CON_DERECHO_ID, _VOLUMEN_TOTAL_ID),
        )

    assert resolution.binding_values == {_M303_BINDING_ID: Decimal("0.00")}
    assert resolution.unresolved_binding_ids == ()


def test_unfiled_earlier_quarters_are_named(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The box regularises 1T-3T; with none filed it names each instead of reading zero."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_carried_prior(),
            filed={"2T": {_SOPORTADO_INTERIORES_ID: Decimal("0.00")}},
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    assert message == render_tr(f"{_KEY}.source_periods_missing", periods="1T, 3T")


def test_an_earlier_quarter_filed_without_its_deducible_boxes_is_refused(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The practised deduction is read box by box; an absent box is not read as zero."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_carried_prior(),
            filed={period: {_SOPORTADO_INTERIORES_ID: Decimal("0.00")} for period in ("1T", "2T", "3T")},
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    absent = ", ".join(str(casilla_id) for casilla_id in _DEDUCIBLE_CUOTA_IDS if casilla_id != _SOPORTADO_INTERIORES_ID)
    assert message == render_tr(f"{_KEY}.source_period_cuotas_missing", period="1T", casillas=absent)


def test_an_earlier_quarter_that_disagrees_with_the_ledger_is_refused(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A filed deduction the ledger cannot reproduce at the provisional percentage is not guessed at.

    1T filed 292,00 of deducible interior cuota -- the manual's first quarter at
    73% -- while the ledger holds no input IVA for the quarter. The gross base
    of that deduction is unknown, so the regularisation refuses and names the
    quarter, the box and both figures.
    """
    zero_quarter = dict.fromkeys(_DEDUCIBLE_CUOTA_IDS, Decimal("0.00"))
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_4t = _resolve(
            profile.repository,
            modelo=Modelo("303").value,
            period="4T",
            authority_operation=authority_operation,
            register=_register_with_carried_prior(),
            filed={
                "1T": {**zero_quarter, _SOPORTADO_INTERIORES_ID: Decimal("292.00")},
                "2T": zero_quarter,
                "3T": zero_quarter,
            },
        )

    message = _sole_unresolved_message(resolution, _M303_BINDING_ID)
    assert message == render_tr(
        f"{_KEY}.source_period_ledger_divergence",
        period="1T",
        casilla=str(_SOPORTADO_INTERIORES_ID),
        filed=Decimal("292.00"),
        expected=Decimal("0.00"),
        percentage=_MANUAL_PROVISIONAL_PERCENTAGE,
    )


def test_modelo_390_restates_the_filed_settlement_regularisation(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The annual field equals the 4T box the taxpayer filed, so 390 and 303 cannot disagree."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_0a = _resolve(
            profile.repository,
            modelo=Modelo("390").value,
            period="0A",
            authority_operation=authority_operation,
            filed={"4T": {_REGULARIZACION_ID: _MANUAL_CASILLA_44_REGULARIZACION}},
        )

    assert resolution.binding_values == {_M390_BINDING_ID: _MANUAL_CASILLA_44_REGULARIZACION}
    assert resolution.unresolved_binding_ids == ()
    assert resolution.diagnostics == ()
    assert {row.source_ref for row in resolution.provenance} == {"303:2025:4T:44"}


def test_modelo_390_reads_only_the_explicitly_injected_observation_store(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A settlement filed in the active primary profile cannot leak into the secondary's summary."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        primary_observations = CalculationObservationRepository(objects=runtime.primary.repository)
        _save_m303_observation(
            primary_observations, period="4T", casilla_values={_REGULARIZACION_ID: Decimal("-100.00")}
        )
        with runtime.switch_to_secondary():
            resolution, _snapshot_0a = _resolve(
                runtime.secondary.repository,
                modelo=Modelo("390").value,
                period="0A",
                authority_operation=authority_operation,
                filed={"4T": {_REGULARIZACION_ID: _MANUAL_CASILLA_44_REGULARIZACION}},
                bucket_id=runtime.secondary.bucket_id,
            )

    assert resolution.binding_values == {_M390_BINDING_ID: _MANUAL_CASILLA_44_REGULARIZACION}


def test_modelo_390_without_a_filed_settlement_names_every_terminal_period(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Neither a 4T nor a month-12 liquidation is filed: the annual field names both and its box."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, snapshot = _resolve(
            profile.repository,
            modelo=Modelo("390").value,
            period="0A",
            authority_operation=authority_operation,
        )

    message = _sole_unresolved_message(resolution, _M390_BINDING_ID)
    assert message == render_tr(f"{_KEY}.settlement_observation_missing", periods="4T, 12")
    box = sole_bound_casilla(snapshot.revision, _M390_BINDING_ID)
    assert box is not None, "the annual regularisation fills one box of the Modelo 390"
    assert resolution.diagnostics[0].casilla_id == box


def test_modelo_390_with_both_cadences_filed_is_ambiguous(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A 4T and a month-12 settlement cannot both be the year's last liquidation."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution, _snapshot_0a = _resolve(
            profile.repository,
            modelo=Modelo("390").value,
            period="0A",
            authority_operation=authority_operation,
            filed={
                "4T": {_REGULARIZACION_ID: _MANUAL_CASILLA_44_REGULARIZACION},
                "12": {_REGULARIZACION_ID: Decimal("-50.00")},
            },
        )

    message = _sole_unresolved_message(resolution, _M390_BINDING_ID)
    assert message == render_tr(f"{_KEY}.settlement_observation_ambiguous", periods="4T, 12")
