"""IVA compensation relation-prefill binding tests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.tests.iva_compensation_history_support import (
    BOX_85_BINDING,
    BOX_97_BINDING,
    BOX_662_BINDING,
    M303_COMPENSACION_APLICADA_CASILLA,
    M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    M303_DISPONIBLE_CASILLA,
    M303_GENERADA_CASILLA,
    M303_POSTERIOR_CASILLA,
    M303_PRINTED_COMPENSATION_REFERENCE_CASILLA,
    M303_RESULTADO_CASILLA,
    M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
    modelo_390_annual_snapshot,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext, CalculationSourceResolution
from cadrumo.application.calculations.iva_compensation_annual_partition import (
    IvaCompensationAnnualPartitionSourceResolver,
    resolve_iva_compensation_annual_partition_binding_values,
)
from cadrumo.application.calculations.m303_carry_ingress import M303CarryIngressError
from cadrumo.application.calculations.observations_repository import (
    ObservationEnvelopePayload,
    ResultDispositionProjection,
)
from cadrumo.application.calculations.relation_prefill import resolve_relations_from_local_store
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.observed_header_fact import ObservedHeaderFact
from cadrumo.core.period import Period
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.tests.registry_observations import (
    registry_grounded_modelo_observation,
    registry_grounded_observations,
    revision_id_for_observation,
)

from .....domain.calculations.registry.tests.relation_fixture import relation_prefill_values_as_binding_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIFO_BUCKET_ID = "39039000-0000-4000-8000-000000000097"
_HISTORY_BUCKET_ID = "39039000-0000-4000-8000-000000000390"


def _save_normalized_m303_carry_observation(
    repository: CalculationObservationRepository,
    observation: RegistryModeloObservation,
    *,
    disposition: ResultDisposition,
) -> None:
    """Persist real app-filing carry evidence through the production ingress."""
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind="app_filing",
            captured_at=datetime(2027, 1, 30, 12, 0, tzinfo=UTC),
            result_disposition=ResultDispositionProjection(
                disposition=disposition,
                provenance_kind="app_filing",
                provenance_locator=f"test-local-filing:{observation.filing_year}:{observation.period}",
            ),
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )


def _prepare_m303_carry_envelope(
    repository: CalculationObservationRepository,
    *,
    period: str,
    casilla_values: Mapping[CasillaId, Decimal],
    disposition: ResultDisposition,
    source_kind: str = "app_filing",
    provenance_kind: Literal["source_header", "app_filing"] = "app_filing",
    source_headers: tuple[ObservedHeaderFact, ...] = (),
) -> ObservationEnvelopePayload:
    """Build test filing evidence through the production envelope ingress."""
    observation = registry_grounded_modelo_observation(
        modelo="303",
        filing_year=2025,
        period=period,
        casilla_values=casilla_values,
    )
    return repository.prepare_observation_envelope(
        observation,
        source_kind=source_kind,
        captured_at=datetime(2027, 1, 30, 12, 0, tzinfo=UTC),
        source_headers=source_headers,
        result_disposition=ResultDispositionProjection(
            disposition=disposition,
            provenance_kind=provenance_kind,
            provenance_locator=f"test-filing:2025:{period}",
        ),
        stamped_revision_id=revision_id_for_observation(observation),
    )


def _raw_m303_carry_envelope(
    *,
    period: str,
    casilla_values: Mapping[CasillaId, Decimal],
    result_disposition: ResultDispositionProjection | None,
    source_kind: str = "app_filing",
    source_headers: tuple[ObservedHeaderFact, ...] = (),
) -> ObservationEnvelopePayload:
    """Attempt a malformed M303 payload; canonical model validation rejects it."""
    observation = registry_grounded_modelo_observation(
        modelo="303",
        filing_year=2025,
        period=period,
        casilla_values=casilla_values,
    )
    return ObservationEnvelopePayload(
        observation=observation,
        source_kind=source_kind,
        captured_at=datetime(2027, 1, 30, 12, 0, tzinfo=UTC),
        source_headers=source_headers,
        result_disposition=result_disposition,
        stamped_revision_id=revision_id_for_observation(observation),
    )


def test_modelo_390_carry_boxes_resolve_through_fifo_partition_with_carried_pending(tmp_path: Path) -> None:
    """End-to-end: the M390 box-97 / box-662 BINDING values come from the FIFO partition.

    Files four 303 quarters with a real carried-pending chain (1T credit carried,
    2T applies part of it, 4T generates more) as observations, then resolves the
    M390 annual compensation partition through its production source resolver.
    The two carry-box bindings must carry the partition: box 97 the last period's
    own result (50), box 662 the rest of the year's pending credit (70), together
    the 120 still pending, proving the boxes are not routed through the
    double-counting per-period relation path (50 / 100).
    """
    quarter_chain = [
        ("1T", Decimal("-100.00"), Decimal("100.00"), Decimal("0.00"), Decimal("0.00"), Decimal("100.00")),
        ("2T", Decimal("-10.00"), Decimal("0.00"), Decimal("30.00"), Decimal("70.00"), Decimal("70.00")),
        ("3T", Decimal("-10.00"), Decimal("0.00"), Decimal("0.00"), Decimal("70.00"), Decimal("70.00")),
        ("4T", Decimal("-50.00"), Decimal("50.00"), Decimal("0.00"), Decimal("70.00"), Decimal("120.00")),
    ]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FIFO_BUCKET_ID):
        observation_repo = CalculationObservationRepository()
        for period, resultado, generada, aplicada, posterior, disponible in quarter_chain:
            _save_normalized_m303_carry_observation(
                observation_repo,
                registry_grounded_modelo_observation(
                    modelo="303",
                    filing_year=2025,
                    period=period,
                    casilla_values={
                        M303_RESULTADO_CASILLA: resultado,
                        M303_GENERADA_CASILLA: generada,
                        M303_COMPENSACION_APLICADA_CASILLA: aplicada,
                        M303_POSTERIOR_CASILLA: posterior,
                        M303_DISPONIBLE_CASILLA: disponible,
                    },
                ),
                disposition=ResultDisposition.COMPENSACION,
            )

        snapshot = modelo_390_annual_snapshot()
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            resolution = IvaCompensationAnnualPartitionSourceResolver(
                repository=observation_repo,
                registry_snapshot=snapshot,
                operation=_authority_operation_for_test,
            ).resolve(
                CalculationSourceContext(
                    bucket_id=_FIFO_BUCKET_ID,
                    modelo="390",
                    filing_year=2025,
                    period=Period.from_year_and_code(2025, "0A"),
                    revision=snapshot.revision,
                ),
            )

    _4t_disponible = quarter_chain[-1][5]
    assert resolution.binding_values[BOX_97_BINDING] == Decimal("50.00")
    assert resolution.binding_values[BOX_662_BINDING] == Decimal("70.00")
    assert resolution.relation_values == {}
    assert not resolution.unresolved_binding_ids
    assert resolution.binding_values[BOX_97_BINDING] + resolution.binding_values[BOX_662_BINDING] == _4t_disponible
    assert resolution.provenance
    assert {item.dependency_treatment for item in resolution.provenance} == {"direct_annual_settlement"}
    assert {item.resolved_binding_source for item in resolution.provenance} == {
        BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION
    }
    assert {item.source_modelo for item in resolution.provenance} == {"303"}


def test_modelo_390_partition_refuses_missing_intermediate_m303_periods(tmp_path: Path) -> None:
    """A 1T/4T pair cannot make the declared four-quarter source complete."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FIFO_BUCKET_ID):
        observation_repo = CalculationObservationRepository()
        for period, resultado, generada, posterior, disponible in (
            ("1T", Decimal("-100.00"), Decimal("100.00"), Decimal("0.00"), Decimal("100.00")),
            ("4T", Decimal("-50.00"), Decimal("50.00"), Decimal("100.00"), Decimal("150.00")),
        ):
            _save_normalized_m303_carry_observation(
                observation_repo,
                registry_grounded_modelo_observation(
                    modelo="303",
                    filing_year=2025,
                    period=period,
                    casilla_values={
                        M303_RESULTADO_CASILLA: resultado,
                        M303_GENERADA_CASILLA: generada,
                        M303_COMPENSACION_APLICADA_CASILLA: Decimal("0.00"),
                        M303_POSTERIOR_CASILLA: posterior,
                        M303_DISPONIBLE_CASILLA: disponible,
                    },
                ),
                disposition=ResultDisposition.COMPENSACION,
            )

        snapshot = modelo_390_annual_snapshot()
        with bundled_indexed_authority().operation() as authority_operation:
            resolution = IvaCompensationAnnualPartitionSourceResolver(
                repository=observation_repo,
                registry_snapshot=snapshot,
                operation=authority_operation,
            ).resolve(
                CalculationSourceContext(
                    bucket_id=_FIFO_BUCKET_ID,
                    modelo="390",
                    filing_year=2025,
                    period=Period.from_year_and_code(2025, "0A"),
                    revision=snapshot.revision,
                ),
            )

    assert not resolution.binding_values
    assert set(resolution.unresolved_binding_ids) == {BOX_85_BINDING, BOX_97_BINDING, BOX_662_BINDING}
    assert {
        diagnostic.binding_id
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "iva_compensation_annual_source_evidence_failure"
    } == {BOX_85_BINDING, BOX_97_BINDING, BOX_662_BINDING}


