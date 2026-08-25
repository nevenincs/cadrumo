"""Anti-tautology proof: simulate a regression and confirm the boundary catches it.

The roundtrip-test suite asserts strict pydantic equality across an
encrypted persistence boundary. The risk of a tautological test is
that a save-drops-X / load-re-defaults-X regression would still pass
the equality check if the test fixture used the default value for X.

This file exercises the *negative case* explicitly: it persists a
ModeloDraft through the encrypted store, then surgically mutates the
on-disk JSON envelope to delete one critical field and confirms the
load side either rejects the mutated payload or surfaces the missing
data as inequality against the original. The point is to prove
that the strict-equality pattern WOULD catch a real boundary drop,
which validates every other roundtrip test in the suite by
construction.

If this test ever passes the assertion when the boundary is broken
(i.e. load returns the original-equal record despite the mutated
JSON), every roundtrip test in the suite is suspect and must be
re-audited.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef

from ....adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from ....adapters.persistence.storage.sql import SecureObjectRow
from ....core import CasillaId, Period, validated_casilla_id
from ....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from .._schema import (
    ModeloApprovalBasis,
    ModeloCasillaProvenance,
    ModeloDraft,
    ModeloDraftStatus,
    ModeloValue,
    ModeloValueKind,
    compute_modelo_draft_id,
    registry_schema_version,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_ID = "d4c9ced7-e9c3-4ca7-87f7-4659a32d49e3"  # was 'filing-runtime'
_DRAFT_TIMESTAMP = datetime(2026, 5, 25, 13, 45, 0, tzinfo=UTC)
_APPROVED_AT = datetime(2026, 5, 25, 14, 30, tzinfo=UTC)
_OPTIONAL_FIELD_DROP_FIELDS = (
    "casilla_provenance",
    "notes",
    "approved_at",
    "approved_by",
    "review_checksum",
    "approval_basis",
)


_IVA_DEVENGADO_CASILLA: CasillaId = validated_casilla_id("iva.devengado")
_IVA_DEDUCIBLE_CASILLA: CasillaId = validated_casilla_id("iva.deducible")
_IVA_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_IVA_RESULTADO_OPERANDS = (_IVA_DEVENGADO_CASILLA, _IVA_DEDUCIBLE_CASILLA)


def _populated_draft(*, resultado: Decimal = Decimal("12345.67")) -> ModeloDraft:
    period = Period.from_year_and_code(2025, "1T")
    snapshot_ref = RegistrySnapshotRef(
        modelo="303",
        revision_id="2025-y-siguientes",
        modelo_year=2025,
        period="1T",
    )
    values = (
        ModeloValue(
            casilla_id=_IVA_RESULTADO_CASILLA,
            value=resultado,
            kind=ModeloValueKind.COMPUTED,
            source="computed from inputs",
            formula_trace_casilla_ids=_IVA_RESULTADO_OPERANDS,
        ),
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
                casilla_id=_IVA_DEVENGADO_CASILLA,
                formula_id="iva-cuota-devengada-formula",
                legal_refs=("ley-37-1992:art-92",),
                source_refs=("aeat-iva-2025",),
            ),
        ),
        findings=(),
        created_at=_DRAFT_TIMESTAMP,
        updated_at=_DRAFT_TIMESTAMP,
        schema_version=registry_schema_version(modelo="303", revision_id="2025-y-siguientes"),
        notes="Draft pending operator review",
        approved_at=_APPROVED_AT,
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


def test_boundary_catches_simulated_field_drop_via_corrupted_payload(
    tmp_path: Path,
) -> None:
    """Drop a typed field from the on-disk JSON envelope; load must refuse.

    The test:

      1. Saves a populated draft through the real encrypted boundary.
      2. Reaches into SQLite, decrypts the row's payload, mutates the
         JSON envelope to delete the ``snapshot_ref`` key, re-encrypts
         the mutated bytes, and writes them back.
      3. Loads the draft via the repository.

    The load side must raise a typed ``ValidationError`` because
    ``snapshot_ref`` is a required current field. If the mutated record
    loads, every roundtrip test in the suite is suspect and must be
    re-audited.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        try:
            original = _populated_draft()
            repo = ModeloDraftRepository(bucket_id=_BUCKET_ID)
            repo.save(original)

            # Sanity check: a normal load yields strict equality.
            baseline = repo.load(original.draft_id)
            assert baseline is not None
            assert baseline == original
            assert baseline.snapshot_ref is not None

            # Reach into the encrypted row and surgically delete the
            # snapshot_ref field from the JSON envelope payload. The
            # column accessor handles encrypt/decrypt automatically.
            stmt = select(SecureObjectRow).where(
                SecureObjectRow.namespace == ModeloDraftRepository.namespace,
                SecureObjectRow.object_key == original.draft_id,
            )

            def mutate(decoded):
                assert "snapshot_ref" in decoded["payload"], (
                    "fixture must serialise snapshot_ref into the envelope's payload for this test to be meaningful"
                )
                del decoded["payload"]["snapshot_ref"]

            mutate_encrypted_secure_object_json(
                profile.repository._engine,
                row_statement=stmt,
                mutate=mutate,
            )

            # Now reload through the repository. With ``snapshot_ref``
            # absent, strict model validation must refuse the payload.
            with pytest.raises(ValidationError):
                ModeloDraftRepository(bucket_id=_BUCKET_ID).load(original.draft_id)
        finally:
            profile.repository._engine.dispose()


