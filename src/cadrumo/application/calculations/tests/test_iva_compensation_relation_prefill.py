"""IVA compensation relation-prefill binding tests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pytest

from ....core import BindingSourceKind, CasillaId, ObservedHeaderFact, Period, ResultDisposition
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.relations import materialize_relation_binding_values
from ....tests.registry_observations import registry_grounded_modelo_observation, registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import CalculationSourceContext
from .._iva_compensation_annual_partition import (
    IvaCompensationAnnualPartitionSourceResolver,
    resolve_iva_compensation_annual_partition_binding_values,
)
from .._m303_carry_ingress import M303CarryIngressError
from .._observations_repository import CalculationObservationRepository, ResultDispositionProjection
from .._relation_prefill import resolve_relations_from_local_store
from ._iva_compensation_history_support import (
    _BOX_97_BINDING,
    _BOX_662_BINDING,
    _M303_COMPENSACION_APLICADA_CASILLA,
    _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    _M303_DISPONIBLE_CASILLA,
    _M303_GENERADA_CASILLA,
    _M303_POSTERIOR_CASILLA,
    _M303_PRINTED_COMPENSATION_REFERENCE_CASILLA,
    _M303_RESULTADO_CASILLA,
    _M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
    _modelo_390_annual_snapshot,
)

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
            normalize_m303_carry=True,
        )
    )


def _prepare_m303_carry_envelope(
    repository: CalculationObservationRepository,
    *,
    period: str,
    casilla_values: Mapping[CasillaId, Decimal],
    disposition: ResultDisposition | None,
    source_kind: str = "app_filing",
    provenance_kind: Literal["source_header", "app_filing"] = "app_filing",
    source_headers: tuple[ObservedHeaderFact, ...] = (),
    normalize: bool = True,
):
    """Build test filing evidence through the production envelope ingress."""
    return repository.prepare_observation_envelope(
        registry_grounded_modelo_observation(
            modelo="303",
            filing_year=2025,
            period=period,
            casilla_values=casilla_values,
        ),
        source_kind=source_kind,
        captured_at=datetime(2027, 1, 30, 12, 0, tzinfo=UTC),
        source_headers=source_headers,
        result_disposition=(
            ResultDispositionProjection(
                disposition=disposition,
                provenance_kind=provenance_kind,
                provenance_locator=f"test-filing:2025:{period}",
            )
            if disposition is not None
            else None
        ),
        normalize_m303_carry=normalize,
    )


def test_modelo_390_carry_boxes_resolve_through_fifo_partition_with_carried_pending(tmp_path: Path) -> None:
    """End-to-end: the M390 box-97 / box-662 BINDING values come from the FIFO partition.

    Files four 303 quarters with a real carried-pending chain (1T credit carried,
    2T applies part of it, 4T generates more) as observations, then resolves the
    M390 annual compensation partition through its production source resolver.
    The two carry-box bindings must carry the FIFO partition
    (box 97 = 120, box 662 = 0), NOT the per-period relation sums (50 / 100),
    proving the registry no longer routes the boxes through the double-counting
    per-period relation path.
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
                        _M303_RESULTADO_CASILLA: resultado,
                        _M303_GENERADA_CASILLA: generada,
                        _M303_COMPENSACION_APLICADA_CASILLA: aplicada,
                        _M303_POSTERIOR_CASILLA: posterior,
                        _M303_DISPONIBLE_CASILLA: disponible,
                    },
                ),
                disposition=ResultDisposition.COMPENSACION,
            )

        snapshot = _modelo_390_annual_snapshot()
        resolution = IvaCompensationAnnualPartitionSourceResolver(
            repository=observation_repo,
            registry_snapshot=snapshot,
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
    assert resolution.binding_values[_BOX_97_BINDING] == _4t_disponible
    assert resolution.binding_values[_BOX_662_BINDING] == Decimal("0.00")
    assert resolution.relation_values == {}
    assert not resolution.unresolved_binding_ids
    assert resolution.binding_values[_BOX_97_BINDING] + resolution.binding_values[_BOX_662_BINDING] == _4t_disponible
    assert resolution.provenance
    assert {item.dependency_treatment for item in resolution.provenance} == {"direct_annual_settlement"}
    assert {item.resolved_binding_source for item in resolution.provenance} == {
        BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION
    }
    assert {item.source_modelo for item in resolution.provenance} == {"303"}


def test_modelo_390_compensation_bindings_resolve_from_secure_iva_history(tmp_path: Path) -> None:
    """M390 ordinary 303 totals use relations; compensation uses the FIFO partition.

    The cuota / resultado annual-summary bindings resolve via ``relation_prefill``
    backed by ``cross_model_output`` relations. The compensación bindings
    (ultimo-periodo + generada-ejercicio-no-97) read current M303 compensation
    state casillas through ``iva_compensation_annual_partition`` so boxes 97/662
    are produced together from the FIFO partition.
    """
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
                        _M303_CUOTA_DEVENGADA_TOTAL_CASILLA: devengada,
                        _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: deducible,
                        _M303_RESULTADO_REGIMEN_GENERAL_CASILLA: regimen_general,
                        _M303_RESULTADO_CASILLA: Decimal("-1.00"),
                        _M303_GENERADA_CASILLA: compensacion,
                    },
                ),
                disposition=ResultDisposition.COMPENSACION,
            )

        snapshot = _modelo_390_annual_snapshot()
        relation_vals = resolve_relations_from_local_store(
            snapshot,
            repository=observation_repo,
            captured_at=datetime(2027, 1, 30, 12, 0, tzinfo=UTC),
        )
        annual_partition = IvaCompensationAnnualPartitionSourceResolver(
            repository=observation_repo,
            registry_snapshot=snapshot,
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
    resolved = materialize_relation_binding_values(snapshot.revision, relation_values_map, period="0A")

    assert resolved["modelo-390-prev-303-cuota-devengada-total"] == Decimal("390.00")
    assert resolved["modelo-390-prev-303-cuota-deducible-total"] == Decimal("180.00")
    assert resolved["modelo-390-prev-303-resultado-regimen-general"] == Decimal("210.00")
    assert annual_partition.binding_values["modelo-390-prev-303-compensacion-generada-ejercicio-no-97"] == Decimal(
        "50.00",
    )
    assert annual_partition.binding_values["modelo-390-prev-303-compensacion-ultimo-periodo"] == Decimal("100.00")
    resolved_rels = {rv.relation for rv in relation_vals.values if rv.value is not None}
    assert resolved_rels == {
        "modelo-390-rel-303-cuota-devengada-total",
        "modelo-390-rel-303-cuota-deducible-total",
        "modelo-390-rel-303-resultado-regimen-general",
    }
    assert not annual_partition.relation_values
    assert not annual_partition.unresolved_binding_ids
    assert all(rv.provenance == "local_filing" for rv in relation_vals.values if rv.value is not None)


def test_relation_prefill_fifo_state_refuses_printed_number_compensation_references(tmp_path: Path) -> None:
    # Every sibling in this module runs inside a real bucket runtime; these
    # two reached CalculationObservationRepository with no active session.
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FIFO_BUCKET_ID):
        snapshot = _modelo_390_annual_snapshot()
        repository = CalculationObservationRepository()
        generated_observation = registry_grounded_observations(
            modelo="303",
            filing_year=2025,
            period="4T",
            casilla_values={
                _M303_RESULTADO_CASILLA: Decimal("-50.00"),
                _M303_GENERADA_CASILLA: Decimal("50.00"),
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
            normalize_m303_carry=True,
        )
        observation = envelope.observation.model_copy(
            update={
                "observations": (
                    *envelope.observation.observations,
                    generated_observation.model_copy(
                        update={"casilla_id": _M303_PRINTED_COMPENSATION_REFERENCE_CASILLA}
                    ),
                ),
            },
        )
        invalid_envelope = envelope.model_copy(update={"observation": observation})

        with pytest.raises(RegistryValidationError) as excinfo:
            resolve_iva_compensation_annual_partition_binding_values(
                snapshot.revision,
                (invalid_envelope,),
                filing_year=2025,
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
                _M303_RESULTADO_CASILLA: Decimal("-25.00"),
                _M303_GENERADA_CASILLA: Decimal("25.00"),
            },
            disposition=ResultDisposition.COMPENSACION,
        )
        mismatched_observation = envelope.observation.model_copy(
            update={
                "observations": tuple(
                    observation.model_copy(update={"value": Decimal("99.00")})
                    if observation.casilla_id == _M303_DISPONIBLE_CASILLA
                    else observation
                    for observation in envelope.observation.observations
                ),
            },
        )
        repository.save(envelope.model_copy(update={"observation": mismatched_observation}))
        snapshot = _modelo_390_annual_snapshot()

        with pytest.raises(M303CarryIngressError):
            IvaCompensationAnnualPartitionSourceResolver(
                repository=repository,
                registry_snapshot=snapshot,
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
    # Every sibling in this module runs inside a real bucket runtime; these
    # two reached CalculationObservationRepository with no active session.
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FIFO_BUCKET_ID):
        repository = CalculationObservationRepository()
        input_values = {
            _M303_RESULTADO_CASILLA: Decimal("-25.00"),
            _M303_GENERADA_CASILLA: Decimal("25.00"),
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
        snapshot = _modelo_390_annual_snapshot()

        carried_values = resolve_iva_compensation_annual_partition_binding_values(
            snapshot.revision,
            (carried,),
            filing_year=2025,
        )
        refunded_values = resolve_iva_compensation_annual_partition_binding_values(
            snapshot.revision,
            (refunded,),
            filing_year=2025,
        )

        assert carried_values[_BOX_97_BINDING] == Decimal("25.00")
        assert carried_values[_BOX_662_BINDING] == Decimal("0.00")
        assert refunded_values[_BOX_97_BINDING] == Decimal("0.00")
        assert refunded_values[_BOX_662_BINDING] == Decimal("0.00")


def test_annual_partition_refuses_legacy_and_conflicting_disposition_evidence(tmp_path: Path) -> None:
    """Missing or conflicting filing disposition cannot participate in FIFO."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_FIFO_BUCKET_ID):
        repository = CalculationObservationRepository()
        legacy = _prepare_m303_carry_envelope(
            repository,
            period="4T",
            casilla_values={
                _M303_RESULTADO_CASILLA: Decimal("-25.00"),
                _M303_GENERADA_CASILLA: Decimal("25.00"),
            },
            disposition=None,
            normalize=False,
        )
        repository.save(legacy)
        snapshot = _modelo_390_annual_snapshot()

        with pytest.raises(M303CarryIngressError):
            IvaCompensationAnnualPartitionSourceResolver(
                repository=repository,
                registry_snapshot=snapshot,
            ).resolve(
                CalculationSourceContext(
                    bucket_id=_FIFO_BUCKET_ID,
                    modelo="390",
                    filing_year=2025,
                    period=Period.from_year_and_code(2025, "0A"),
                    revision=snapshot.revision,
                ),
            )

    conflicting = _prepare_m303_carry_envelope(
        CalculationObservationRepository(),
        period="4T",
        casilla_values={
            _M303_RESULTADO_CASILLA: Decimal("-25.00"),
            _M303_GENERADA_CASILLA: Decimal("25.00"),
        },
        disposition=ResultDisposition.COMPENSACION,
        source_kind="aeat_sede_live_capture",
        provenance_kind="source_header",
        source_headers=(
            ObservedHeaderFact(
                header_key="declaration_type",
                value="D",
                source_artefact_kind="submitted_file",
                source_locator="modelo-303:test:declaration_type:13:1",
            ),
        ),
        normalize=False,
    )

    with pytest.raises(M303CarryIngressError):
        resolve_iva_compensation_annual_partition_binding_values(
            _modelo_390_annual_snapshot().revision,
            (conflicting,),
            filing_year=2025,
        )