def test_modelo_390_partition_accepts_explicit_zero_intermediate_m303_periods(tmp_path: Path) -> None:
    """Filed zero periods complete annual evidence; they are not missing periods."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FIFO_BUCKET_ID):
        observation_repo = CalculationObservationRepository()
        for period, resultado, generada, aplicada, posterior, disponible, disposition in (
            (
                "1T",
                Decimal("0.00"),
                Decimal("0.00"),
                Decimal("0.00"),
                Decimal("0.00"),
                Decimal("0.00"),
                ResultDisposition.NEGATIVA,
            ),
            (
                "2T",
                Decimal("0.00"),
                Decimal("0.00"),
                Decimal("0.00"),
                Decimal("0.00"),
                Decimal("0.00"),
                ResultDisposition.NEGATIVA,
            ),
            (
                "3T",
                Decimal("0.00"),
                Decimal("0.00"),
                Decimal("0.00"),
                Decimal("0.00"),
                Decimal("0.00"),
                ResultDisposition.NEGATIVA,
            ),
            (
                "4T",
                Decimal("-50.00"),
                Decimal("50.00"),
                Decimal("0.00"),
                Decimal("0.00"),
                Decimal("50.00"),
                ResultDisposition.COMPENSACION,
            ),
        ):
            _save_normalized_m303_carry_observation(
                observation_repo,
                registry_grounded_modelo_observation(
                    modelo="303",
                    filing_year=2025,
                    period=period,
                    casilla_values={
                        M303_RESULTADO_CASILLA: resultado,
                        M303_GENERADA_CASILLA: generada,
                        M303_COMPENSACION_APLICADA_CASILLA: aplicada,
                        M303_POSTERIOR_CASILLA: posterior,
                        M303_DISPONIBLE_CASILLA: disponible,
                    },
                ),
                disposition=disposition,
            )

        snapshot = modelo_390_annual_snapshot()
        with bundled_indexed_authority().operation() as authority_operation:
            resolution = IvaCompensationAnnualPartitionSourceResolver(
                repository=observation_repo,
                registry_snapshot=snapshot,
                operation=authority_operation,
            ).resolve(
                CalculationSourceContext(
                    bucket_id=_FIFO_BUCKET_ID,
                    modelo="390",
                    filing_year=2025,
                    period=Period.from_year_and_code(2025, "0A"),
                    revision=snapshot.revision,
                ),
            )

    assert resolution.binding_values[BOX_97_BINDING] == Decimal("50.00")
    assert resolution.binding_values[BOX_662_BINDING] == Decimal("0.00")
    # 1T filed [78] = [87] = 0.00, so no credit came from earlier years: a proven zero.
    assert resolution.binding_values[BOX_85_BINDING] == Decimal("0.00")
    assert not resolution.unresolved_binding_ids
    assert not {
        diagnostic.binding_id
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "iva_compensation_annual_source_evidence_failure"
    }


def _resolve_partition_for_quarters(
    tmp_path: Path,
    quarters: tuple[tuple[ResultDisposition, dict[CasillaId, Decimal]], ...],
) -> CalculationSourceResolution:
    """File four M303 quarters through the production ingress and resolve the M390 partition."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FIFO_BUCKET_ID):
        observation_repo = CalculationObservationRepository()
        for period, (disposition, casilla_values) in zip(("1T", "2T", "3T", "4T"), quarters, strict=True):
            _save_normalized_m303_carry_observation(
                observation_repo,
                registry_grounded_modelo_observation(
                    modelo="303",
                    filing_year=2025,
                    period=period,
                    casilla_values=casilla_values,
                ),
                disposition=disposition,
            )
        snapshot = modelo_390_annual_snapshot()
        with bundled_indexed_authority().operation() as authority_operation:
            return IvaCompensationAnnualPartitionSourceResolver(
                repository=observation_repo,
                registry_snapshot=snapshot,
                operation=authority_operation,
            ).resolve(
                CalculationSourceContext(
                    bucket_id=_FIFO_BUCKET_ID,
                    modelo="390",
                    filing_year=2025,
                    period=Period.from_year_and_code(2025, "0A"),
                    revision=snapshot.revision,
                ),
            )


