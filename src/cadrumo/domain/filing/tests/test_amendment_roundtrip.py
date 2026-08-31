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

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.profile.filing_amendments import ModeloAmendmentRepository
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....core.storage_taxonomy import StorageCategory
from ....core.storage_taxonomy_locations import storage_path
from ....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ...calculations.registry.schema_references import RegistrySnapshotRef
from ..amendment import (
    AmendmentKind,
    CasillaChange,
    ModeloComplementaria,
    make_amendment_id,
)
from ..schema import (
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
_AMENDMENT_CREATED_AT = datetime(2026, 5, 25, 15, 0, 0, tzinfo=UTC)
_NAIVE_AMENDMENT_CREATED_AT = datetime(2026, 5, 25, 15, 0, 0)
_OFFSET_AMENDMENT_CREATED_AT = datetime(2026, 5, 25, 16, 0, 0, tzinfo=timezone(timedelta(hours=1)))


_IVA_DEVENGADO_CASILLA: CasillaId = validated_casilla_id("iva.devengado")
_IVA_DEDUCIBLE_CASILLA: CasillaId = validated_casilla_id("iva.deducible")
_IVA_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_IVA_RESULTADO_OPERANDS = (_IVA_DEVENGADO_CASILLA, _IVA_DEDUCIBLE_CASILLA)
_NONCANONICAL_IVA_DEVENGADO_CASILLA_ID = " iva.devengado "


def _populated_amended_draft() -> ModeloDraft:
    """Build the ModeloDraft embedded inside the amendment."""

    period = Period.from_year_and_code(2025, "1T")
    snapshot_ref = RegistrySnapshotRef(
        modelo="303",
        revision_id="2025-y-siguientes",
        modelo_year=2025,
        period="1T",
    )
    values = (
        ModeloValue(
            casilla_id=_IVA_DEVENGADO_CASILLA,
            value=Decimal("20500.00"),  # corrected upward by 500
            kind=ModeloValueKind.LITERAL,
            source="amended literal",
        ),
        ModeloValue(
            casilla_id=_IVA_RESULTADO_CASILLA,
            value=Decimal("12845.67"),  # 500 higher than the original
            kind=ModeloValueKind.COMPUTED,
            source="recomputed after iva.devengado correction",
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
        findings=(),
        created_at=_DRAFT_TIMESTAMP,
        updated_at=_DRAFT_TIMESTAMP,
        schema_version=registry_schema_version(modelo="303", revision_id="2025-y-siguientes"),
    )


def _populated_amendment() -> ModeloComplementaria:
    submission_id = "S-2025-001"
    delta = (
        CasillaChange(
            casilla_id=_IVA_DEVENGADO_CASILLA,
            old_value=Decimal("20000.00"),
            new_value=Decimal("20500.00"),
            reason="invoice F-2025-027 was issued at the wrong IVA rate",
        ),
        CasillaChange(
            casilla_id=_IVA_RESULTADO_CASILLA,
            old_value=Decimal("12345.67"),
            new_value=Decimal("12845.67"),
            reason="recomputed downstream of iva.devengado",
        ),
    )
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
        created_at=_AMENDMENT_CREATED_AT,
    )


def test_casilla_change_rejects_noncanonical_casilla_reference() -> None:
    with pytest.raises(ValidationError, match="casilla_id"):
        CasillaChange(
            casilla_id=_NONCANONICAL_IVA_DEVENGADO_CASILLA_ID,
            old_value=Decimal("20000.00"),
            new_value=Decimal("20500.00"),
            reason="noncanonical casilla id must fail before persistence",
        )


@pytest.mark.parametrize("created_at", (_NAIVE_AMENDMENT_CREATED_AT, _OFFSET_AMENDMENT_CREATED_AT))
def test_filing_amendment_refuses_ambiguous_created_at(created_at: datetime) -> None:
    """The persisted amendment audit instant must be explicitly UTC."""

    payload = _populated_amendment().model_dump()
    payload["created_at"] = created_at

    with pytest.raises(ValidationError, match=r"datetime must be in UTC|datetime must be timezone-aware"):
        ModeloComplementaria.model_validate(payload)


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
    assert loaded.delta[0].casilla_id == _IVA_DEVENGADO_CASILLA
    assert loaded.delta[0].old_value == Decimal("20000.00")
    assert loaded.delta[0].new_value == Decimal("20500.00")
    assert loaded.delta[1].casilla_id == _IVA_RESULTADO_CASILLA
    # AmendmentKind enum identity + the nested amended_draft
    # carries its own typed substructure.
    assert loaded.amendment_kind is AmendmentKind.COMPLEMENTARIA
    assert loaded.amended_draft.snapshot_ref is not None
    assert loaded.amended_draft.snapshot_ref.revision_id == "2025-y-siguientes"
    assert loaded.created_at == _AMENDMENT_CREATED_AT
    assert loaded.created_at.utcoffset() == timedelta()
    assert loaded.model_dump(mode="json")["created_at"] == "2026-05-25T15:00:00Z"


def test_filing_amendment_persists_only_to_the_secure_database_object(
    tmp_path: Path,
) -> None:
    """A saved amendment never reaches either plaintext ``submissions/amendments*`` directory.

    :data:`StorageCategory.SUBMISSIONS_AMENDMENTS` now declares
    no consumer at all. Its only one was the master-key rotation sweep,
    deleted with the shared-master model it belonged to, and even then that
    module only walked the directory looking for ``.envelope.json`` files to
    re-encrypt -- it was a sweep, never a writer. :class:`ModeloAmendmentRepository`'s own module
    docstring states "no plaintext amendment JSON or envelope file lands on
    disk"; this proves it for ``submissions/amendments``, mirroring
    ``test_put_file_reads_source_but_persists_only_secure_database_object``
    for the attachments store.

    :data:`StorageCategory.SUBMISSIONS_AMENDMENT_RESULTS` is checked here
    too rather than in its own test: the deleted master-key rotation sweep
    documented ``ModeloAmendmentRepository`` as "one consumer identity" bound
    to BOTH sibling directories under one shared HKDF context, while the
    repository never references an "amendment result" concept anywhere in its
    source -- that rotation-plan entry was a re-encryption-sweep target the
    directory could hold, never evidence of a real writer for it, and the
    sweep itself is now gone. Asserting
    both absences in the one place that persists an amendment keeps that
    shared-consumer relationship visible instead of splitting it across two
    tests that could drift independently.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        original = _populated_amendment()
        repo = ModeloAmendmentRepository(bucket_id=_BUCKET_ID)
        repo.save(original)

        assert repo.load(original.amendment_id) == original
        assert not storage_path(StorageCategory.SUBMISSIONS_AMENDMENTS).exists()
        assert not storage_path(StorageCategory.SUBMISSIONS_AMENDMENT_RESULTS).exists()


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

    from sqlalchemy import select

    from ....adapters.persistence.storage._secure_object_namespaces import FILING_AMENDMENTS_NAMESPACE
    from ....adapters.persistence.storage.sql._orm import SecureObjectRow
    from ....adapters.persistence.storage.sql.session import session_scope

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        try:
            original = _populated_amendment()
            repo = ModeloAmendmentRepository(bucket_id=_BUCKET_ID)
            repo.save(original)

            with session_scope(profile.repository._engine) as session:
                all_rows = session.execute(select(SecureObjectRow)).scalars().all()
                amendment_rows = [r for r in all_rows if r.namespace == FILING_AMENDMENTS_NAMESPACE.namespace]
                assert len(amendment_rows) == 1, (
                    f"expected one amendment row, found {len(amendment_rows)} "
                    f"(namespaces: {sorted({r.namespace for r in all_rows})})"
                )
            stmt = select(SecureObjectRow).where(
                SecureObjectRow.namespace == FILING_AMENDMENTS_NAMESPACE.namespace,
            )

            def mutate(envelope):
                payload = envelope["payload"]
                assert payload.get("delta"), (
                    "fixture must serialise a non-empty delta tuple for this proof test to be meaningful"
                )
                payload["delta"] = []

            mutate_encrypted_secure_object_json(
                profile.repository._engine,
                row_statement=stmt,
                mutate=mutate,
            )

            with pytest.raises(ValidationError, match="delta"):
                ModeloAmendmentRepository(bucket_id=_BUCKET_ID).load(original.amendment_id)
        finally:
            profile.repository._engine.dispose()
