"""Amendment links between filing records are validated by the catalogue and survive encrypted storage.

An amendment must name a baseline that exists in the same catalogue, at the same
filing coordinate, and the baseline must name the amendment as its successor.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.core.period import Period
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
    derive_filing_record_id,
)

from .filing_record_support import BUCKET_ID, FILING_YEAR, PERIOD_2T, RECORD_BUCKET_ID, hex_blob

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _amendment_pair(
    *,
    target_id_override: str | None = None,
    amendment_period: Period | None = None,
    amendment_filing_year: int | None = None,
    baseline_successor_override: str | None = None,
) -> ModeloRecordCatalogue:
    """Build a baseline plus an amendment whose link can be steered off target."""
    bucket_id = RECORD_BUCKET_ID
    work_unit_id = hex_blob("a")
    baseline_revision = hex_blob("b")
    amendment_revision = hex_blob("c")
    baseline_filed_at = datetime(FILING_YEAR, 7, 1, 9, 0, 0, tzinfo=UTC)
    amendment_filed_at = baseline_filed_at + timedelta(days=45)

    baseline_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=baseline_revision,
        filed_by="aeat.cli.modelo.file",
    )
    amendment_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=amendment_revision,
        filed_by="aeat.cli.modelo.amend",
    )
    baseline = ModeloRecord(
        filing_record_id=baseline_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=baseline_revision,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=FILING_YEAR,
        period=PERIOD_2T,
        filed_at=baseline_filed_at,
        filed_by="aeat.cli.modelo.file",
        status=ModeloRecordStatus.SUPERSEDIDO,
        superseded_at=amendment_filed_at,
        superseded_by_filing_record_id=baseline_successor_override or amendment_id,
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )
    period = amendment_period or PERIOD_2T
    amendment = ModeloRecord(
        filing_record_id=amendment_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=amendment_revision,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=amendment_filing_year or FILING_YEAR,
        period=period,
        filed_at=amendment_filed_at,
        filed_by="aeat.cli.modelo.amend",
        status=ModeloRecordStatus.VIGENTE,
        amends_filing_record_id=target_id_override or baseline_id,
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.COMPLEMENTARIA,
    )
    return ModeloRecordCatalogue(records={baseline_id: baseline, amendment_id: amendment})


def test_amendment_link_to_a_record_outside_the_catalogue_is_refused() -> None:
    """A complementaria must correct a filing that exists, not a claimed one."""
    with pytest.raises(ValidationError, match="not in this catalogue"):
        _amendment_pair(target_id_override=hex_blob("f"))


def test_amendment_link_to_itself_is_refused() -> None:
    """A record cannot be its own amendment baseline."""
    bucket_id = RECORD_BUCKET_ID
    work_unit_id = hex_blob("a")
    revision = hex_blob("b")
    record_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision,
        filed_by="aeat.cli.modelo.amend",
    )
    self_amending = ModeloRecord(
        filing_record_id=record_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=FILING_YEAR,
        period=PERIOD_2T,
        filed_at=datetime(FILING_YEAR, 7, 1, 9, 0, 0, tzinfo=UTC),
        filed_by="aeat.cli.modelo.amend",
        status=ModeloRecordStatus.VIGENTE,
        amends_filing_record_id=record_id,
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.COMPLEMENTARIA,
    )

    with pytest.raises(ValidationError, match="cannot amend itself"):
        ModeloRecordCatalogue(records={record_id: self_amending})


def test_amendment_link_across_filing_coordinates_is_refused() -> None:
    """An amendment corrects the same (bucket, modelo, year, period) coordinate."""
    with pytest.raises(ValidationError, match="across filing coordinates"):
        _amendment_pair(
            amendment_period=Period.from_year_and_code(FILING_YEAR, "3T"),
        )


def test_resolvable_same_coordinate_amendment_survives_encrypted_storage(
    tmp_path: Path,
) -> None:
    """Valid parity: a resolvable, distinct, same-coordinate link round-trips."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID):
        original = _amendment_pair()
        ModeloRecordCatalogueRepository(bucket_id=BUCKET_ID).save(original)
        loaded = ModeloRecordCatalogueRepository(bucket_id=BUCKET_ID).load()

    assert loaded == original
    amendment = loaded.current_for(
        bucket_id=RECORD_BUCKET_ID,
        modelo="303",
        filing_year=FILING_YEAR,
        period=PERIOD_2T,
    )
    assert amendment is not None
    assert amendment.amends_filing_record_id is not None
    baseline = loaded.get(amendment.amends_filing_record_id)
    assert baseline is not None
    assert baseline.filing_record_id != amendment.filing_record_id
    assert (baseline.bucket_id, baseline.modelo, baseline.filing_year, baseline.period) == (
        amendment.bucket_id,
        amendment.modelo,
        amendment.filing_year,
        amendment.period,
    )


