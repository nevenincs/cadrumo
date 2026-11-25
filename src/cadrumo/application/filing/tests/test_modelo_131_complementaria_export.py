"""The Modelo 131 declaration-level complementaria byte follows the amendment evidence.

DR131 ``aeat-dr-131-2024`` onwards prints página 1 posición 692, longitud 1, "Declaración
complementaria", alfanumérico with valores ``blanco o "X"``. An original filing leaves it
blank; a complementaria writes ``X``. The expected bytes are transcribed from the designs,
never read from the layout under test. Each case runs the whole ``export_draft`` path with
its post-write verification; the filing-kind reader round trip lives with the sede capture tests.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.modelo import Modelo
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....domain.calculations.registry.tests.authored_editions import authored_revisions
from ....domain.filing.software_identity import development_mock_software_identity
from ....domain.submission.models import ModeloDraftStatus
from ..draft_construction import build_draft
from ..export import export_draft
from ..producer_snapshot import GeneralFilingProfileFacts, build_filing_producer_snapshot
from ..runtime import ModeloOperatorProfile
from .export_support import export_schema_provider, typed_producer_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_PAGE_ONE_OPEN = b"<T13101000>"
_MARKER_POSITION = 692


def _exported_file(tmp_path: Path, *, filing_year: int, period: str, complementaria: bool) -> bytes:
    template = typed_producer_snapshot(complementaria=complementaria)
    snapshot = build_filing_producer_snapshot(
        modelo=Modelo("131"),
        taxpayer_tax_id=template.taxpayer_tax_id,
        taxpayer_identity=template.taxpayer_identity,
        presenter=template.presenter,
        model_profile=GeneralFilingProfileFacts(),
        elections=template.elections,
        amendment_evidence=template.amendment_evidence,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )
    provider = export_schema_provider(filing_year=filing_year, period=period, modelos=("131",))
    draft = build_draft(
        modelo="131",
        period=Period.from_year_and_code(filing_year, period),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Complementaria export"),
        inputs={
            validated_casilla_id("03", surface="test_m131_complementaria.casilla"): Decimal("1000"),
            validated_casilla_id("05", surface="test_m131_complementaria.casilla"): Decimal("500"),
            "modelo-131.page1.actividad-1-epigrafe": "722",
            "modelo-131.page1.actividad-1-rendimiento-neto": Decimal("1200.50"),
            "modelo-131.dpa.epigrafe-iae": ["722", "845"],
            "modelo-131.did.iban": "ES9121000418450200051332",
            **({"modelo-131-resultados-negativos-anteriores": Decimal("0")} if period != "1T" else {}),
        },
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
    return output_path.read_bytes()


# The oldest authored design predates the byte, so every later design is covered,
# each at the first period it serves.
_CARRYING_DESIGNS = authored_revisions("131")[1:]


@pytest.mark.parametrize(
    ("filing_year", "period"),
    [
        (design.valid_from.year, design.period_selector.periods_for_year(design.valid_from.year)[0])
        for design in _CARRYING_DESIGNS
    ],
    ids=[str(design.id) for design in _CARRYING_DESIGNS],
)
@pytest.mark.parametrize(
    ("complementaria", "byte"),
    [(False, b" "), (True, b"X")],
    ids=("original", "complementaria"),
)
def test_the_page_one_complementaria_byte_follows_the_amendment_evidence(
    tmp_path: Path,
    filing_year: int,
    period: str,
    complementaria: bool,
    byte: bytes,
) -> None:
    body = _exported_file(tmp_path, filing_year=filing_year, period=period, complementaria=complementaria)

    start = body.index(_PAGE_ONE_OPEN) + _MARKER_POSITION - 1
    assert body[start : start + 1] == byte
    dpa_starts = [i for i in range(len(body)) if body.startswith(b"<T131DPA00>", i)]
    assert [body[i + 11 : i + 12] for i in dpa_starts] == [b" ", b"C"]
