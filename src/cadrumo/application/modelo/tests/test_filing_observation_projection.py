"""Filing views preserve the canonical identifiers stored by observation producers."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition, revision_covering
from ...calculations.observations_repository import (
    ObservationEnvelopePayload,
    ObservationLayers,
    ObservationOverride,
    ObservationSourceKind,
)
from ..filing_record_view_operation import (
    ModeloFilingObservationLayerProjection,
    ModeloFilingObservationLayersProjection,
    ModeloFilingObservationOverrideProjection,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(1980, 4, 10, 9, 0, tzinfo=UTC)
_FILING_YEAR = newest_authored_edition("130")
_REVISION_ID = str(revision_covering("130", _FILING_YEAR).id)


def test_m130_layers_and_override_preserve_long_working_figure_identifiers() -> None:
    # These working figures accompany the numbered boxes in the saved M130 calculation.
    values = (
        ("01", "12000.00"),
        ("gastos-deducibles-previos", "2000.00"),
        ("provisiones-gastos-dificil-justificacion", "500.00"),
        ("rendimiento-neto-reducible-art-32-1", "0.00"),
        ("saldo-negativo-fin-periodo", "0.00"),
    )
    observation = RegistryModeloObservation(
        modelo="130",
        filing_year=_FILING_YEAR,
        period="1T",
        observations=tuple(
            CasillaObservation(
                casilla_id=validated_casilla_id(key),
                value=Decimal(value),
                legal_refs=("rd-439-2007:art-110",),
                source_refs=("aeat-modelo-130-instructions",),
            )
            for key, value in reversed(values)
        ),
    )
    official = ObservationEnvelopePayload(
        source_kind=ObservationSourceKind.AEAT_CSV_REGISTER,
        captured_at=_NOW,
        stamped_revision_id=_REVISION_ID,
        observation=observation,
    )
    override = ObservationOverride(
        actor="operator",
        reason="corrected from supporting evidence",
        recorded_at=_NOW,
        replaced_source_kind=official.source_kind,
        replaced_values={validated_casilla_id(key): value for key, value in reversed(values)},
    )
    pending = ObservationEnvelopePayload(
        source_kind=ObservationSourceKind.OPERATOR_MANUAL,
        captured_at=_NOW,
        stamped_revision_id=_REVISION_ID,
        observation=observation,
        override=override,
    )

    projection = ModeloFilingObservationLayersProjection.from_layers(
        ObservationLayers(modelo="130", filing_year=_FILING_YEAR, period="1T", official=official, pending_local=pending)
    )
    restored = ModeloFilingObservationLayersProjection.model_validate_json(projection.model_dump_json())

    assert restored == projection
    assert restored.official is not None
    assert restored.official.casilla_values == values
    assert restored.official.official_evidence
    assert restored.pending_local is not None
    assert restored.pending_local.casilla_values == values
    assert not restored.pending_local.official_evidence
    assert restored.override is not None
    assert restored.override.replaced_values == values
    assert restored.effective_source_kind is ObservationSourceKind.OPERATOR_MANUAL


@pytest.mark.parametrize("key", ("a" * 64, "", "a" * 65, "invalid casilla"))
@pytest.mark.parametrize("override", (False, True))
def test_observation_projection_keys_follow_canonical_casilla_bounds(key: str, override: bool) -> None:
    def project() -> ModeloFilingObservationLayerProjection | ModeloFilingObservationOverrideProjection:
        if override:
            return ModeloFilingObservationOverrideProjection(
                actor="operator",
                reason="corrected from supporting evidence",
                recorded_at=_NOW,
                replaced_values=((key, "1.00"),),
            )
        return ModeloFilingObservationLayerProjection(
            source_kind=ObservationSourceKind.AEAT_CSV_REGISTER,
            official_evidence=True,
            captured_at=_NOW,
            stamped_revision_id=_REVISION_ID,
            casilla_values=((key, "1.00"),),
        )

    if key == "a" * 64:
        projection = project()
        restored = type(projection).model_validate_json(projection.model_dump_json())
        assert restored == projection
    else:
        with pytest.raises(ValidationError):
            project()
