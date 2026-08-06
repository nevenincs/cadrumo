"""Inbound adapter for the Certificado de Situación Censal (G313) artefact.

Public facade: :func:`parse_certificado_censal_bytes`. See the parser
module docstring for the structure-only / unpinned-extraction posture.
"""

from __future__ import annotations

from ._parser import parse_certificado_censal_bytes

__all__ = ["parse_certificado_censal_bytes"]
