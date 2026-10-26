"""Persistence-test support for stored justificante evidence metadata."""

from __future__ import annotations

import hashlib
from datetime import datetime

from pydantic import AnyHttpUrl, TypeAdapter

from cadrumo.adapters.inbound.pdf.source_provenance import source_pdf_reference_path
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.core.period import Period
from cadrumo.domain.justificante.schema import Justificante
from cadrumo.tests.aeat_literal_fixtures import justificante_cotejo_url


def persist_justificante_metadata(
    csv: str,
    *,
    modelo: str,
    filing_year: int,
    period: str,
    captured_at: datetime,
    tax_id: str = "X1234567L",
    presentation_id: str | None = None,
) -> None:
    """Persist a justificante record through the concrete profile repository."""
    pdf_bytes = f"%PDF-1.4\n% synthetic justificante {csv}\n%%EOF\n".encode()
    source_pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    JustificanteRepository().save(
        Justificante(
            csv=csv,
            modelo=modelo,
            period=Period.from_year_and_code(filing_year, period),
            ejercicio=str(filing_year),
            presentation_id=presentation_id,
            presented_at=captured_at,
            tax_id=tax_id,
            total_a_ingresar=None,
            total_a_devolver=None,
            verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
            source_pdf_path=source_pdf_reference_path(source_pdf_sha256),
            source_pdf_sha256=source_pdf_sha256,
            parsed_at=captured_at,
        ),
    )
