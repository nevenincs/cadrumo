"""Canonical AEAT certificado identifier."""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

__all__ = ["AEAT_CERTIFICADO_PATTERN", "AeatCertificadoId"]


AEAT_CERTIFICADO_PATTERN = r"^\d{10,16}$"
"""The observed span of the sede's notification numbers; AEAT publishes no format for them."""

AeatCertificadoId = Annotated[str, StringConstraints(min_length=10, max_length=16, pattern=AEAT_CERTIFICADO_PATTERN)]
"""AEAT's certificate number, bounded to the notification parser contract."""