def _quarter(
    resultado: str,
    *,
    generada: str = "0.00",
    aplicada: str | None = None,
    posterior: str | None = None,
    disponible: str,
) -> dict[CasillaId, Decimal]:
    """One quarter's compensation casillas; an omitted box 78 or 87 is not stated, not zero."""
    values = {
        M303_RESULTADO_CASILLA: Decimal(resultado),
        M303_GENERADA_CASILLA: Decimal(generada),
        M303_DISPONIBLE_CASILLA: Decimal(disponible),
    }
    if aplicada is not None:
        values[M303_COMPENSACION_APLICADA_CASILLA] = Decimal(aplicada)
    if posterior is not None:
        values[M303_POSTERIOR_CASILLA] = Decimal(posterior)
    return values


def test_modelo_390_unknown_opening_with_in_year_compensation_leaves_85_97_and_662_unresolved(
    tmp_path: Path,
) -> None:
    """1T states neither box 87 nor box 78, so the opening credit is unknown.

    2T then compensates 30.00 (box 78). The FIFO charges that to the unknown
    opening first, so the year's own 100.00 credit may be untouched or partly
    used; boxes 97 and 662 cannot be stated, and none of the three may read as zero.
    """
    compensacion = ResultDisposition.COMPENSACION
    resolution = _resolve_partition_for_quarters(
        tmp_path,
        (
            (compensacion, _quarter("-100.00", generada="100.00", disponible="100.00")),
            (compensacion, _quarter("-10.00", aplicada="30.00", posterior="70.00", disponible="70.00")),
            (compensacion, _quarter("-10.00", aplicada="0.00", posterior="70.00", disponible="70.00")),
            (compensacion, _quarter("-10.00", aplicada="0.00", posterior="70.00", disponible="70.00")),
        ),
    )

    assert not resolution.binding_values
    assert set(resolution.unresolved_binding_ids) == {BOX_85_BINDING, BOX_97_BINDING, BOX_662_BINDING}
    opening_diagnostics = {
        diagnostic.binding_id: diagnostic.message
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "source_issue"
    }
    assert set(opening_diagnostics) == {BOX_85_BINDING, BOX_97_BINDING, BOX_662_BINDING}
    assert all("unknown, not zero" in message for message in opening_diagnostics.values())


