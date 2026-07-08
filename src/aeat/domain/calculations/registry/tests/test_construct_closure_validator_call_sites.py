"""Construct closure evidence validation.

The modelo validator must route
:class:`~domain.calculations.registry.ConstructDefinition` rows through the
same official-source evidence gate as the revision-closure dispatcher, so a
layout-only source cannot make a construct filing-grade.

See Also:
    :func:`~domain.calculations.registry._validate_constructs.validate_construct_closure`
        Construct grounding gate exercised through the public validator.
    :class:`~domain.calculations.registry._validate.RegistryValidator`
        Modelo-level validator whose call path this regression pins.
"""

from __future__ import annotations

import pytest

from .._schema import ConstructDefinition
from .._validate import RegistryValidator
from ._referential_integrity_support import (
    REFERENCE_LEGAL_ID,
    REFERENCE_SOURCE_ID,
    RegistryValidationError,
    minimal_casilla,
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_validation_rejects_construct_without_official_source_evidence() -> None:
    """The revision validator must route constructs through evidence-tier checks."""

    catalogues = minimal_catalogues()
    layout_only_source = catalogues.sources[REFERENCE_SOURCE_ID].model_copy(update={"evidence_tier": "layout_authority"})
    casilla = minimal_casilla()
    construct = ConstructDefinition(
        id="construct.without-guidance",
        title="Construct without official guidance",
        casilla_ids=(casilla.id,),
        legal_refs=(REFERENCE_LEGAL_ID,),
        source_refs=(REFERENCE_SOURCE_ID,),
    )
    revision = minimal_revision(casillas=(casilla,), constructs=(construct,))

    with pytest.raises(
        RegistryValidationError,
        match=r"construct construct\.without-guidance requires official_source_guidance source evidence",
    ):
        RegistryValidator(
            catalogues.model_copy(update={"sources": {REFERENCE_SOURCE_ID: layout_only_source}}),
        ).validate_modelo(minimal_modelo(revision))
