"""Closed enumeration of every AEAT modelo tracked by the registry.

The :class:`ModeloCode` members name every modelo materialised by the
catalogue under :mod:`aeat.domain.modelos`. Each enum value is the
canonical three-character AEAT code string (``"036"``, ``"100"``, ...),
which lets consumers interoperate transparently with string-keyed
APIs such as :data:`aeat.domain.deadlines.CALENDAR`.
"""

from __future__ import annotations

from enum import StrEnum


class ModeloCode(StrEnum):
    """Canonical AEAT modelo code.

    Each member's value is the three-character numeric code AEAT uses
    on public forms and Sede Electrónica URLs. The closed membership
    tracks the modelos covered by the inventory.

    Attributes:
        MODELO_036: Full census declaration (*Declaración censal completa*).
        MODELO_037: Simplified census declaration (*Declaración censal
            simplificada*; retired 2025-02-03).
        MODELO_100: Annual personal income-tax (IRPF) return.
        MODELO_111: IRPF withholding — employment and economic activities.
        MODELO_115: Withholding — urban rental payments.
        MODELO_123: Withholding — investment income (interest, dividends).
        MODELO_130: Quarterly IRPF instalment — direct-estimation regime.
        MODELO_131: Quarterly IRPF instalment — objective-estimation regime.
        MODELO_180: Annual summary of urban-rental withholdings.
        MODELO_190: Annual summary of employment and activity withholdings.
        MODELO_193: Annual summary of investment-income withholdings.
        MODELO_200: Annual corporate-tax (Impuesto sobre Sociedades) return.
        MODELO_202: Quarterly corporate-tax instalment.
        MODELO_232: Related-party and tax-haven operations declaration.
        MODELO_303: Periodic VAT (IVA) self-assessment.
        MODELO_347: Annual declaration of third-party operations.
        MODELO_349: Recapitulative declaration of intra-EU operations.
        MODELO_369: VAT self-assessment for the OSS / IOSS regime.
        MODELO_390: Annual VAT summary return.
        MODELO_720: Informative declaration of foreign assets and rights.
        MODELO_840: Economic Activities Tax (IAE) declaration.
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