def test_modelo_390_unknown_opening_without_compensation_still_resolves_97_and_662(tmp_path: Path) -> None:
    """With box 78 zero in every quarter, nothing can have consumed credit generated in the year.

    Boxes 97 and 662 then do not depend on the unknown opening: 4T generates
    50.00 and nothing was applied, so 97 = 50.00 and 662 = 0.00. Box 85 stays unknown.
    """
    negativa = ResultDisposition.NEGATIVA
    resolution = _resolve_partition_for_quarters(
        tmp_path,
        (
            (negativa, _quarter("0.00", disponible="0.00")),
            (negativa, _quarter("0.00", aplicada="0.00", posterior="0.00", disponible="0.00")),
            (negativa, _quarter("0.00", aplicada="0.00", posterior="0.00", disponible="0.00")),
            (
                ResultDisposition.COMPENSACION,
                _quarter("-50.00", generada="50.00", aplicada="0.00", disponible="50.00"),
            ),
        ),
    )

    assert resolution.binding_values == {
        BOX_97_BINDING: Decimal("50.00"),
        BOX_662_BINDING: Decimal("0.00"),
    }
    assert resolution.unresolved_binding_ids == (BOX_85_BINDING,)


def test_modelo_390_known_opening_keeps_all_three_boxes_resolved_with_in_year_compensation(tmp_path: Path) -> None:
    """1T states box 87 = 900.00 and box 78 = 100.00, so the opening is 1000.00 (87 + 78).

    The opening is consumed first: 100 (1T) + 150 (2T) leave 750.00; 3T generates
    40.00 and 4T applies 760.00, taking the last 750.00 of the opening and
    10.00 of the year's lot, leaving 30.00 for the year-end boxes. Box 85 is the opening consumed, 1000.00.
    """
    ingreso = ResultDisposition.INGRESO
    resolution = _resolve_partition_for_quarters(
        tmp_path,
        (
            (ingreso, _quarter("10.00", aplicada="100.00", posterior="900.00", disponible="900.00")),
            (ingreso, _quarter("10.00", aplicada="150.00", posterior="750.00", disponible="750.00")),
            (
                ResultDisposition.COMPENSACION,
                _quarter("-40.00", generada="40.00", aplicada="0.00", posterior="750.00", disponible="790.00"),
            ),
            (ingreso, _quarter("10.00", aplicada="760.00", posterior="30.00", disponible="30.00")),
        ),
    )

    assert not resolution.unresolved_binding_ids
    assert resolution.binding_values[BOX_85_BINDING] == Decimal("1000.00")
    assert resolution.binding_values[BOX_97_BINDING] + resolution.binding_values[BOX_662_BINDING] == Decimal("30.00")


