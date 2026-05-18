"""Strict roundtrip across the encrypted FilingAmendmentRepository boundary.

``FilingAmendmentRepository`` persists :class:`FilingAmendment` records
at ``SensitivityClass.AUDIT`` — corrective filings derived from a
previously submitted filing.

Anti-tautology discipline: every defaultable field on the FilingDraft
inside the amendment carries a non-default value, every CasillaChange
has a non-None ``old_value`` (real correction, not a fresh entry), and
the amendment_kind is COMPLEMENTARIA which is the more constrained
shape (additive amendment over a prior filing).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
    override_master_key_provider,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings
from ..calculations.registry._schema import RegistrySnapshotRef
from ._amendment import (
    AmendmentKind,
    CasillaChange,
    FilingAmendment,
    make_amendment_id,
)
from ._complementaria_repository import FilingAmendmentRepository
from ._schema import (
    FilingDraft,
    FilingDraftStatus,
    FilingValue,
    FilingValueKind,
)


pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_amended_draft() -> FilingDraft:
    """Build the FilingDraft embedded inside the amendment."""

    now = datetime.now(UTC).replace(microsecond=0)
    return FilingDraft(
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
        status=FilingDraftStatus.DRAFT,
        values=(
            FilingValue(
                casilla_id="iva.devengado",
                value=Decimal("20500.00"),  # corrected upward by 500
                kind=FilingValueKind.LITERAL,
                source="amended literal",
            ),
            FilingValue(
                casilla_id="iva.resultado",
                value=Decimal("12845.67"),  # 500 higher than the original
                kind=FilingValueKind.COMPUTED,
                source="recomputed after iva.devengado correction",
                formula_trace=("iva.devengado", "iva.deducible"),
            ),
        ),
        binding_values=(),
        findings=(),
        created_at=now,
        updated_at=now,
        schema_version="schema-2025-1",
    )


def _populated_amendment() -> FilingAmendment:
    submission_id = "S-2025-001"
    delta = (
        CasillaChange(
            casilla_code="iva.devengado",
            old_value=Decimal("20000.00"),
            new_value=Decimal("20500.00"),
            reason="invoice F-2025-027 was issued at the wrong VAT rate",
        ),
        CasillaChange(
            casilla_code="iva.resultado",
            old_value=Decimal("12345.67"),
            new_value=Decimal("12845.67"),
            reason="recomputed downstream of iva.devengado",
        ),
    )
    now = datetime.now(UTC).replace(microsecond=0)
    return FilingAmendment(
        amendment_id=make_amendment_id(
            submission_id=submission_id,
            amendment_kind=AmendmentKind.COMPLEMENTARIA,
            delta=delta,
        ),
        submission_id=submission_id,
        original_csv="ABCD12345678EFGH",
        original_model="303",
        original_period="2025Q1",
        amendment_kind=AmendmentKind.COMPLEMENTARIA,
        delta=delta,
        amended_draft=_populated_amended_draft(),
        created_at=now,
    )


def test_filing_amendment_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A FilingAmendment with delta + amended draft roundtrips strictly."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "amendment-roundtrip.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine)

        original = _populated_amendment()
        repo = FilingAmendmentRepository()
        repo.save(original)
        loaded = repo.load(original.amendment_id)

        assert loaded is not None
        assert loaded == original
        # Per-field witnesses for the delta tuple (the most fragile
        # part — a save-drops-old_value regression would surface
        # here as None on load).
        assert len(loaded.delta) == 2
        assert loaded.delta[0].casilla_code == "iva.devengado"
        assert loaded.delta[0].old_value == Decimal("20000.00")
        assert loaded.delta[0].new_value == Decimal("20500.00")
        assert loaded.delta[1].casilla_code == "iva.resultado"
        # AmendmentKind enum identity + the nested amended_draft
        # carries its own typed substructure.
        assert loaded.amendment_kind is AmendmentKind.COMPLEMENTARIA
        assert loaded.amended_draft.snapshot_ref is not None
        assert loaded.amended_draft.snapshot_ref.revision_id == "2025-y-siguientes"
    finally:
        engine.dispose()
        override_master_key_provider(None)


def test_filing_amendment_emptied_delta_surfaces_at_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anti-tautology proof: emptying the delta tuple must surface on load.

    :class:`FilingAmendment` enforces ``delta: CasillaDelta =
    Field(min_length=1)`` — an amendment with no corrections is a
    semantically empty record that would silently invalidate the
    audit-trail purpose of the amendment catalogue. A persisted
    amendment whose delta tuple is emptied post-save MUST fail load
    via the min_length=1 constraint.

    Persists an amendment, reaches into ``SecureObjectRow`` via
    ``session_scope``, surgically empties the delta tuple in the
    encrypted JSON envelope, and asserts the load path catches the
    drift.

    If this test passes silently with an empty delta, the amendment
    catalogue boundary is tautological and the audit-trail contract
    is not actually enforced post-persistence.
    """

    import json as _json

    from sqlalchemy import select

    from ...adapters.persistence.storage.sql._orm import SecureObjectRow
    from ...adapters.persistence.storage.sql.session import session_scope
    from ._complementaria_repository import _AMENDMENT_NAMESPACE

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "amendment-anti-tautology.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine)
        original = _populated_amendment()
        repo = FilingAmendmentRepository()
        repo.save(original)

        with session_scope(engine) as session:
            all_rows = session.execute(select(SecureObjectRow)).scalars().all()
            amendment_rows = [r for r in all_rows if r.namespace == _AMENDMENT_NAMESPACE]
            assert len(amendment_rows) == 1, (
                f"expected one amendment row, found {len(amendment_rows)} "
                f"(namespaces: {sorted({r.namespace for r in all_rows})})"
            )
            row = amendment_rows[0]
            envelope = _json.loads(row.payload.decode("utf-8"))
            payload = envelope["payload"]
            assert payload.get("delta"), (
                "fixture must serialise a non-empty delta tuple for "
                "this proof test to be meaningful"
            )
            payload["delta"] = []
            row.payload = _json.dumps(envelope).encode("utf-8")

        regression_caught = False
        try:
            repo.load(original.amendment_id)
        except Exception:  # noqa: BLE001 - boundary may raise different types
            regression_caught = True
        assert regression_caught, (
            "anti-tautology proof failed: emptying the delta tuple "
            "did NOT surface on load. The amendment catalogue "
            "boundary is tautological and the audit-trail contract "
            "is not actually enforced post-persistence."
        )
    finally:
        engine.dispose()
        override_master_key_provider(None)
