"""Canonical AEAT certificado identifier."""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

__all__ = ["AeatCertificadoId"]


AeatCertificadoId = Annotated[str, StringConstraints(min_length=10, max_length=16, pattern=r"^\d{10,16}$")]
"""AEAT's certificate number, bounded to the notification parser contract."""