_ingreso = ResultDisposition.INGRESO
_compensa = ResultDisposition.COMPENSACION
_negativa = ResultDisposition.NEGATIVA


@pytest.mark.parametrize(
    ("quarters", "box_85", "box_97", "box_662"),
    [
        pytest.param(
            (
                (_negativa, _quarter("0.00", aplicada="200.00", posterior="800.00", disponible="800.00")),
                (_negativa, _quarter("0.00", aplicada="600.00", posterior="200.00", disponible="200.00")),
                (
                    _compensa,
                    _quarter("-500.00", generada="500.00", aplicada="0.00", posterior="200.00", disponible="700.00"),
                ),
                (
                    _compensa,
                    _quarter("-200.00", generada="200.00", aplicada="0.00", posterior="700.00", disponible="900.00"),
                ),
            ),
            "800.00",
            "200.00",
            "500.00",
            id="manual-iva-2025-p277",
        ),
        pytest.param(
            (
                (_ingreso, _quarter("100.00", aplicada="0.00", posterior="0.00", disponible="0.00")),
                (
                    _compensa,
                    _quarter("-200.00", generada="200.00", aplicada="0.00", posterior="0.00", disponible="200.00"),
                ),
                (_negativa, _quarter("0.00", aplicada="0.00", posterior="200.00", disponible="200.00")),
                (
                    _compensa,
                    _quarter("-500.00", generada="500.00", aplicada="0.00", posterior="200.00", disponible="700.00"),
                ),
            ),
            "0.00",
            "500.00",
            "200.00",
            id="manual-iva-2025-p279",
        ),
        pytest.param(
            (
                (_negativa, _quarter("0.00", aplicada="100.00", posterior="100.00", disponible="100.00")),
                (
                    _compensa,
                    _quarter("-200.00", generada="200.00", aplicada="0.00", posterior="100.00", disponible="300.00"),
                ),
                (_ingreso, _quarter("100.00", aplicada="300.00", posterior="0.00", disponible="0.00")),
                (
                    _compensa,
                    _quarter("-500.00", generada="500.00", aplicada="0.00", posterior="0.00", disponible="500.00"),
                ),
            ),
            "200.00",
            "500.00",
            "0.00",
            id="manual-iva-2025-p280-example-2",
        ),
        pytest.param(
            (
                (_negativa, _quarter("0.00", aplicada="100.00", posterior="100.00", disponible="100.00")),
                (
                    _compensa,
                    _quarter("-200.00", generada="200.00", aplicada="0.00", posterior="100.00", disponible="300.00"),
                ),
                (_negativa, _quarter("0.00", aplicada="0.00", posterior="300.00", disponible="300.00")),
                (
                    _compensa,
                    _quarter("-500.00", generada="500.00", aplicada="0.00", posterior="300.00", disponible="800.00"),
                ),
            ),
            "100.00",
            "500.00",
            "200.00",
            id="manual-iva-2025-p280-example-3",
        ),
    ],
)
def test_modelo_390_boxes_85_97_and_662_match_the_manual_examples(
    tmp_path: Path,
    quarters: tuple[tuple[ResultDisposition, dict[CasillaId, Decimal]], ...],
    box_85: str,
    box_97: str,
    box_662: str,
) -> None:
    """Manual IVA 2025 pp. 277-281. Box 97 is the result of the last autoliquidación and box 662 the year's other
    pending credit: "las cuotas a compensar generadas en el ejercicio en alguno de los períodos de liquidación
    distintos del último".
    """
    resolution = _resolve_partition_for_quarters(tmp_path, quarters)

    assert resolution.binding_values == {
        BOX_85_BINDING: Decimal(box_85),
        BOX_97_BINDING: Decimal(box_97),
        BOX_662_BINDING: Decimal(box_662),
    }


