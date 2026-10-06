"""Production enrollment must admit the reviewed publication, never the retired template."""

import pytest

from ...application.export.google_review_operation_contracts import GOOGLE_REVIEW_OPERATION_DEFINITION_ID
from ...application.operations.registry import OperationFrontendProjection
from ..operation_composition import build_production_operation_registry

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_production_publication_has_authority_and_review_contracts() -> None:
    registry = build_production_operation_registry()
    registration = registry.lookup_public_registration(GOOGLE_REVIEW_OPERATION_DEFINITION_ID)
    assert registration.access_resolver is not None
    assert registration.contract.review_projection_schema is not None
    assert registration.contract.interaction_response_schema is not None
    definition = registry.lookup(GOOGLE_REVIEW_OPERATION_DEFINITION_ID)
    assert OperationFrontendProjection.CLI in definition.permitted_frontends
    assert OperationFrontendProjection.MCP not in definition.permitted_frontends
    assert registry.lookup_public_registration("export.google-sheets").access_resolver is None
