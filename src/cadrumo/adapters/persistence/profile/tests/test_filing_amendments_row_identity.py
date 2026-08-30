"""A filing amendment is bound to the row key it is filed under.

``ModeloAmendmentRepository`` stores each amendment under its own
``amendment_id``, so the object key and the decrypted payload are two encodings
of one fact. Nothing compared them: ``load`` validated only classification and
envelope version, and ``list_amendment_ids`` read ids out of payloads without
ever consulting the key each payload was filed under.

A valid amendment B written under A's row key was therefore returned by
``load("amend-A")`` as if it were A, and enumeration reported B twice while two
distinct rows existed -- so a complementaria consumer iterating filing history
could act on the wrong amendment for a period.

Real behaviour throughout: a real isolated bucket runtime, the real encrypted
SQL backend, the real repository. The substitution is performed through the
public secure-object writer, so the planted row is genuinely valid at every
layer beneath the identity check. Nothing is mocked.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from .....core.period import Period
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....domain.calculations.registry.schema_references import RegistrySnapshotRef
from .....domain.filing.amendment import CasillaChange, ModeloComplementaria
from .....domain.filing.schema import ModeloDraft, ModeloValue, ModeloValueKind, compute_modelo_draft_id, registry_schema_version
from .....domain.submission import ModeloDraftStatus
from ...storage import FILING_AMENDMENTS_NAMESPACE, Envelope, SecureObjectRowIdentityError
from ...storage.sql.secure_objects import SecureObjectRepository
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..filing_amendments import ModeloAmendmentRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "49494949-4949-4949-8949-494949494949"
_CASILLA: CasillaId = validated_casilla_id("01", surface="_AMENDMENT_ROW_IDENTITY_CASILLA")
_MODELO = "130"
_REVISION_ID = "2019-y-siguientes"
_NOW = datetime(2026, 4, 27, 10, 0, tzinfo=UTC)

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)


def _amendment(amendment_id: str) -> ModeloComplementaria:
    values = (
        ModeloValue(
            casilla_id=_CASILLA,
            value=Decimal("13000"),
            kind=ModeloValueKind.LITERAL,
            source=f"correction for {amendment_id}",
        ),
    )
    period = Period.from_year_and_code(2026, "1T")
    snapshot_ref = RegistrySnapshotRef(
        modelo=_MODELO,
        revision_id=_REVISION_ID,
        modelo_year=period.filing_year,
        period=period.registry_token,
    )
    amended_draft = ModeloDraft(
        draft_id=compute_modelo_draft_id(
            modelo=_MODELO,
            period=period,
            profile_tax_id="00000000T",
            snapshot_ref=snapshot_ref,
            values=values,
        ),
        modelo=_MODELO,
        period=period,
        profile_tax_id="00000000T",
        subject_tax_id="00000000T",
        snapshot_ref=snapshot_ref,
        status=ModeloDraftStatus.VALIDADO,
        values=values,
        created_at=_NOW,
        updated_at=_NOW,
        schema_version=registry_schema_version(modelo=_MODELO, revision_id=_REVISION_ID),
    )
    return ModeloComplementaria(
        amendment_id=amendment_id,
        submission_id="sub-row-identity",
        original_csv="CSVROWIDENT0001",
        original_model=_MODELO,
        original_period=period,
        delta=(
            CasillaChange(
                casilla_id=_CASILLA,
                old_value=Decimal("12500"),
                new_value=Decimal("13000"),
                reason=f"correction for {amendment_id}",
            ),
        ),
        amended_draft=amended_draft,
        created_at=_NOW,
    )


def _plant_under_foreign_key(payload: ModeloComplementaria, *, row_key: str) -> None:
    """Write ``payload``'s valid envelope under a DIFFERENT row key.

    Uses the public secure-object writer, so the planted row carries correct
    classification, schema version, AEAD binding, and revision lineage for the
    key it now occupies. Every layer beneath the identity check accepts it,
    which is what makes the substitution invisible without that check.
    """
    envelope = Envelope[ModeloComplementaria](
        schema_version=FILING_AMENDMENTS_NAMESPACE.schema_version,
        written_at=_NOW,
        classification=FILING_AMENDMENTS_NAMESPACE.sensitivity,
        payload=payload,
    )
    SecureObjectRepository().save(
        namespace=FILING_AMENDMENTS_NAMESPACE.namespace,
        object_key=row_key,
        classification=FILING_AMENDMENTS_NAMESPACE.sensitivity,
        schema_version=FILING_AMENDMENTS_NAMESPACE.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )


def test_amendment_round_trips_under_its_own_key() -> None:
    """POSITIVE CONTROL: an honestly-filed amendment still loads and enumerates.

    Without this, every refusal below is equally satisfied by a repository that
    refuses every row, which would take the whole complementaria history
    offline. This also pins that the identity check accepts the key the
    repository itself writes.
    """
    repo = ModeloAmendmentRepository()
    amendment = _amendment("amend-a")
    repo.save(amendment)

    assert ModeloAmendmentRepository().load("amend-a") == amendment
    assert repo.list_amendment_ids() == ("amend-a",)
    assert [a.amendment_id for a in repo.iter_amendments()] == ["amend-a"]


def test_load_refuses_a_foreign_amendment_filed_under_the_requested_key() -> None:
    """``load("amend-a")`` must not return amendment B.

    DISCRIMINATING: before the fix this returned B's payload with
    ``amendment_id == "amend-b"`` and no error at all, so a caller that trusted
    the id it asked for acted on a different filing's correction.
    """
    repo = ModeloAmendmentRepository()
    repo.save(_amendment("amend-a"))
    _plant_under_foreign_key(_amendment("amend-b"), row_key="amend-a")

    with pytest.raises(SecureObjectRowIdentityError):
        repo.load("amend-a")


def test_enumeration_refuses_a_foreign_amendment_rather_than_duplicating_it() -> None:
    """Enumeration must not report one amendment twice under two rows.

    ``list_amendment_ids`` read ids out of payloads, so the planted row
    contributed B's id a second time and ``iter_amendments`` then loaded B
    twice -- an amendment history showing two corrections where one exists.
    """
    repo = ModeloAmendmentRepository()
    repo.save(_amendment("amend-a"))
    repo.save(_amendment("amend-b"))
    _plant_under_foreign_key(_amendment("amend-b"), row_key="amend-a")

    with pytest.raises(SecureObjectRowIdentityError):
        repo.list_amendment_ids()
    with pytest.raises(SecureObjectRowIdentityError):
        list(repo.iter_amendments())


def test_the_refusal_names_the_identity_the_payload_rebuilds() -> None:
    """The error carries the id the payload claims, not the key requested.

    That is the diagnostic an operator needs to tell a substituted row from a
    merely absent one: the namespace plus the identity actually found.
    """
    repo = ModeloAmendmentRepository()
    repo.save(_amendment("amend-a"))
    _plant_under_foreign_key(_amendment("amend-b"), row_key="amend-a")

    with pytest.raises(SecureObjectRowIdentityError) as excinfo:
        repo.load("amend-a")

    assert excinfo.value.expected_identifier == "amend-b"
    assert excinfo.value.namespace == FILING_AMENDMENTS_NAMESPACE.namespace