def test_modelo_390_compensation_bindings_resolve_from_secure_iva_history(tmp_path: Path) -> None:
    """M390 ordinary 303 totals use relations; compensation uses the FIFO partition.

    The cuota / resultado annual-summary bindings resolve via ``relation_prefill``
    backed by ``cross_model_output`` relations. The compensación bindings
    (ultimo-periodo + generada-ejercicio-no-97) read current M303 compensation
    state casillas through ``iva_compensation_annual_partition`` so boxes 97/662
    are _produced together from the FIFO partition.
    """
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        quarter_data = [
            ("1T", Decimal("100.00"), Decimal("40.00"), Decimal("60.00"), Decimal("20.00")),
            ("2T", Decimal("80.00"), Decimal("30.00"), Decimal("50.00"), Decimal("10.00")),
            ("3T", Decimal("120.00"), Decimal("50.00"), Decimal("70.00"), Decimal("20.00")),
            ("4T", Decimal("90.00"), Decimal("60.00"), Decimal("30.00"), Decimal("100.00")),
        ]
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_HISTORY_BUCKET_ID):
            observation_repo = CalculationObservationRepository()
            for period, devengada, deducible, regimen_general, compensacion in quarter_data:
                _save_normalized_m303_carry_observation(
                    observation_repo,
                    registry_grounded_modelo_observation(
                        modelo="303",
                        filing_year=2025,
                        period=period,
                        casilla_values={
                            M303_CUOTA_DEVENGADA_TOTAL_CASILLA: devengada,
                            M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: deducible,
                            M303_RESULTADO_REGIMEN_GENERAL_CASILLA: regimen_general,
                            M303_RESULTADO_CASILLA: Decimal("-1.00"),
                            M303_GENERADA_CASILLA: compensacion,
                        },
                    ),
                    disposition=ResultDisposition.COMPENSACION,
                )

            snapshot = modelo_390_annual_snapshot()
            relation_vals = resolve_relations_from_local_store(
                snapshot,
                repository=observation_repo,
                captured_at=datetime(2027, 1, 30, 12, 0, tzinfo=UTC),
                operation=_authority_operation_for_test,
            )
            annual_partition = IvaCompensationAnnualPartitionSourceResolver(
                repository=observation_repo,
                registry_snapshot=snapshot,
                operation=_authority_operation_for_test,
            ).resolve(
                CalculationSourceContext(
                    bucket_id=_HISTORY_BUCKET_ID,
                    modelo="390",
                    filing_year=2025,
                    period=Period.from_year_and_code(2025, "0A"),
                    revision=snapshot.revision,
                ),
            )

        relation_values_map = {rv.relation: rv.value for rv in relation_vals.values if rv.value is not None}
        resolved = relation_prefill_values_as_binding_values(snapshot.revision, relation_values_map, period="0A")

        assert resolved["modelo-390-prev-303-cuota-devengada-total"] == Decimal("390.00")
        assert resolved["modelo-390-prev-303-cuota-deducible-total"] == Decimal("180.00")
        assert resolved["modelo-390-prev-303-resultado-regimen-general"] == Decimal("210.00")
        assert annual_partition.binding_values["modelo-390-prev-303-compensacion-generada-ejercicio-no-97"] == Decimal(
            "50.00",
        )
        assert annual_partition.binding_values["modelo-390-prev-303-compensacion-ultimo-periodo"] == Decimal("100.00")
        resolved_rels = {rv.relation for rv in relation_vals.values if rv.value is not None}
        assert resolved_rels == {
            "modelo-390-prev-303-cuota-devengada-total",
            "modelo-390-prev-303-cuota-deducible-total",
            "modelo-390-prev-303-resultado-regimen-general",
        }
        assert not annual_partition.relation_values
        # These quarters state no box 78 or 87, so the credit the year opened with
        # is unknown: box 85 stays unresolved instead of reading as zero.
        assert annual_partition.unresolved_binding_ids == (BOX_85_BINDING,)
        assert BOX_85_BINDING not in annual_partition.binding_values
        assert all(rv.provenance == "local_filing" for rv in relation_vals.values if rv.value is not None)


