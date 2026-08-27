"""Roundtrip + anti-tautology proofs for binding-value provenance.

:class:`ModeloBindingValue` carries the regulatory grounding of a bound
casilla at parity with the casilla half (:class:`ModeloCasillaProvenance`):
a typed :class:`~cadrumo.core.BindingSourceKind` ``source`` plus ``legal_refs``
and ``source_refs`` populated from the registry binding definition. Those
values ride inside the encrypted :class:`ModeloDraft` persisted through the
FINANCIAL-classified :class:`ModeloDraftRepository`.

This module exercises the **encrypted persistence boundary** with real
adapters (the test-support ``EphemeralMasterKeyProvider``-backed secure store, a
real SQLite engine, the real serializer): it persists a draft whose binding
values carry NON-DEFAULT provenance, reloads it, and asserts strict pydantic
equality. It then proves the boundary is not tautological by surgically
dropping each provenance field from the on-disk JSON envelope and confirming
the load either raises ``ValidationError`` or returns a strictly-unequal
record. If that anti-tautology proof ever passed with the boundary broken,
every roundtrip in the filing suite would be suspect.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from ....adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from ....adapters.persistence.storage.sql import SecureObjectRow
from ....core import BindingSourceKind, CasillaId, Period, validated_casilla_id
from ....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ...calculations.registry.schema_references import RegistrySnapshotRef
from .._schema import (
    ModeloBindingValue,
    ModeloDraft,
    ModeloDraftStatus,
    ModeloValue,
    ModeloValueKind,
    compute_modelo_draft_id,
    registry_schema_version,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_ID = "54b1b7fc-dbe4-4295-b691-fbb219b96b68"  # was 'filing-binding-provenance'
_DRAFT_TIMESTAMP = datetime(2026, 5, 25, 13, 45, 0, tzinfo=UTC)
_PROVENANCE_FIELDS = ("source", "legal_refs", "source_refs")
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id(
    "03",
    surface="_M130_RENDIMIENTO_NETO_CASILLA",
)


def _populated_draft(*, rendimiento: Decimal = Decimal("8400.00")) -> ModeloDraft:
    """Build a draft whose binding values carry NON-DEFAULT provenance.

    Every provenance field is set to a non-default value (a typed source
    kind that is not the first member, multi-entry legal/source refs, a
    populated row index) so a save-drops-field / load-re-defaults-field
    regression cannot pass the strict-equality witness vacuously.
    """
    period = Period.from_year_and_code(2025, "1T")
    snapshot_ref = RegistrySnapshotRef(
        modelo="130",
        revision_id="2019-y-siguientes",
        modelo_year=2025,
        period="1T",
    )
    values = (
        ModeloValue(
            casilla_id=_M130_RENDIMIENTO_NETO_CASILLA,
            value=rendimiento,
            kind=ModeloValueKind.LITERAL,
            source="user-supplied",
        ),
    )
    binding_values = (
        ModeloBindingValue(
            binding_id="modelo-130-ingresos-ledger",
            value=Decimal("8400.00"),
            kind=ModeloValueKind.LITERAL,
            source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
            legal_refs=("ley-35-2006:art-27", "ley-35-2006:art-28"),
            source_refs=("aeat-m130-2025-ingresos", "aeat-m130-instrucciones"),
            row_index=1,
        ),
        ModeloBindingValue(
            binding_id="modelo-130-gastos-ledger",
            value=Decimal("1200.50"),
            kind=ModeloValueKind.LITERAL,
            source=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
            legal_refs=("ley-35-2006:art-30",),
            source_refs=("aeat-m130-2025-gastos",),
        ),
    )
    return ModeloDraft(
        draft_id=compute_modelo_draft_id(
            modelo="130",
            period=period,
            profile_tax_id="12345678Z",
            snapshot_ref=snapshot_ref,
            values=values,
            binding_values=binding_values,
        ),
        modelo="130",
        period=period,
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=snapshot_ref,
        status=ModeloDraftStatus.BORRADOR,
        values=values,
        binding_values=binding_values,
        casilla_provenance=(),
        findings=(),
        created_at=_DRAFT_TIMESTAMP,
        updated_at=_DRAFT_TIMESTAMP,
        schema_version=registry_schema_version(modelo="130", revision_id="2019-y-siguientes"),
        notes="Draft pending operator review",
    )


def test_binding_value_provenance_roundtrips_through_encrypted_boundary(
    tmp_path: Path,
) -> None:
    """Persist NON-DEFAULT binding provenance and assert strict equality on reload."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        try:
            original = _populated_draft()
            ModeloDraftRepository(bucket_id=_BUCKET_ID).save(original)

            loaded = ModeloDraftRepository(bucket_id=_BUCKET_ID).load(original.draft_id)
            assert loaded is not None
            assert loaded == original

            # The typed source kind, legal refs, and source refs all survive
            # the encrypted cycle as the exact values written.
            by_id = {bv.binding_id: bv for bv in loaded.binding_values}
            income = by_id["modelo-130-ingresos-ledger"]
            assert income.source is BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION
            assert income.legal_refs == ("ley-35-2006:art-27", "ley-35-2006:art-28")
            assert income.source_refs == ("aeat-m130-2025-ingresos", "aeat-m130-instrucciones")
        finally:
            profile.repository._engine.dispose()


def test_boundary_catches_binding_provenance_field_drop(
    tmp_path: Path,
) -> None:
    """Drop a binding-value provenance field on disk; the boundary must surface it.

    Each case persists the populated draft, surgically deletes the target
    provenance key from the first binding value inside the decrypted JSON
    envelope, re-encrypts, and reloads. Two outcomes prove the boundary is
    honest:

      * the load raises a typed ``ValidationError`` (the required
        ``source`` enum or strict shape refuses the mutated payload); or
      * the load returns a draft whose binding value re-defaults the field
        (``legal_refs`` / ``source_refs`` to ``()``), making it strictly
        unequal to the original.

    If neither holds the strict-equality pattern is tautological.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        try:
            repository = ModeloDraftRepository(bucket_id=_BUCKET_ID)
            for index, field_name in enumerate(_PROVENANCE_FIELDS, start=1):
                # Each case needs its own storage row. The repository refuses a
                # draft whose id is not its content address, so the cases are
                # separated by distinct CONTENT (a per-case rendimiento amount)
                # and the id follows from it, rather than by an invented id.
                original = _populated_draft(rendimiento=Decimal(f"8400.0{index}"))
                repository.save(original)

                stmt = select(SecureObjectRow).where(
                    SecureObjectRow.namespace == ModeloDraftRepository.namespace,
                    SecureObjectRow.object_key == original.draft_id,
                )

                def mutate(decoded, *, field: str = field_name):
                    binding_values = decoded["payload"]["binding_values"]
                    assert binding_values, "fixture must serialise binding_values for this proof to be meaningful"
                    assert field in binding_values[0], (
                        f"fixture must serialise binding-value {field!r} into the envelope payload"
                    )
                    del binding_values[0][field]

                mutate_encrypted_secure_object_json(
                    profile.repository._engine,
                    row_statement=stmt,
                    mutate=mutate,
                )

                try:
                    mutated = repository.load(original.draft_id)
                except ValidationError:
                    continue
                assert mutated is not None
                assert mutated != original, (
                    f"binding-value field {field_name!r} was dropped on disk but the loaded "
                    "model is still equal to the original — the boundary regression is invisible"
                )
        finally:
            profile.repository._engine.dispose()
