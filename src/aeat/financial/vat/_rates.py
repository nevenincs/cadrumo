"""Hand-curated 2025 VAT rate table for the 27 EU member states.

The numeric rates were codified from the European Commission's
"VAT rates applied in the Member States of the European Union"
reference (retrieval_date = 2026-04-13). Spain and Germany are fully
expanded with every tier the TDP classifier needs; France, Italy
and the Netherlands are expanded with the two common tiers; every
other member state is covered with at least the ``GENERAL`` tier so
``lookup_rate`` can round-trip every :class:`EUMemberState` member.

The individual :class:`VATRate` records are frozen pydantic models;
the aggregate :data:`VAT_RATE_TABLE` is an immutable mapping so the
substrate cannot be mutated in place after import.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from types import MappingProxyType

from ._schema import EUMemberState, VATRate, VATRateKind

_EFFECTIVE_FROM = date(2025, 1, 1)


def _rate(
    member_state: EUMemberState,
    kind: VATRateKind,
    pct: str,
    reference: str,
) -> VATRate:
    """Shorthand builder for a 2025 open-ended :class:`VATRate`."""
    return VATRate(
        member_state=member_state,
        kind=kind,
        pct=Decimal(pct),
        effective_from=_EFFECTIVE_FROM,
        effective_until=None,
        boe_or_directive_reference=reference,
    )


_LEY_37 = "Ley 37/1992 Art. 90/91 (BOE-A-1992-28740)"
_DIR_2006_112 = "Directive 2006/112/EC (Council VAT Directive)"


_ES_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.ES, VATRateKind.GENERAL, "21", "Ley 37/1992 Art. 90.Uno"),
    _rate(EUMemberState.ES, VATRateKind.REDUCED, "10", "Ley 37/1992 Art. 91.Uno"),
    _rate(EUMemberState.ES, VATRateKind.SUPER_REDUCED, "4", "Ley 37/1992 Art. 91.Dos"),
    _rate(EUMemberState.ES, VATRateKind.ZERO, "0", "Ley 37/1992 Art. 24/25 (exenciones plenas)"),
)

_DE_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.DE, VATRateKind.GENERAL, "19", f"{_DIR_2006_112}; UStG §12(1)"),
    _rate(EUMemberState.DE, VATRateKind.REDUCED, "7", f"{_DIR_2006_112}; UStG §12(2)"),
    _rate(EUMemberState.DE, VATRateKind.ZERO, "0", f"{_DIR_2006_112} Art. 138"),
)

_FR_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.FR, VATRateKind.GENERAL, "20", f"{_DIR_2006_112}; CGI Art. 278"),
    _rate(EUMemberState.FR, VATRateKind.REDUCED, "10", f"{_DIR_2006_112}; CGI Art. 278 bis"),
    _rate(EUMemberState.FR, VATRateKind.SUPER_REDUCED, "5.5", f"{_DIR_2006_112}; CGI Art. 278-0 bis"),
    _rate(EUMemberState.FR, VATRateKind.ZERO, "0", f"{_DIR_2006_112} Art. 138"),
)

_IT_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.IT, VATRateKind.GENERAL, "22", f"{_DIR_2006_112}; DPR 633/1972"),
    _rate(EUMemberState.IT, VATRateKind.REDUCED, "10", f"{_DIR_2006_112}; DPR 633/1972"),
    _rate(EUMemberState.IT, VATRateKind.SUPER_REDUCED, "4", f"{_DIR_2006_112}; DPR 633/1972"),
    _rate(EUMemberState.IT, VATRateKind.ZERO, "0", f"{_DIR_2006_112} Art. 138"),
)

_NL_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.NL, VATRateKind.GENERAL, "21", f"{_DIR_2006_112}; Wet OB 1968 Art. 9"),
    _rate(EUMemberState.NL, VATRateKind.REDUCED, "9", f"{_DIR_2006_112}; Wet OB 1968 Art. 9"),
    _rate(EUMemberState.NL, VATRateKind.ZERO, "0", f"{_DIR_2006_112} Art. 138"),
)

_BE_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.BE, VATRateKind.GENERAL, "21", f"{_DIR_2006_112}; Code TVA"),
    _rate(EUMemberState.BE, VATRateKind.REDUCED, "12", f"{_DIR_2006_112}; Code TVA"),
    _rate(EUMemberState.BE, VATRateKind.SUPER_REDUCED, "6", f"{_DIR_2006_112}; Code TVA"),
)

_AT_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.AT, VATRateKind.GENERAL, "20", f"{_DIR_2006_112}; UStG 1994 §10"),
    _rate(EUMemberState.AT, VATRateKind.REDUCED, "10", f"{_DIR_2006_112}; UStG 1994 §10"),
)

_PT_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.PT, VATRateKind.GENERAL, "23", f"{_DIR_2006_112}; CIVA"),
    _rate(EUMemberState.PT, VATRateKind.REDUCED, "13", f"{_DIR_2006_112}; CIVA"),
    _rate(EUMemberState.PT, VATRateKind.SUPER_REDUCED, "6", f"{_DIR_2006_112}; CIVA"),
)

_IE_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.IE, VATRateKind.GENERAL, "23", f"{_DIR_2006_112}; VATCA 2010"),
    _rate(EUMemberState.IE, VATRateKind.REDUCED, "13.5", f"{_DIR_2006_112}; VATCA 2010"),
)

_PL_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.PL, VATRateKind.GENERAL, "23", f"{_DIR_2006_112}; Ustawa VAT"),
    _rate(EUMemberState.PL, VATRateKind.REDUCED, "8", f"{_DIR_2006_112}; Ustawa VAT"),
)

_SE_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.SE, VATRateKind.GENERAL, "25", f"{_DIR_2006_112}; Mervärdesskattelag"),
    _rate(EUMemberState.SE, VATRateKind.REDUCED, "12", f"{_DIR_2006_112}; Mervärdesskattelag"),
)

_DK_RATES: tuple[VATRate, ...] = (_rate(EUMemberState.DK, VATRateKind.GENERAL, "25", f"{_DIR_2006_112}; Momsloven"),)

_FI_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.FI, VATRateKind.GENERAL, "25.5", f"{_DIR_2006_112}; Arvonlisäverolaki"),
    _rate(EUMemberState.FI, VATRateKind.REDUCED, "14", f"{_DIR_2006_112}; Arvonlisäverolaki"),
)

_HU_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.HU, VATRateKind.GENERAL, "27", f"{_DIR_2006_112}; ÁFA törvény"),
    _rate(EUMemberState.HU, VATRateKind.REDUCED, "18", f"{_DIR_2006_112}; ÁFA törvény"),
    _rate(EUMemberState.HU, VATRateKind.SUPER_REDUCED, "5", f"{_DIR_2006_112}; ÁFA törvény"),
)

_GR_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.GR, VATRateKind.GENERAL, "24", f"{_DIR_2006_112}; N. 2859/2000"),
    _rate(EUMemberState.GR, VATRateKind.REDUCED, "13", f"{_DIR_2006_112}; N. 2859/2000"),
)

_CZ_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.CZ, VATRateKind.GENERAL, "21", f"{_DIR_2006_112}; Zákon o DPH"),
    _rate(EUMemberState.CZ, VATRateKind.REDUCED, "12", f"{_DIR_2006_112}; Zákon o DPH"),
)

_SK_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.SK, VATRateKind.GENERAL, "23", f"{_DIR_2006_112}; Zákon o DPH SK"),
    _rate(EUMemberState.SK, VATRateKind.REDUCED, "5", f"{_DIR_2006_112}; Zákon o DPH SK"),
)

_LU_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.LU, VATRateKind.GENERAL, "17", f"{_DIR_2006_112}; Loi TVA LU"),
    _rate(EUMemberState.LU, VATRateKind.REDUCED, "8", f"{_DIR_2006_112}; Loi TVA LU"),
)

_BG_RATES: tuple[VATRate, ...] = (_rate(EUMemberState.BG, VATRateKind.GENERAL, "20", f"{_DIR_2006_112}; ЗДДС"),)

_HR_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.HR, VATRateKind.GENERAL, "25", f"{_DIR_2006_112}; Zakon o PDV-u"),
    _rate(EUMemberState.HR, VATRateKind.REDUCED, "13", f"{_DIR_2006_112}; Zakon o PDV-u"),
)

_CY_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.CY, VATRateKind.GENERAL, "19", f"{_DIR_2006_112}; Cyprus VAT Law"),
    _rate(EUMemberState.CY, VATRateKind.REDUCED, "9", f"{_DIR_2006_112}; Cyprus VAT Law"),
)

_EE_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.EE, VATRateKind.GENERAL, "22", f"{_DIR_2006_112}; Käibemaksuseadus"),
)

_LV_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.LV, VATRateKind.GENERAL, "21", f"{_DIR_2006_112}; PVN likums"),
    _rate(EUMemberState.LV, VATRateKind.REDUCED, "12", f"{_DIR_2006_112}; PVN likums"),
)

_LT_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.LT, VATRateKind.GENERAL, "21", f"{_DIR_2006_112}; PVM įstatymas"),
    _rate(EUMemberState.LT, VATRateKind.REDUCED, "9", f"{_DIR_2006_112}; PVM įstatymas"),
)

_MT_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.MT, VATRateKind.GENERAL, "18", f"{_DIR_2006_112}; VAT Act Malta"),
    _rate(EUMemberState.MT, VATRateKind.REDUCED, "7", f"{_DIR_2006_112}; VAT Act Malta"),
)

_RO_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.RO, VATRateKind.GENERAL, "19", f"{_DIR_2006_112}; Codul Fiscal RO"),
    _rate(EUMemberState.RO, VATRateKind.REDUCED, "9", f"{_DIR_2006_112}; Codul Fiscal RO"),
)

_SI_RATES: tuple[VATRate, ...] = (
    _rate(EUMemberState.SI, VATRateKind.GENERAL, "22", f"{_DIR_2006_112}; ZDDV-1"),
    _rate(EUMemberState.SI, VATRateKind.REDUCED, "9.5", f"{_DIR_2006_112}; ZDDV-1"),
)


_MUTABLE_TABLE: dict[EUMemberState, tuple[VATRate, ...]] = {
    EUMemberState.AT: _AT_RATES,
    EUMemberState.BE: _BE_RATES,
    EUMemberState.BG: _BG_RATES,
    EUMemberState.CY: _CY_RATES,
    EUMemberState.CZ: _CZ_RATES,
    EUMemberState.DE: _DE_RATES,
    EUMemberState.DK: _DK_RATES,
    EUMemberState.EE: _EE_RATES,
    EUMemberState.ES: _ES_RATES,
    EUMemberState.FI: _FI_RATES,
    EUMemberState.FR: _FR_RATES,
    EUMemberState.GR: _GR_RATES,
    EUMemberState.HR: _HR_RATES,
    EUMemberState.HU: _HU_RATES,
    EUMemberState.IE: _IE_RATES,
    EUMemberState.IT: _IT_RATES,
    EUMemberState.LT: _LT_RATES,
    EUMemberState.LU: _LU_RATES,
    EUMemberState.LV: _LV_RATES,
    EUMemberState.MT: _MT_RATES,
    EUMemberState.NL: _NL_RATES,
    EUMemberState.PL: _PL_RATES,
    EUMemberState.PT: _PT_RATES,
    EUMemberState.RO: _RO_RATES,
    EUMemberState.SE: _SE_RATES,
    EUMemberState.SI: _SI_RATES,
    EUMemberState.SK: _SK_RATES,
}

VAT_RATE_TABLE: Mapping[EUMemberState, tuple[VATRate, ...]] = MappingProxyType(_MUTABLE_TABLE)
"""Immutable view over the hand-curated 2025 EU VAT rate table.

The mapping covers all 27 EU member states and carries at least 50
:class:`VATRate` entries in total. See the module docstring for the
authoritative source.
"""


def total_rate_count() -> int:
    """Return the total number of :class:`VATRate` records in the table."""
    return sum(len(rates) for rates in VAT_RATE_TABLE.values())


__all__ = ["VAT_RATE_TABLE", "total_rate_count"]
