"""Modelo 202 provisional declaration-profile evidence boundary tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.resources.bundled_data import bundled_path
from .._validate import RegistryValidator
from ..errors import RegistryValidationError
from ..schema import ModeloDefinition, RegistryCatalogues
from ..schema_extraction import ExtractionProfileDefinition, ExtractionTargetDefinition
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M202_REVISION_ID = "2025-y-siguientes"
_M202_PROFILE_ID = "9f8cdb06-8956-4a23-8db4-e7a51efa2ada"  # was 'modelo-202-declaracion-pdf'
_M202_TARGET_CASILLAS = ("01", "03", "04", "34")


def _committed_modelo_202() -> tuple[ModeloDefinition, RegistryCatalogues]:
    """Load the live Modelo 202 registry entry and its shared catalogues."""
    return _committed_modelo("202")


def _provisional_m202_profile(modelo: ModeloDefinition) -> ExtractionProfileDefinition:
    """Build the removed synthetic-only M202 profile against current casilla authority.

    M202's former profile was backed only by published text and had no real
    declaration specimen.  The current corpus therefore keeps no production
    extraction profile for it.  This fixture preserves the validator contract
    without restoring that unsupported production authority.
    """
    revision = modelo.revisions[_M202_REVISION_ID]
    casilla_ids = {casilla.id for casilla in revision.casillas}
    assert set(_M202_TARGET_CASILLAS) <= casilla_ids
    return ExtractionProfileDefinition(
        id=_M202_PROFILE_ID,
        surface="declaracion_pdf",
        artefact_kind="declaration_pdf",
        accepted_artefact_kinds=("declaration_pdf",),
        parser="cadrumo.adapters.inbound.declaracion.parser.parse_declaracion",
        provisional_pending_specimen=True,
        target_casillas=tuple(
            ExtractionTargetDefinition(
                casilla_id=casilla_id,
                match_strategy="numeric_casilla",
                value_kind="amount",
            )
            for casilla_id in _M202_TARGET_CASILLAS
        ),
        confidence="review_required",
        corpus_round_trip_verified=False,
        verification_source="synthetic_from_aeat_published_text",
        min_coverage=Decimal("1.0"),
        failure_semantics="fail_hard",
        legal_refs=revision.legal_refs,
        source_refs=revision.source_refs,
    )


def _with_provisional_profile(
    modelo: ModeloDefinition,
    profile: ExtractionProfileDefinition,
) -> ModeloDefinition:
    """Return M202 with the non-production provisional fixture enrolled."""
    revision = modelo.revisions[_M202_REVISION_ID]
    assert not revision.extraction_profiles
    updated_revision = revision.model_copy(update={"extraction_profiles": (profile,)})
    return modelo.model_copy(update={"revisions": {**modelo.revisions, updated_revision.id: updated_revision}})


def _validate(modelo: ModeloDefinition, catalogues: RegistryCatalogues) -> None:
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_committed_m202_has_no_declaration_pdf_profile_without_real_specimen() -> None:
    """Production extraction authority is absent until a real specimen grounds it."""
    modelo, _catalogues = _committed_modelo_202()

    for revision in modelo.revisions.values():
        assert all(profile.id != _M202_PROFILE_ID for profile in revision.extraction_profiles)
        assert all(profile.surface != "declaracion_pdf" for profile in revision.extraction_profiles)


def test_m202_provisional_profile_is_review_required_and_not_round_trip_enrolled() -> None:
    """A synthetic-only M202 profile remains explicitly provisional at build time."""
    modelo, catalogues = _committed_modelo_202()
    profile = _provisional_m202_profile(modelo)

    assert profile.provisional_pending_specimen is True
    assert profile.confidence == "review_required"
    assert profile.corpus_round_trip_verified is False
    _validate(_with_provisional_profile(modelo, profile), catalogues)


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
    """A contradictory claim on the provisional M202 profile fails the registry gate."""
    modelo, catalogues = _committed_modelo_202()
    profile = _provisional_m202_profile(modelo).model_copy(update=update)

    with pytest.raises(RegistryValidationError) as excinfo:
        _validate(_with_provisional_profile(modelo, profile), catalogues)

    assert required_message in str(excinfo.value)
