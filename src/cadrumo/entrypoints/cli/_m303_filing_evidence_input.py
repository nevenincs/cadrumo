"""Canonical CLI loader for immutable Modelo 303 filing evidence."""

from __future__ import annotations

from pathlib import Path

import typer
from pydantic import ValidationError

from ...core import Modelo
from ...core.period import Period
from ...core.external_constants import UTF_8_ENCODING
from ...core.i18n import tr
from ...domain.modelos.calculation_revision import FilingInstanceEvidence


def m303_filing_instance_evidence_from_cli(
    *,
    modelo: str,
    period: Period,
    evidence_file: Path | None,
) -> FilingInstanceEvidence | None:
    """Load one complete typed evidence document before revision creation."""
    if modelo != Modelo.M303.value:
        if evidence_file is not None:
            raise typer.BadParameter(tr("cli.app.quickfile.errors.m303_evidence_forbidden"))
        return None
    if evidence_file is None:
        raise typer.BadParameter(tr("cli.app.quickfile.errors.m303_filing_evidence_required"))
    try:
        raw = evidence_file.read_text(encoding=UTF_8_ENCODING)
        evidence = FilingInstanceEvidence.model_validate_json(raw)
    except (OSError, ValidationError) as exc:
        raise typer.BadParameter(
            tr("cli.app.quickfile.errors.m303_filing_evidence_invalid", path=str(evidence_file)),
        ) from exc
    if evidence.m303.period != period:
        raise typer.BadParameter(tr("cli.app.quickfile.errors.m303_filing_evidence_period_mismatch"))
    return evidence


__all__ = ["m303_filing_instance_evidence_from_cli"]
