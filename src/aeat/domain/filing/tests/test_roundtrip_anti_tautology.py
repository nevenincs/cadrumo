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

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from ....adapters.persistence.storage.sql._orm import SecureObjectRow
from ....adapters.persistence.storage.sql.session import session_scope
from ....core._period import Period
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
                casilla_id="iva.resultado",
                value=Decimal("12345.67"),
                kind=ModeloValueKind.COMPUTED,
                source="computed from inputs",
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

    Two outcomes are acceptable proofs that the boundary is honest:

      * The load side raises a typed ``ValidationError``
        (strict-mode + extra='forbid' refuses the mutated shape).
      * The load side returns a ModeloDraft whose ``snapshot_ref`` is
        ``None`` instead of the original ``RegistrySnapshotRef`` — a
        strict-equality check against the original then fails.

    If neither outcome holds (i.e. the load somehow returns the
    original equal-record despite the JSON mutation), every roundtrip
    test in the suite is tautological and the entire pattern needs
    re-auditing. Without this test, that conclusion could not be drawn.
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
            with session_scope(profile.repository._engine) as session:
                stmt = select(SecureObjectRow).limit(1)
                row = session.execute(stmt).scalar_one()
                decoded = json.loads(row.payload.decode("utf-8"))
                assert "snapshot_ref" in decoded["payload"], (
                    "fixture must serialise snapshot_ref into the envelope's payload for this test to be meaningful"
                )
                del decoded["payload"]["snapshot_ref"]
                row.payload = json.dumps(decoded).encode("utf-8")

            # Now reload through the repository. With ``snapshot_ref``
            # absent, one of two things must happen:
            #   (a) the ModeloDraft model validation raises (strict mode);
            #   (b) the load succeeds but the loaded model has
            #       ``snapshot_ref=None`` (the field default), which makes
            #       it strictly unequal to the original.
            regression_caught = False
            try:
                mutated = ModeloDraftRepository(bucket_id=_BUCKET_ID).load(original.draft_id)
            except ValidationError:
                regression_caught = True
            else:
                assert mutated is not None
                # Strict equality against the original now fails: load
                # returned a draft missing the snapshot_ref the original
                # carried. The test fixture pattern (strict-eq witness)
                # catches the drop.
                assert mutated != original
                assert mutated.snapshot_ref is None
                regression_caught = True

            assert regression_caught, (
                "boundary did not detect a deliberate field drop — every "
                "roundtrip test in the suite is suspect and must be re-audited"
            )
        finally:
            profile.repository._engine.dispose()


# ---------------------------------------------------------------------------
# Parametrized field-drop proofs for the 6 optional fields that previously
# used pydantic defaults in the fixture (casilla_provenance, notes,
# approved_at, approved_by, review_checksum, approval_basis).
#
# Each case deletes the field's JSON key from the envelope payload on disk
# and confirms the load either raises ValidationError or returns a value
# that is strictly unequal to the original (i.e. the boundary surfaces the
# data-loss rather than silently re-defaulting the field to match).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field_name",
    [
        "casilla_provenance",
        "notes",
        "approved_at",
        "approved_by",
        "review_checksum",
        "approval_basis",
    ],
)
def test_boundary_catches_optional_field_drop(
    field_name: str,
    tmp_path: Path,
) -> None:
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
            original = _populated_draft()
            repo = ModeloDraftRepository(bucket_id=_BUCKET_ID)
            repo.save(original)

            with session_scope(profile.repository._engine) as session:
                stmt = select(SecureObjectRow).limit(1)
                row = session.execute(stmt).scalar_one()
                decoded = json.loads(row.payload.decode("utf-8"))
                assert field_name in decoded["payload"], (
                    f"fixture must serialise {field_name!r} into the envelope payload "
                    "for this parametrize case to be a meaningful proof"
                )
                del decoded["payload"][field_name]
                row.payload = json.dumps(decoded).encode("utf-8")

            regression_caught = False
            try:
                mutated = ModeloDraftRepository(bucket_id=_BUCKET_ID).load(original.draft_id)
            except ValidationError:
                regression_caught = True
            else:
                assert mutated is not None
                assert mutated != original, (
                    f"field {field_name!r} was dropped from the envelope but the loaded "
                    "model is still equal to the original — the fixture used the pydantic "
                    "default for this field and the boundary regression is invisible"
                )
                regression_caught = True

            assert regression_caught, (
                f"boundary did not detect deliberate drop of field {field_name!r} — "
                "re-audit every roundtrip test in the suite"
            )
        finally:
            profile.repository._engine.dispose()
