"""Closed enumeration of every AEAT modelo tracked by the registry.

The :class:`ModeloCode` members name every modelo that the v1 catalogue
materialises under :mod:`aeat.domain.modelos`. The enum values are the canonical
three-character AEAT code strings (``"036"``, ``"100"``, ...), which
lets consumers interoperate transparently with string-keyed APIs such
as :data:`aeat.domain.deadlines.CALENDAR`.
"""

from __future__ import annotations

from enum import StrEnum


class ModeloCode(StrEnum):
    """Canonical AEAT modelo code.

    Each member's value is the three-character numeric code AEAT uses
    on public forms and Sede Electrónica URLs. The closed membership
    tracks the twenty-one modelos covered by the v1 inventory (see the
    modelo-inventory research document for the provenance of each
    code).
    """

    MODELO_036 = "036"
    MODELO_037 = "037"
    MODELO_100 = "100"
    MODELO_111 = "111"
    MODELO_115 = "115"
    MODELO_123 = "123"
    MODELO_130 = "130"
    MODELO_131 = "131"
    MODELO_180 = "180"
    MODELO_190 = "190"
    MODELO_193 = "193"
    MODELO_200 = "200"
    MODELO_202 = "202"
    MODELO_232 = "232"
    MODELO_303 = "303"
    MODELO_347 = "347"
    MODELO_349 = "349"
    MODELO_369 = "369"
    MODELO_390 = "390"
    MODELO_720 = "720"
    MODELO_840 = "840"
