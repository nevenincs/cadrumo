"""Roundtrip + anti-tautology proofs for binding-value provenance.

:class:`ModeloBindingValue` carries the regulatory grounding of a bound
casilla at parity with the casilla half (:class:`ModeloCasillaProvenance`):
a typed :class:`~aeat.core.BindingSourceKind` ``source`` plus ``legal_refs``
and ``source_refs`` populated from the registry binding definition. Those
values ride inside the encrypted :class:`ModeloDraft` persisted through the
FINANCIAL-classified :class:`ModeloDraftRepository`.

This module exercises the **encrypted persistence boundary** with real
adapters (the runtime ``EphemeralMasterKeyProvider``-backed secure store, a
real SQLite engine, the real serializer): it persists a draft whose binding
values carry NON-DEFAULT provenance, reloads it, and asserts strict pydantic
equality. It then proves the boundary is not tautological by surgically
dropping each provenance field from the on-disk JSON envelope and confirming
the load either raises ``ValidationError`` or returns a strictly-unequal
record. If that anti-tautology proof ever passed with the boundary broken,
every roundtrip in the filing suite would be suspect.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from ....adapters.persistence.storage.crypto._encrypted_columns import (
    decrypt_secure_object_payload,
    encrypt_secure_object_payload,
    secure_object_payload_aad,
)
from ....adapters.persistence.storage.sql._orm import SecureObjectRow
from ....adapters.persistence.storage.sql.session import session_scope
from ....core import BindingSourceKind, Period
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations.registry._schema import RegistrySnapshotRef
from .._repository import ModeloDraftRepository
from .._schema import (
    ModeloBindingValue,
    ModeloDraft,
    ModeloDraftStatus,
    ModeloValue,
    ModeloValueKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_ID = "filing-binding-provenance"


def _populated_draft() -> ModeloDraft:
    """Build a draft whose binding values carry NON-DEFAULT provenance.

    Every provenance field is set to a non-default value (a typed source
    kind that is not the first member, multi-entry legal/source refs, a
    populated row index) so a save-drops-field / load-re-defaults-field
    regression cannot pass the strict-equality witness vacuously.
    """
    now = datetime.now(UTC).replace(microsecond=0)
    return ModeloDraft(
        draft_id="b" * 64,
        modelo="130",
        period=Period.from_year_and_code(2025, "1T"),
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=RegistrySnapshotRef(
            modelo="130",
            revision_id="2019-y-siguientes",
            modelo_year=2025,
            period="1T",
        ),
        status=ModeloDraftStatus.BORRADOR,
        values=(
            ModeloValue(
                casilla_id="03",
                value=Decimal("8400.00"),
                kind=ModeloValueKind.LITERAL,
                source="user-supplied",
            ),
        ),
        binding_values=(
            ModeloBindingValue(
                binding_id="modelo-130-ingresos-ledger",
                value=Decimal("8400.00"),
                kind=ModeloValueKind.LITERAL,
                source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
                legal_refs=("ley-35-2006:art-27", "ley-35-2006:art-28"),
                source_refs=("AEAT.M130.2025.ingresos", "AEAT.M130.instrucciones"),
                row_index=1,
            ),
            ModeloBindingValue(
                binding_id="modelo-130-gastos-ledger",
                value=Decimal("1200.50"),
                kind=ModeloValueKind.LITERAL,
                source=BindingSourceKind.LEDGER_RENTA_EXPENSE_AGGREGATION,
                legal_refs=("ley-35-2006:art-30",),
                source_refs=("AEAT.M130.2025.gastos",),
            ),
        ),
        casilla_provenance=(),
        findings=(),
        created_at=now,
        updated_at=now,
        schema_version="schema-2025-1",
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
            assert income.source_refs == ("AEAT.M130.2025.ingresos", "AEAT.M130.instrucciones")
        finally:
            profile.repository._engine.dispose()


@pytest.mark.parametrize(
    "field_name",
    [
        "source",
        "legal_refs",
        "source_refs",
    ],
)
def test_boundary_catches_binding_provenance_field_drop(
    field_name: str,
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
            original = _populated_draft()
            ModeloDraftRepository(bucket_id=_BUCKET_ID).save(original)

            with session_scope(profile.repository._engine) as session:
                row = session.execute(select(SecureObjectRow).limit(1)).scalar_one()
                aad = secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version)
                plain = decrypt_secure_object_payload(bytes(row.payload), associated_data=aad)
                decoded = json.loads(plain.decode("utf-8"))
                binding_values = decoded["payload"]["binding_values"]
                assert binding_values, "fixture must serialise binding_values for this proof to be meaningful"
                assert field_name in binding_values[0], (
                    f"fixture must serialise binding-value {field_name!r} into the envelope payload"
                )
                del binding_values[0][field_name]
                row.payload = encrypt_secure_object_payload(json.dumps(decoded).encode("utf-8"), associated_data=aad)

            regression_caught = False
            try:
                mutated = ModeloDraftRepository(bucket_id=_BUCKET_ID).load(original.draft_id)
            except ValidationError:
                regression_caught = True
            else:
                assert mutated is not None
                assert mutated != original, (
                    f"binding-value field {field_name!r} was dropped on disk but the loaded "
                    "model is still equal to the original — the boundary regression is invisible"
                )
                regression_caught = True

            assert regression_caught, (
                f"boundary did not detect deliberate drop of binding-value field {field_name!r} — "
                "re-audit every roundtrip test in the suite"
            )
        finally:
            profile.repository._engine.dispose()