def test_relation_prefill_fifo_state_refuses_printed_number_compensation_references(tmp_path: Path) -> None:
    with (
        bundled_indexed_authority().operation() as _authority_operation_for_test,
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FIFO_BUCKET_ID),
    ):
        # Every sibling in this module runs inside a real bucket runtime; these
        # two reached CalculationObservationRepository with no active session.
        snapshot = modelo_390_annual_snapshot()
        repository = CalculationObservationRepository()
        generated_observation = registry_grounded_observations(
            modelo="303",
            filing_year=2025,
            period="4T",
            casilla_values={
                M303_RESULTADO_CASILLA: Decimal("-50.00"),
                M303_GENERADA_CASILLA: Decimal("50.00"),
            },
        )[0]
        valid_observation = RegistryModeloObservation(
            modelo="303",
            filing_year=2025,
            period="4T",
            observations=(generated_observation,),
        )
        envelope = repository.prepare_observation_envelope(
            valid_observation,
            source_kind="app_filing",
            result_disposition=ResultDispositionProjection(
                disposition=ResultDisposition.COMPENSACION,
                provenance_kind="app_filing",
                provenance_locator="test-local-filing:2025:4T",
            ),
            stamped_revision_id=revision_id_for_observation(valid_observation),
        )
        observation = envelope.observation.model_copy(
            update={
                "observations": (
                    *envelope.observation.observations,
                    generated_observation.model_copy(
                        update={"casilla_id": M303_PRINTED_COMPENSATION_REFERENCE_CASILLA}
                    ),
                ),
            },
        )
        invalid_envelope = envelope.model_copy(update={"observation": observation})

        with pytest.raises(RegistryValidationError) as excinfo:
            resolve_iva_compensation_annual_partition_binding_values(
                snapshot.revision, (invalid_envelope,), filing_year=2025, operation=_authority_operation_for_test
            )

        assert str(excinfo.value) == (
            "application.calculations.iva_compensation.errors.annual_partition_casilla_ids_noncanonical"
        )