def test_one_sided_amendment_link_is_refused() -> None:
    """Both records must agree about the amendment relationship they share.

    The three-record disagreement: the amendment correctly resolves to its
    baseline, but the baseline names a third record as its successor. Read
    forwards the chain is coherent; read backwards it is not, so the audit
    history depends on which end you start from.
    """
    third_party_successor = hex_blob("e")

    with pytest.raises(ValidationError, match="one-sided amendment link"):
        _amendment_pair(baseline_successor_override=third_party_successor)


def test_amendment_whose_baseline_names_no_successor_is_refused() -> None:
    """An amendment with no answering back-reference is the same one-sided defect.

    Reaches the refusal through a baseline that is still current, so the
    supersession side of the link is absent rather than merely wrong.
    """
    bucket_id = RECORD_BUCKET_ID
    work_unit_id = hex_blob("a")
    baseline_revision = hex_blob("b")
    amendment_revision = hex_blob("c")
    baseline_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=baseline_revision,
        filed_by="aeat.cli.modelo.file",
    )
    amendment_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=amendment_revision,
        filed_by="aeat.cli.modelo.amend",
    )
    baseline_filed_at = datetime(FILING_YEAR, 7, 1, 9, 0, 0, tzinfo=UTC)
    baseline = ModeloRecord(
        filing_record_id=baseline_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=baseline_revision,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=FILING_YEAR,
        period=PERIOD_2T,
        filed_at=baseline_filed_at,
        filed_by="aeat.cli.modelo.file",
        status=ModeloRecordStatus.VIGENTE,
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )
    amendment = ModeloRecord(
        filing_record_id=amendment_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=amendment_revision,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=FILING_YEAR,
        period=PERIOD_2T,
        filed_at=baseline_filed_at + timedelta(days=45),
        filed_by="aeat.cli.modelo.amend",
        status=ModeloRecordStatus.SUPERSEDIDO,
        superseded_at=baseline_filed_at + timedelta(days=90),
        superseded_by_filing_record_id=hex_blob("e"),
        amends_filing_record_id=baseline_id,
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.COMPLEMENTARIA,
    )

    with pytest.raises(ValidationError, match="one-sided amendment link"):
        ModeloRecordCatalogue(records={baseline_id: baseline, amendment_id: amendment})


def test_agreeing_amendment_link_is_accepted() -> None:
    """Valid parity: forward and reverse links naming each other pass."""
    catalogue = _amendment_pair()

    amendment = catalogue.current_for(
        bucket_id=RECORD_BUCKET_ID,
        modelo="303",
        filing_year=FILING_YEAR,
        period=PERIOD_2T,
    )
    assert amendment is not None
    assert amendment.amends_filing_record_id is not None
    baseline = catalogue.get(amendment.amends_filing_record_id)
    assert baseline is not None
    assert baseline.superseded_by_filing_record_id == amendment.filing_record_id


def test_amendment_chain_of_three_agrees_at_every_hop() -> None:
    """A -> B -> C: each hop's forward and reverse links must name each other."""
    bucket_id = RECORD_BUCKET_ID
    work_unit_id = hex_blob("a")
    first_filed_at = datetime(FILING_YEAR, 7, 1, 9, 0, 0, tzinfo=UTC)
    revisions = (hex_blob("b"), hex_blob("c"), hex_blob("d"))
    actors = ("aeat.cli.modelo.file", "aeat.cli.modelo.amend", "aeat.cli.modelo.amend")
    ids = tuple(
        derive_filing_record_id(
            work_unit_id=work_unit_id,
            calculation_revision_id=revision,
            filed_by=actor,
        )
        for revision, actor in zip(revisions, actors, strict=True)
    )
    records: dict[str, ModeloRecord] = {}
    for index, (record_id, revision, actor) in enumerate(zip(ids, revisions, actors, strict=True)):
        is_last = index == len(ids) - 1
        filed_at = first_filed_at + timedelta(days=45 * index)
        records[record_id] = ModeloRecord(
            filing_record_id=record_id,
            work_unit_id=work_unit_id,
            calculation_revision_id=revision,
            bucket_id=bucket_id,
            modelo=ModeloCode("303"),
            filing_year=FILING_YEAR,
            period=PERIOD_2T,
            filed_at=filed_at,
            filed_by=actor,
            status=ModeloRecordStatus.VIGENTE if is_last else ModeloRecordStatus.SUPERSEDIDO,
            superseded_at=None if is_last else filed_at + timedelta(days=45),
            superseded_by_filing_record_id=None if is_last else ids[index + 1],
            amends_filing_record_id=None if index == 0 else ids[index - 1],
            origin=FilingOrigin.LOCAL,
            confirmation=AeatConfirmationState.PENDIENTE,
            declaration_kind=FilingDeclarationKind.COMPLEMENTARIA,
        )

    catalogue = ModeloRecordCatalogue(records=records)

    assert len(catalogue) == 3
    for index, record_id in enumerate(ids[1:], start=1):
        record = catalogue.get(record_id)
        assert record is not None
        assert record.amends_filing_record_id == ids[index - 1]
        baseline = catalogue.get(ids[index - 1])
        assert baseline is not None
        assert baseline.superseded_by_filing_record_id == record_id
