"""Both literal and declared binding constants supply exact record identity."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.design_constant_bindings import DesignConstantProvider
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType
from cadrumo.domain.calculations.registry.tests.authored_editions import open_ended_revision

from ..authority import compiled_bundled_authority
from ..export_layout_record_join import design_constant_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_design_constant_bindings_contribute_only_their_own_declared_identity() -> None:
    revision = compiled_bundled_authority().modelo("720").revisions[str(open_ended_revision("720").id)]
    binding = revision.bindings[0].model_copy(
        update={
            "provider": DesignConstantProvider(
                record="declaracion", field="modelo", offset=2, length=3, data_type=CasillaDataType.TEXT, value="720"
            )
        }
    )
    assert design_constant_values(revision.model_copy(update={"bindings": (binding,)})) == {str(binding.id): "720"}
    assert design_constant_values(revision.model_copy(update={"bindings": ()})) == {}
