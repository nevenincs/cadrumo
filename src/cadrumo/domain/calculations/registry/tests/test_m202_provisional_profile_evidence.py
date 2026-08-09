"""Modelo 202 provisional declaration-profile evidence boundary tests."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import RegistryCatalogues, RegistryValidator
from .._errors import RegistryValidationError
from .._schema import ExtractionProfileDefinition, ModeloDefinition
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M202_REVISION_ID = "2025-y-siguientes"
_M202_PROFILE_ID = "modelo-202-declaracion-pdf"


def _committed_modelo_202() -> tuple[ModeloDefinition, RegistryCatalogues]:
    """Load the live Modelo 202 registry entry and its shared catalogues."""
    return _committed_modelo("202")


def _m202_profile(modelo: ModeloDefinition) -> ExtractionProfileDefinition:
    revision = modelo.revisions[_M202_REVISION_ID]
    return next(profile for profile in revision.extraction_profiles if profile.id == _M202_PROFILE_ID)


def _with_profile(modelo: ModeloDefinition, replacement: ExtractionProfileDefinition) -> ModeloDefinition:
    """Return Modelo 202 with one real profile replaced for build-gate proof."""
    revision = modelo.revisions[_M202_REVISION_ID]
    profiles = tuple(
        replacement if profile.id == replacement.id else profile for profile in revision.extraction_profiles
    )
    updated_revision = revision.model_copy(update={"extraction_profiles": profiles})
    return modelo.model_copy(update={"revisions": {**modelo.revisions, updated_revision.id: updated_revision}})


def _validate(modelo: ModeloDefinition, catalogues: RegistryCatalogues) -> None:
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_committed_m202_provisional_profile_is_visible_but_not_round_trip_enrolled() -> None:
    """The live M202 profile remains usable while disclosing its evidence limit."""
    modelo, catalogues = _committed_modelo_202()
    profile = _m202_profile(modelo)

    assert profile.provisional_pending_specimen is True
    assert profile.confidence == "review_required"
    assert profile.corpus_round_trip_verified is False
    _validate(modelo, catalogues)


@pytest.mark.parametrize(
    ("update", "required_message"),
    (
        ({"confidence": "strict"}, "must set confidence='review_required'"),
        ({"corpus_round_trip_verified": True}, "cannot set corpus_round_trip_verified=true"),
    ),
)
def test_registry_build_rejects_m202_provisional_evidence_claim_mutation(
    update: dict[str, object],
    required_message: str,
) -> None:
    """A contradictory claim on the real M202 profile fails the registry gate."""
    modelo, catalogues = _committed_modelo_202()
    mutated = _with_profile(modelo, _m202_profile(modelo).model_copy(update=update))

    with pytest.raises(RegistryValidationError) as excinfo:
        _validate(mutated, catalogues)

    assert required_message in str(excinfo.value)
