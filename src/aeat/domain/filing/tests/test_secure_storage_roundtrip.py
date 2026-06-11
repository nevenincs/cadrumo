"""End-to-end roundtrip tests through the encrypted secure-object store.

The :mod:`aeat.domain.calculations.registry.test_cross_boundary_roundtrip`
suite asserts pydantic ``model_dump_json``/``model_validate_json``
identity. That covers the in-process JSON boundary but does not exercise
the encrypted persistence boundary: encrypt -> SQL row -> decrypt ->
pydantic reload. This file fills that gap for the
:class:`ModeloDraftRepository` path.

Tests fail strictly if the persistence boundary drops any field on the
typed envelope. They use real SQLite + real encryption (no mocks, no
stubs) so a regression in the envelope schema, the column-encryption
hook, or the repository load path surfaces as a strict pydantic
inequality, not a flaky equality check.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations.registry._schema import RegistrySnapshotRef
from .._repository import ModeloDraftRepository
from .._schema import (
    ModeloApprovalBasis,
    ModeloCasillaProvenance,
    ModeloDraft,
    ModeloDraftStatus,
    ModeloValue,
    ModeloValueKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_ID = "filing-runtime"


def _populated_draft() -> ModeloDraft:
    """Build a ModeloDraft with every richest-typed field populated.

    Surfaces data-loss in the persistence layer the moment it occurs:
    if any field is silently dropped during the encrypted round-trip,
    the strict pydantic equality fails with a diff showing the lost
    field.
    """

    now = datetime.now(UTC).replace(microsecond=0)
    return ModeloDraft(
        draft_id="d" * 64,
        modelo="303",
        period=Period.from_year_and_code(2025, "1T"),
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            revision_id="2025-y-siguientes",
            modelo_year=2025,
            period="1T",
        ),
        status=ModeloDraftStatus.BORRADOR,
        values=(
            ModeloValue(
                casilla_id="iva.devengado",
                value=Decimal("20000.00"),
                kind=ModeloValueKind.LITERAL,
                source="user-supplied",
            ),
            ModeloValue(
                casilla_id="iva.resultado-regimen-general",
                value=Decimal("12345.67"),
                kind=ModeloValueKind.COMPUTED,
                source="computed from iva.devengado - iva.deducible",
                formula_trace=("iva.devengado", "iva.deducible"),
            ),
        ),
        binding_values=(),
        casilla_provenance=(
            ModeloCasillaProvenance(
                casilla_id="iva.devengado",
                formula_id="iva-cuota-devengada-formula",
                legal_refs=("LIVA.art-92",),
                source_refs=("AEAT.IVA.2025.casilla-01",),
            ),
        ),
        findings=(),
        created_at=now,
        updated_at=now,
        schema_version="schema-2025-1",
        notes="Draft pending operator review",
        approved_at=datetime(2026, 5, 25, 14, 30, tzinfo=UTC),
        approved_by="operator-reviewer-1",
        review_checksum="a" * 64,
        approval_basis=ModeloApprovalBasis(
            draft_payload_fingerprint="b" * 64,
            draft_review_fingerprint="c" * 64,
            transaction_catalogue_fingerprint="d" * 64,
            category_profiles_fingerprint="e" * 64,
            schema_formula_fingerprint="f" * 64,
        ),
    )


def test_filing_draft_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A ModeloDraft saved through ModeloDraftRepository loads back byte-for-byte equal.

    Exercises the full encrypted-persistence boundary:

        ModeloDraft -> Envelope -> JSON bytes -> column encryption ->
            SQLite -> column decryption -> JSON bytes -> Envelope ->
                ModeloDraft.

    If any layer drops a field on the typed envelope (subject_tax_id,
    snapshot_ref, formula_trace on a ModeloValue, the period or
    revision_id of the snapshot_ref nested model, etc.), the strict
    pydantic equality fails. No mocks; the encryption hook is driven
    by the active bucket runtime.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        original = _populated_draft()
        repo = ModeloDraftRepository(bucket_id=_BUCKET_ID)
        repo.save(original)
        loaded = ModeloDraftRepository(bucket_id=_BUCKET_ID).load(original.draft_id)

    assert loaded is not None
    assert loaded == original

    # Per-field witnesses so a future regression diagnoses
    # immediately without diff-on-failure trawling.
    assert loaded.subject_tax_id == "12345678Z"
    assert loaded.snapshot_ref is not None
    assert loaded.snapshot_ref.modelo == "303"
    assert loaded.snapshot_ref.revision_id == "2025-y-siguientes"
    assert loaded.snapshot_ref.modelo_year == 2025
    assert loaded.snapshot_ref.period == "1T"
    computed = next(v for v in loaded.values if v.kind is ModeloValueKind.COMPUTED)
    assert computed.formula_trace == ("iva.devengado", "iva.deducible")
    assert len(loaded.casilla_provenance) == 1
    assert loaded.casilla_provenance[0].casilla_id == "iva.devengado"
    assert loaded.casilla_provenance[0].formula_id == "iva-cuota-devengada-formula"
    assert loaded.notes == "Draft pending operator review"
    assert loaded.approved_at == datetime(2026, 5, 25, 14, 30, tzinfo=UTC)
    assert loaded.approved_by == "operator-reviewer-1"
    assert loaded.review_checksum == "a" * 64
    assert loaded.approval_basis is not None
    assert loaded.approval_basis.draft_payload_fingerprint == "b" * 64


def test_calculation_revision_observations_survive_encrypted_storage(
    tmp_path: Path,
) -> None:
    """Typed ``CasillaObservation`` provenance survives the encrypted catalogue path.

    The calculation-revision catalogue is persisted through
    :class:`CalculationRevisionCatalogueRepository`, which wraps the
    catalogue in an :class:`Envelope[CalculationRevisionCatalogue]`
    and stores the JSON bytes encrypted at ``FINANCIAL`` sensitivity.
    A populated ``observations`` tuple on the inner
    :class:`CalculationRevision` carries operand_refs, operand_values,
    legal_refs, source_refs per casilla. Every one of those fields
    must survive the encrypt -> SQLite -> decrypt cycle; a regression
    in the envelope schema or the catalogue's serialization would
    drop them silently.
    """

    from ...calculations.registry._bindings import CasillaObservation
    from ...modelos._calculation_repository import (
        CalculationRevisionCatalogueRepository,
    )
    from ...modelos._calculation_revision import (
        CalculationRevision,
        CalculationRevisionCatalogue,
        CalculationRevisionState,
        derive_calculation_revision_id,
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        now = datetime.now(UTC).replace(microsecond=0)
        observation = CasillaObservation(
            casilla_id="iva.resultado-regimen-general",
            value=Decimal("12345.67"),
            formula_id="iva.formula.resultado",
            operand_refs=("iva.devengado", "iva.deducible"),
            operand_values=(Decimal("20000.00"), Decimal("7654.33")),
            legal_refs=("LIVA.art-94",),
            source_refs=("AEAT.IVA.2025",),
        )
        work_unit_id = "9" * 64
        casilla_values = {"iva.resultado-regimen-general": Decimal("12345.67")}
        revision = CalculationRevision(
            calculation_revision_id=derive_calculation_revision_id(
                work_unit_id=work_unit_id,
                inputs_snapshot={},
                binding_overrides={},
                casilla_values=casilla_values,
            ),
            work_unit_id=work_unit_id,
            state=CalculationRevisionState.BORRADOR,
            casilla_values=casilla_values,
            observations=(observation,),
            created_at=now,
            updated_at=now,
        )
        catalogue = CalculationRevisionCatalogue(
            revisions={revision.calculation_revision_id: revision},
        )

        repo = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID)
        repo.save(catalogue)
        loaded = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert loaded == catalogue
    loaded_revision = loaded.get(revision.calculation_revision_id)
    assert loaded_revision is not None
    # The typed envelope must be preserved; without it, the
    # operand_refs / operand_values / legal_refs / source_refs
    # provenance would be lost across the persistence boundary.
    assert loaded_revision.observations == (observation,)
    assert loaded_revision.observations[0].operand_refs == observation.operand_refs
    assert loaded_revision.observations[0].operand_values == observation.operand_values
    assert loaded_revision.observations[0].legal_refs == observation.legal_refs
    assert loaded_revision.observations[0].source_refs == observation.source_refs