def test_annual_partition_reader_refuses_a_persisted_available_generated_pair_mismatch(tmp_path: Path) -> None:
    """The FIFO reader independently rejects a pair changed after ingress."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FIFO_BUCKET_ID):
        repository = CalculationObservationRepository()
        envelope = _prepare_m303_carry_envelope(
            repository,
            period="4T",
            casilla_values={
                M303_RESULTADO_CASILLA: Decimal("-25.00"),
                M303_GENERADA_CASILLA: Decimal("25.00"),
            },
            disposition=ResultDisposition.COMPENSACION,
        )
        mismatched_observation = envelope.observation.model_copy(
            update={
                "observations": tuple(
                    observation.model_copy(update={"value": Decimal("99.00")})
                    if observation.casilla_id == M303_DISPONIBLE_CASILLA
                    else observation
                    for observation in envelope.observation.observations
                ),
            },
        )
        repository.save(envelope.model_copy(update={"observation": mismatched_observation}))
        snapshot = modelo_390_annual_snapshot()

        with (
            bundled_indexed_authority().operation() as _authority_operation_for_test,
            pytest.raises(M303CarryIngressError),
        ):
            IvaCompensationAnnualPartitionSourceResolver(
                repository=repository,
                registry_snapshot=snapshot,
                operation=_authority_operation_for_test,
            ).resolve(
                CalculationSourceContext(
                    bucket_id=_FIFO_BUCKET_ID,
                    modelo="390",
                    filing_year=2025,
                    period=Period.from_year_and_code(2025, "0A"),
                    revision=snapshot.revision,
                ),
            )


def test_annual_partition_keeps_refunded_credit_out_of_both_m390_carry_boxes(tmp_path: Path) -> None:
    """Identical negative results diverge only by the filed C/D disposition."""
    with (
        bundled_indexed_authority().operation() as _authority_operation_for_test,
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FIFO_BUCKET_ID),
    ):
        # Every sibling in this module runs inside a real bucket runtime; these
        # two reached CalculationObservationRepository with no active session.
        repository = CalculationObservationRepository()
        input_values = {
            M303_RESULTADO_CASILLA: Decimal("-25.00"),
            M303_GENERADA_CASILLA: Decimal("25.00"),
        }
        carried = _prepare_m303_carry_envelope(
            repository,
            period="4T",
            casilla_values=input_values,
            disposition=ResultDisposition.COMPENSACION,
        )
        refunded = _prepare_m303_carry_envelope(
            repository,
            period="4T",
            casilla_values=input_values,
            disposition=ResultDisposition.DEVOLUCION,
        )
        snapshot = modelo_390_annual_snapshot()

        carried_values = resolve_iva_compensation_annual_partition_binding_values(
            snapshot.revision, (carried,), filing_year=2025, operation=_authority_operation_for_test
        )
        refunded_values = resolve_iva_compensation_annual_partition_binding_values(
            snapshot.revision, (refunded,), filing_year=2025, operation=_authority_operation_for_test
        )

        assert carried_values[BOX_97_BINDING] == Decimal("25.00")
        assert carried_values[BOX_662_BINDING] == Decimal("0.00")
        assert refunded_values[BOX_97_BINDING] == Decimal("0.00")
        assert refunded_values[BOX_662_BINDING] == Decimal("0.00")


def test_annual_partition_refuses_underdeclared_and_conflicting_disposition_evidence(tmp_path: Path) -> None:
    """Missing or conflicting filing disposition cannot participate in FIFO."""
    with (
        bundled_indexed_authority().operation() as _authority_operation_for_test,
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FIFO_BUCKET_ID),
    ):
        with pytest.raises(ValidationError, match="requires canonical result disposition"):
            _raw_m303_carry_envelope(
                period="4T",
                casilla_values={
                    M303_RESULTADO_CASILLA: Decimal("-25.00"),
                    M303_GENERADA_CASILLA: Decimal("25.00"),
                },
                result_disposition=None,
            )
        conflicting = _prepare_m303_carry_envelope(
            CalculationObservationRepository(),
            period="4T",
            casilla_values={
                M303_RESULTADO_CASILLA: Decimal("-25.00"),
                M303_GENERADA_CASILLA: Decimal("25.00"),
            },
            disposition=ResultDisposition.COMPENSACION,
        ).model_copy(
            update={
                "source_headers": (
                    ObservedHeaderFact(
                        header_key="filing.result_disposition",
                        value="D",
                        source_artefact_kind="submitted_file",
                        source_locator="modelo-303:test:declaration_type:13:1",
                    ),
                ),
            },
        )

        with pytest.raises(M303CarryIngressError):
            resolve_iva_compensation_annual_partition_binding_values(
                modelo_390_annual_snapshot().revision,
                (conflicting,),
                filing_year=2025,
                operation=_authority_operation_for_test,
            )
