"""A boolean answer bound to a one-byte text slot exports blank or ``X``.

DR131 (``aeat-dr-131-2026``) página 1 prints two such operator-answered campos, all alfanuméricos de
longitud 1 with valores ``blanco o "X"``: posición 109 (contribuyente con discapacidad
igual o superior al 33 por 100) and 613 (derecho a la deducción por vivienda habitual).
Posición 692 (declaración complementaria) is stated by the amendment evidence instead. DR184 (``aeat-dr-184-2025``) posición 82 reads ``X``
when the miembro remains one at 31 December. The operator answers each as a boolean
binding, so the answer reaches a text slot through the binding path. The expected bytes
are transcribed from the designs, never read from the layout under test; the whole
``export_draft`` path writes and reads them back.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope, open_ended_revision
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.casilla_id import validated_casilla_id
from ....core.modelo import Modelo
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....domain.filing.protocols import ModeloInputValue
from ....domain.filing.software_identity import development_mock_software_identity
from ....domain.submission.models import ModeloDraftStatus
from ..draft_construction import build_draft
from ..export import export_draft
from ..producer_snapshot import GeneralFilingProfileFacts, build_filing_producer_snapshot
from ..record_field_renderer import binding_field_value, format_field
from ..runtime import ModeloOperatorProfile
from .export_support import EXPORT_PERIOD, export_schema_provider, typed_producer_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

#: (binding, one-based posición in the página 1 record) of each boolean answer the design prints.
_MARKERS = (
    ("modelo-131.page1.discapacidad-33", 109),
    ("modelo-131.page1.vivienda-derecho-deduccion", 613),
)
_PAGE_ONE_OPEN = b"<T13101000>"


def _exported_page_one_marker(tmp_path: Path, binding: str, position: int, answer: str | None) -> str:
    base = typed_producer_snapshot(complementaria=False)
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo("131"),
        taxpayer_tax_id=base.taxpayer_tax_id,
        taxpayer_identity=base.taxpayer_identity,
        presenter=base.presenter,
        model_profile=GeneralFilingProfileFacts(),
        elections=base.elections,
        amendment_evidence=base.amendment_evidence,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )
    provider = export_schema_provider(filing_year=EXPORT_PERIOD.filing_year, period="1T", modelos=("131",))
    inputs: dict[str, ModeloInputValue] = {
        validated_casilla_id("03", surface="test_m131_marker.casilla"): Decimal("1000"),
        validated_casilla_id("05", surface="test_m131_marker.casilla"): Decimal("500"),
        "modelo-131.page1.actividad-1-epigrafe": "722",
        "modelo-131.page1.actividad-1-rendimiento-neto": Decimal("1200.50"),
        "modelo-131.dpa.epigrafe-iae": ["722"],
        "modelo-131.did.iban": "ES9121000418450200051332",
    }
    if answer is not None:
        inputs[binding] = answer
    draft = build_draft(
        modelo="131",
        period=EXPORT_PERIOD,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Export registry test"),
        inputs=inputs,
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    output_path = tmp_path / "modelo-131.txt"

    export_draft(
        draft,
        output_path=output_path,
        producer_snapshot=snapshot,
        product_software_identity=development_mock_software_identity(),
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        schema_provider=provider,
    )

    payload = output_path.read_bytes()
    start = payload.index(_PAGE_ONE_OPEN)
    return payload[start + position - 1 : start + position].decode("ascii")


@pytest.mark.parametrize(("binding", "position"), _MARKERS)
@pytest.mark.parametrize(
    ("answer", "expected"),
    [("yes", "X"), ("no", " "), (None, " ")],
    ids=("true", "false", "absent"),
)
def test_the_answered_box_exports_one_marker_byte(
    tmp_path: Path, binding: str, position: int, answer: str | None, expected: str
) -> None:
    assert _exported_page_one_marker(tmp_path, binding, position, answer) == expected


@pytest.mark.parametrize(
    ("answer", "expected"), [(True, "X"), (False, " "), (None, " ")], ids=("true", "false", "absent")
)
def test_modelo_184_member_at_year_end_slot_writes_the_design_marker(answer: bool | None, expected: str) -> None:
    snapshot = published_snapshot(
        "184", filing_year=max(open_ended_revision("184").valid_from.year, filing_year_envelope().floor), period="0A"
    )
    [field] = [
        candidate
        for layout in snapshot.revision.export_layouts
        for record in layout.records
        for candidate in record.fields
        if candidate.binding == "modelo-184-member-row-miembro-a-31-diciembre"
    ]
    assert (field.offset, field.length, field.data_type) == (82, 1, "text")

    assert field.binding is not None
    value = binding_field_value(field, {(field.binding, 1): answer}, 1)

    assert format_field(field, value) == expected