# ---------------------------------------------------------------------------
# Field-drop proofs for the 6 optional fields that previously
# used pydantic defaults in the fixture (casilla_provenance, notes,
# approved_at, approved_by, review_checksum, approval_basis).
#
# Each case deletes the field's JSON key from the envelope payload on disk
# and confirms the load either raises ValidationError or returns a value
# that is strictly unequal to the original (i.e. the boundary surfaces the
# data-loss rather than silently re-defaulting the field to match).
# ---------------------------------------------------------------------------


def test_boundary_catches_optional_field_drop(tmp_path: Path) -> None:
    """Drop an optional field from the on-disk envelope; boundary must surface the loss.

    For each of the six optional fields that carry non-default values in the
    populated fixture, this test:

      1. Saves the draft through the real encrypted boundary.
      2. Surgically deletes the target field from the JSON envelope.
      3. Reloads and asserts either ``ValidationError`` or strict inequality
         against the original.

    If a field is silently re-defaulted on load and the test fixture used
    the default, equality would pass vacuously — which is the tautology this
    suite guards against.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        try:
            repo = ModeloDraftRepository(bucket_id=_BUCKET_ID)
            for index, field_name in enumerate(_OPTIONAL_FIELD_DROP_FIELDS, start=1):
                # Each case needs its own storage row. The repository refuses a
                # draft whose id is not its content address, so the cases are
                # separated by distinct CONTENT (a per-case resultado amount)
                # and the id follows from it, rather than by an invented id.
                original = _populated_draft(resultado=Decimal(f"12345.6{index}"))
                repo.save(original)

                stmt = select(SecureObjectRow).where(
                    SecureObjectRow.namespace == ModeloDraftRepository.namespace,
                    SecureObjectRow.object_key == original.draft_id,
                )

                def mutate(decoded, *, field: str = field_name):
                    assert field in decoded["payload"], (
                        f"fixture must serialise {field!r} into the envelope payload "
                        "for this field-drop case to be a meaningful proof"
                    )
                    del decoded["payload"][field]

                mutate_encrypted_secure_object_json(
                    profile.repository._engine,
                    row_statement=stmt,
                    mutate=mutate,
                )

                try:
                    mutated = repo.load(original.draft_id)
                except ValidationError:
                    continue
                assert mutated is not None
                assert mutated != original, (
                    f"field {field_name!r} was dropped from the envelope but the loaded "
                    "model is still equal to the original — the fixture used the pydantic "
                    "default for this field and the boundary regression is invisible"
                )
        finally:
            profile.repository._engine.dispose()
