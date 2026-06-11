"""Strict roundtrip across the encrypted ModeloAmendmentRepository boundary.

``ModeloAmendmentRepository`` persists :class:`ModeloComplementaria`
and :class:`ModeloSustitutiva` records at ``SensitivityClass.AUDIT``
— corrective filings derived from a previously submitted filing.

Anti-tautology discipline: every defaultable field on the ModeloDraft
inside the amendment carries a non-default value, every CasillaChange
has a non-None ``old_value`` (real correction, not a fresh entry), and
the persisted variant is the LGT Art. 122.2 ``ModeloComplementaria``
(additive amendment over a prior filing).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core._period import Period
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations.registry._schema import RegistrySnapshotRef
from .._amendment import (
    AmendmentKind,
    CasillaChange,
    ModeloComplementaria,
    make_amendment_id,
)
from .._complementaria_repository import ModeloAmendmentRepository
from .._schema import (
    ModeloDraft,
    ModeloDraftStatus,
    ModeloValue,
    ModeloValueKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_ID = "filing-runtime"


def _populated_amended_draft() -> ModeloDraft:
    """Build the ModeloDraft embedded inside the amendment."""

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
                value=Decimal("20500.00"),  # corrected upward by 500
                kind=ModeloValueKind.LITERAL,
                source="amended literal",
            ),
            ModeloValue(
                casilla_id="iva.resultado",
                value=Decimal("12845.67"),  # 500 higher than the original
                kind=ModeloValueKind.COMPUTED,
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


def _populated_amendment() -> ModeloComplementaria:
    submission_id = "S-2025-001"
    delta = (
        CasillaChange(
            casilla_code="iva.devengado",
            old_value=Decimal("20000.00"),
            new_value=Decimal("20500.00"),
            reason="invoice F-2025-027 was issued at the wrong IVA rate",
        ),
        CasillaChange(
            casilla_code="iva.resultado",
            old_value=Decimal("12345.67"),
            new_value=Decimal("12845.67"),
            reason="recomputed downstream of iva.devengado",
        ),
    )
    now = datetime.now(UTC).replace(microsecond=0)
    return ModeloComplementaria(
        amendment_id=make_amendment_id(
            submission_id=submission_id,
            amendment_kind=AmendmentKind.COMPLEMENTARIA,
            delta=delta,
        ),
        submission_id=submission_id,
        original_csv="ABCD12345678EFGH",
        original_model="303",
        original_period=Period.from_year_and_code(2025, "1T"),
        delta=delta,
        amended_draft=_populated_amended_draft(),
        created_at=now,
    )


def test_filing_amendment_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A ModeloComplementaria with delta + amended draft roundtrips strictly."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        original = _populated_amendment()
        repo = ModeloAmendmentRepository(bucket_id=_BUCKET_ID)
        repo.save(original)
        loaded = ModeloAmendmentRepository(bucket_id=_BUCKET_ID).load(original.amendment_id)

    assert loaded is not None
    assert loaded == original
    # Per-field witnesses for the delta tuple (the most fragile
    # part - a save-drops-old_value regression would surface here as
    # None on load).
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


def test_filing_amendment_emptied_delta_surfaces_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: emptying the delta tuple must surface on load.

    :class:`ModeloComplementaria` enforces ``delta: CasillaDelta =
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

    from ....adapters.persistence.storage.sql._orm import SecureObjectRow
    from ....adapters.persistence.storage.sql.session import session_scope
    from .._complementaria_repository import _AMENDMENT_NAMESPACE

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        try:
            original = _populated_amendment()
            repo = ModeloAmendmentRepository(bucket_id=_BUCKET_ID)
            repo.save(original)

            with session_scope(profile.repository._engine) as session:
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
                    "fixture must serialise a non-empty delta tuple for this proof test to be meaningful"
                )
                payload["delta"] = []
                row.payload = _json.dumps(envelope).encode("utf-8")

            with pytest.raises(ValidationError, match="delta"):
                ModeloAmendmentRepository(bucket_id=_BUCKET_ID).load(original.amendment_id)
        finally:
            profile.repository._engine.dispose()
