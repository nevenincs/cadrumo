"""Shared ModeloDraft construction for the encrypted filing round-trip tests."""

from __future__ import annotations

from datetime import UTC, datetime

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.filing.schema import (
    ModeloApprovalBasis,
    ModeloCasillaProvenance,
    ModeloDraft,
    ModeloValue,
    compute_modelo_draft_id,
    registry_schema_version,
)
from cadrumo.domain.submission.models import ModeloDraftStatus

DRAFT_TIMESTAMP = datetime(2026, 5, 25, 13, 45, 0, tzinfo=UTC)
APPROVED_AT = datetime(2026, 5, 25, 14, 30, tzinfo=UTC)
IVA_DEVENGADO_CASILLA: CasillaId = validated_casilla_id("iva.devengado")
IVA_DEDUCIBLE_CASILLA: CasillaId = validated_casilla_id("iva.deducible")
IVA_RESULTADO_OPERANDS = (IVA_DEVENGADO_CASILLA, IVA_DEDUCIBLE_CASILLA)


def approved_modelo_303_draft(values: tuple[ModeloValue, ...]) -> ModeloDraft:
    """Build a reviewed, approved 303 draft with every optional field populated around ``values``."""
    period = Period.from_year_and_code(2025, "1T")
    snapshot_ref = RegistrySnapshotRef(
        modelo="303",
        revision_id="2025-y-siguientes",
        modelo_year=2025,
        period="1T",
    )
    return ModeloDraft(
        draft_id=compute_modelo_draft_id(
            modelo="303",
            period=period,
            profile_tax_id="12345678Z",
            snapshot_ref=snapshot_ref,
            values=values,
        ),
        modelo="303",
        period=period,
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=snapshot_ref,
        status=ModeloDraftStatus.BORRADOR,
        values=values,
        binding_values=(),
        casilla_provenance=(
            ModeloCasillaProvenance(
                casilla_id=IVA_DEVENGADO_CASILLA,
                formula_id="iva-cuota-devengada-formula",
                legal_refs=("ley-37-1992:art-92",),
                source_refs=("aeat-iva-2025",),
            ),
        ),
        findings=(),
        created_at=DRAFT_TIMESTAMP,
        updated_at=DRAFT_TIMESTAMP,
        schema_version=registry_schema_version(modelo="303", revision_id="2025-y-siguientes"),
        notes="Draft pending operator review",
        approved_at=APPROVED_AT,
        approved_by="operator-reviewer-1",
        review_checksum="a" * 64,
        approval_basis=ModeloApprovalBasis(
            draft_payload_fingerprint="b" * 16,
            draft_review_fingerprint="c" * 64,
            transaction_catalogue_fingerprint="d" * 64,
            invoice_catalogue_fingerprint="1" * 64,
            prior_filing_observations_fingerprint="2" * 64,
            profile_activity_fingerprint="3" * 64,
            category_profiles_fingerprint="e" * 64,
            schema_formula_fingerprint="f" * 64,
        ),
    )
