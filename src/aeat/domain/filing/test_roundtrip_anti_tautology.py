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

from ...adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base, SecureObjectRow
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...adapters.persistence.storage.sql.session import session_scope
from ...core.config import Settings
from ..calculations.registry._schema import RegistrySnapshotRef
from ._repository import ModeloDraftRepository
from ._schema import (
    ModeloDraft,
    ModeloDraftStatus,
    ModeloValue,
    ModeloValueKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_draft() -> ModeloDraft:
    now = datetime.now(UTC).replace(microsecond=0)
    return ModeloDraft(
        draft_id="d" * 64,
        modelo="303",
        period="2025Q1",
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            revision_id="2025-y-siguientes",
            filing_year=2025,
            period="1T",
        ),
        status=ModeloDraftStatus.DRAFT,
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
        findings=(),
        created_at=now,
        updated_at=now,
        schema_version="schema-2025-1",
    )


def test_boundary_catches_simulated_field_drop_via_corrupted_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "anti-tautology.db"
        # ``ModeloDraftRepository()`` constructs its own
        # ``SecureObjectRepository()`` which falls back to the
        # process-default engine. Setting the env var here ensures the
        # default engine and the explicit engine in this test point at
        # the same SQLite file.
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

            original = _populated_draft()
            repo = ModeloDraftRepository()
            repo.save(original)

            # Sanity check: a normal load yields strict equality.
            baseline = repo.load(original.draft_id)
            assert baseline is not None
            assert baseline == original
            assert baseline.snapshot_ref is not None

            # Reach into the encrypted row and surgically delete the
            # snapshot_ref field from the JSON envelope payload. The
            # column accessor handles encrypt/decrypt automatically.
            with session_scope(engine) as session:
                stmt = select(SecureObjectRow).limit(1)
                row = session.execute(stmt).scalar_one()
                decoded = json.loads(row.payload.decode("utf-8"))
                assert "snapshot_ref" in decoded["payload"], (
                    "fixture must serialise snapshot_ref into the envelope's payload "
                    "for this test to be meaningful"
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
                mutated = repo.load(original.draft_id)
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
            engine.dispose()
