"""Filed-declaration and IVA wallet observations the observation store suites persist."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import AnyHttpUrl

from ......core.config import Settings
from ......core.period import Period
from ......domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition
from ......domain.calculations.registry.tests.published_authority import published_snapshot
from ..iva_compensation_wallet_parsing import WALLET_URL
from ..schema import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
)

_AEAT = Settings.external_constants().aeat
_COTEJO_DOCUMENT_URL = f"{_AEAT.domains.www6}{_AEAT.sede_paths.cotejo_document}"


def declaration_pdf_artefact(body: bytes) -> FiledDeclaracionArtefact:
    """A cotejo declaration PDF artefact whose digest and size are those of ``body``."""
    return FiledDeclaracionArtefact(
        kind="declaration_pdf",
        source_url=AnyHttpUrl(f"{_COTEJO_DOCUMENT_URL}?CSV=TUD4V9XAUV7QJ8QV"),
        content_type="application/pdf",
        byte_count=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        captured_at=datetime(newest_authored_edition("100") + 1, 7, 1, 9, 0, 0, tzinfo=UTC),
    )


def filed_declaration_observation(
    artefact: FiledDeclaracionArtefact, *, expediente_id: str = "202310013522456T"
) -> FiledDeclaracionObservation:
    """A presented Modelo 100 observation of the newest authored exercise carrying ``artefact``."""
    ejercicio = newest_authored_edition("100")
    return FiledDeclaracionObservation(
        modelo="100",
        ejercicio=ejercicio,
        period=Period.from_year_and_code(ejercicio, "0A"),
        expediente_id=expediente_id,
        status="PRESENTADA",
        presented_at=datetime(ejercicio + 1, 6, 30, 12, 34, 56, tzinfo=UTC),
        authenticated_identity="12345678Z",
        artefacts=(artefact,),
        registry_snapshot_ref=published_snapshot("100", filing_year=ejercicio, period="0A").snapshot_ref,
    )


def pending_wallet_observation(captured_at: datetime) -> IvaCompensationWalletObservation:
    """A second-quarter wallet observation of the horizon exercise holding 1200 pending from the first quarter."""
    year = filing_year_envelope().horizon
    return IvaCompensationWalletObservation(
        taxpayer_nif="12345678Z",
        authenticated_identity="12345678Z",
        target_year=year,
        target_period=Period.from_year_and_code(year, "2T"),
        rows=(
            IvaCompensationWalletRow(
                generation_year=year,
                generation_period=Period.from_year_and_code(year, "1T"),
                generated_amount=Decimal("1200"),
                applied_amount=Decimal("0"),
                pending_amount=Decimal("1200"),
                raw_label=f"{year} | 1T | 1200 | 0 | 1200",
            ),
        ),
        total_pending=Decimal("1200"),
        source_url=AnyHttpUrl(WALLET_URL),
        captured_at=captured_at,
        raw_sha256="b" * 64,
    )
