"""Related filing navigation preserves accepted, discarded and pending identities."""

from __future__ import annotations

from datetime import timedelta

import pytest

from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ..declarations_list import DeclarationListGroup, DeclarationListRow
from ..declarations_list_projection import worded_list_row
from ..declarations_workspace_contracts import DeclarationsWorkspaceFilingRefV1
from ..filing_record_view_operation import ModeloFilingRecordViewRequest, capture
from .test_filing_record_view_operation import PROFILE, filing_record_view_operation_bundle, source

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def related_filing_chain(*, branched: bool = True):
    unit, original = source()
    base = original.model_copy(
        update={
            "confirmation": AeatConfirmationState.CONFIRMADA,
            "external_evidence": ExternalEvidence(
                kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
                reference_id="EXP-BASE",
                imported_at=original.filed_at,
            ),
        }
    )
    discarded = original.model_copy(
        update={
            "filing_record_id": derive_filing_record_id(
                work_unit_id=unit.work_unit_id,
                calculation_revision_id="b" * 64,
                filed_by=original.filed_by,
            ),
            "calculation_revision_id": "b" * 64,
            "filed_at": original.filed_at + timedelta(days=1),
            "declaration_kind": FilingDeclarationKind.RECTIFICATIVA,
            "amends_filing_record_id": base.filing_record_id,
        }
    )
    pending = discarded.model_copy(
        update={
            "filing_record_id": derive_filing_record_id(
                work_unit_id=unit.work_unit_id,
                calculation_revision_id="c" * 64,
                filed_by=original.filed_by,
            ),
            "calculation_revision_id": "c" * 64,
            "filed_at": original.filed_at + timedelta(days=2),
        }
    )
    supersession = {
        "status": ModeloRecordStatus.SUPERSEDIDO,
        "superseded_by_filing_record_id": pending.filing_record_id,
        "superseded_at": pending.filed_at,
    }
    base = base.model_copy(update=supersession)
    discarded = discarded.model_copy(update=supersession | {"confirmation": AeatConfirmationState.DESCARTADA})
    if not branched:
        base = base.model_copy(update={"superseded_by_filing_record_id": discarded.filing_record_id})
        discarded = discarded.model_copy(
            update={
                "confirmation": AeatConfirmationState.CONFIRMADA,
                "external_evidence": ExternalEvidence(
                    kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
                    reference_id="EXP-FIRST-CORRECTION",
                    imported_at=discarded.filed_at,
                ),
            }
        )
        pending = pending.model_copy(update={"amends_filing_record_id": discarded.filing_record_id})
    records = (base, discarded, pending)
    return unit, records, ModeloRecordCatalogue(records={item.filing_record_id: item for item in reversed(records)})


@pytest.mark.parametrize("language", tuple(OutputLanguage))
def test_list_serves_the_entire_coordinate_in_time_order_with_distinct_links(language: OutputLanguage) -> None:
    unit, records, _catalogue = related_filing_chain()
    base, discarded, pending = records
    refs = tuple(DeclarationsWorkspaceFilingRefV1.from_record(item) for item in reversed(records))
    other_period = refs[0].model_copy(update={"period": Period.from_year_and_code(unit.filing_year, "2T")})
    member = refs[0].model_copy(update={"member_nif": "X0001500M"})
    row = DeclarationListRow(
        key="declaration",
        modelo=str(unit.modelo),
        period=unit.period,
        state="recorded",
        group=DeclarationListGroup.RECORDED,
    )

    projection = worded_list_row(row, language, (*refs, other_period, member))

    assert tuple(item.filing_record_id for item in projection.related_filings) == tuple(
        item.filing_record_id for item in records
    )
    first, retired, latest = projection.related_filings
    assert first.superseded_by_filing_record_id == pending.filing_record_id
    assert retired.confirmation is AeatConfirmationState.DESCARTADA
    assert retired.amends_filing_record_id == base.filing_record_id
    assert latest.amends_filing_record_id == base.filing_record_id
    assert latest.calculation_revision_id == pending.calculation_revision_id
    assert retired.filing_record_id == discarded.filing_record_id
    assert all(item.kind_words and item.confirmation_words and item.status_words for item in projection.related_filings)
    assert all(
        "workspace." not in item.kind_words + item.confirmation_words + item.status_words
        for item in projection.related_filings
    )


@pytest.mark.parametrize("branched", (True, False))
def test_view_navigation_returns_the_selected_immutable_receipt_and_both_branches(branched: bool) -> None:
    unit, records, catalogue = related_filing_chain(branched=branched)
    bundle = filing_record_view_operation_bundle(unit=unit, filing_catalogue=catalogue)

    for record in records:
        result = capture(
            ModeloFilingRecordViewRequest(
                profile_id=PROFILE,
                filing_record_id=record.filing_record_id,
                output_language=OutputLanguage.EN,
            ),
            bundle,
        )

        assert result.record.filing_record_id == record.filing_record_id
        assert result.historical_content.calculation_revision_id == record.calculation_revision_id
        assert result.historical_content.availability == "missing"
        assert tuple(item.filing_record_id for item in result.related_filings) == tuple(
            item.filing_record_id for item in records
        )
        assert result.comparison is not None
        assert result.comparison.base_filing_record_id == record.amends_filing_record_id
        assert result.comparison.availability == (
            "no_base" if record.amends_filing_record_id is None else "missing_content"
        )
