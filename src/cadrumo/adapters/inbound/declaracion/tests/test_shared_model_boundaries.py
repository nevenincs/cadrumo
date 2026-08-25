"""Shared model boundary guards for declaración extraction."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from cadrumo.domain.calculations.registry.schema import RegistrySnapshotRef
from ...pdf import ExtractedCasilla
from .. import ExtractionWarning, InboundDeclaracionObservation, TemplateRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_declaracion_records_use_pydantic_boundary_models() -> None:
    assert issubclass(TemplateRevision, BaseModel)
    assert issubclass(ExtractionWarning, BaseModel)
    assert issubclass(InboundDeclaracionObservation, BaseModel)


def test_declaracion_observation_reuses_shared_pdf_and_registry_models() -> None:
    values_field = InboundDeclaracionObservation.model_fields["values"]
    snapshot_field = InboundDeclaracionObservation.model_fields["registry_snapshot_ref"]

    assert values_field.annotation == tuple[ExtractedCasilla, ...]
    assert snapshot_field.annotation == RegistrySnapshotRef
    assert snapshot_field.is_required()
