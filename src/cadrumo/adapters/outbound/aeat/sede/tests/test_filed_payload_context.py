"""Inbound framing never relaxes declaration-register identity checks."""

from datetime import UTC, datetime

import pytest

from ......core.period import Period
from ......domain.calculations.registry.export_parse import parse_filed_payload
from ......domain.calculations.registry.export_semantics import ExportDraftAttribute
from ......domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from ..declarations_observations import _verify_submitted_file_context
from ..declarations_schema import Declaracion
from ..errors import SedeParseError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.parametrize(("attribute", "body"), [("filing_year", b"2023"), ("period_code", b"2T")])
def test_filed_parser_retains_wrong_identity_for_context_refusal(attribute: str, body: bytes) -> None:
    field = ExportFieldDefinition.model_validate(
        dict(
            id="identity",
            offset=1,
            length=len(body),
            kind="draft",
            draft_attribute=ExportDraftAttribute(attribute),
            data_type="text",
            required=True,
            padding="none",
            justification="none",
            signed=False,
            legal_refs=("orden-eha-3786-2008:art-1",),
            source_refs=("aeat-dr-303-2024-early",),
        )
    )
    layout = ExportLayoutDefinition(
        id="identity-proof",
        legal_refs=field.legal_refs,
        source_refs=field.source_refs,
        records=(
            ExportRecordDefinition(
                id="identity",
                record_type="identity",
                order=0,
                encoding="iso-8859-1",
                line_ending="none",
                fields=(field,),
            ),
        ),
    )
    parsed = parse_filed_payload(layout, body)
    declaration = Declaracion(
        modelo="303",
        ejercicio=2024,
        period=Period.from_year_and_code(2024, "1T"),
        expediente_id="202430300000001A",
        estado="ALTA",
        presented_at=datetime(2024, 4, 20, tzinfo=UTC),
        justificante_link_text="Ver",
        archive_link_text="Ver",
    )
    with pytest.raises(SedeParseError, match="does not match declaration"):
        _verify_submitted_file_context({field.id: field}, parsed.fields, declaration=declaration)
