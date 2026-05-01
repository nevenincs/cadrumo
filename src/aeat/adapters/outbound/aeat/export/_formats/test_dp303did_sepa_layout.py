"""DP303DID SEPA devolución page layout lock (wave 144).

The DP303DID page carries Kent's refund-routing block: SWIFT/BIC,
IBAN, bank name + address, country code, and the SEPA marker.
When Kent files a devolución (tipo=D), his ``--iban`` and
``--swift`` flag values land here. Every byte offset in the
wave-101 devolución export test and the wave-138 IBAN
normalisation E2E test depends on these offsets being stable.

Wave 144 mirrors wave-143's DP30301 lock for this Kent-critical
SEPA page. A fixture regeneration that shifts SWIFT or IBAN by
even one byte ships a malformed SEPA block to AEAT — the refund
would land in a wrong account or silently drop. This test fails
loud first with a targeted message naming the offending field.
"""

from __future__ import annotations

import pytest

from ._record_spec import SegmentSpec
from .modelo_303_2024 import ENVELOPE

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


def _dp303did() -> SegmentSpec:
    for seg in ENVELOPE:
        if seg.segment_id == "DP303DID":
            return seg
    raise AssertionError("DP303DID segment missing from envelope")


#: Canonical SEPA-field layout per the DR303e24 DP303DID page.
#: (field_id, 1-based offset within DP303DID, length, kind).
_EXPECTED_DP303DID_LAYOUT: list[tuple[str, int, int, str]] = [
    ("DP303DID_F001_INICIO_DEL_IDENTIFICADOR_DE", 1, 2, "RESERVED"),
    ("DP303DID_F002_MODELO", 3, 3, "RESERVED"),
    ("DP303DID_F003_P_GINA", 6, 5, "RESERVED"),
    ("DP303DID_F004_FIN_DE_IDENTIFICADOR_DE_MODE", 11, 1, "RESERVED"),
    ("DP303DID_F005_DEVOLUCI_N_SWIFT_BIC", 12, 11, "ALPHANUMERIC"),
    ("DP303DID_F006_DOMICILIACI_N_DEVOLUCI_N_IBA", 23, 34, "ALPHANUMERIC"),
    ("DP303DID_F007_DEVOLUCI_N_BANCO_BANK_NAME", 57, 70, "ALPHANUMERIC"),
    ("DP303DID_F008_DEVOLUCI_N_DIRECCI_N_DEL_BAN", 127, 35, "ALPHANUMERIC"),
    ("DP303DID_F009_DEVOLUCI_N_CIUDAD_CITY", 162, 30, "ALPHANUMERIC"),
    ("DP303DID_F010_DEVOLUCI_N_C_DIGO_PA_S_COUNT", 192, 2, "ALPHANUMERIC"),
    ("DP303DID_F011_DEVOLUCI_N_MARCA_SEPA", 194, 1, "NUMERIC"),
]


class TestDp303didSepaLayout:
    def test_layout_matches_canonical(self) -> None:
        segment = _dp303did()
        by_field_id = {s.field_id: s for s in segment.specs}
        for expected_field, expected_offset, expected_length, expected_kind in _EXPECTED_DP303DID_LAYOUT:
            assert expected_field in by_field_id, (
                f"DP303DID missing {expected_field!r}. SEPA page regression — Kent's "
                f"refund routing may land in the wrong AEAT slot."
            )
            spec = by_field_id[expected_field]
            assert spec.offset == expected_offset, (
                f"DP303DID field {expected_field!r} at offset {spec.offset}; expected "
                f"{expected_offset}. Upstream field shift detected."
            )
            assert spec.length == expected_length, (
                f"DP303DID field {expected_field!r} length {spec.length}; expected {expected_length}."
            )
            assert spec.kind.name == expected_kind, (
                f"DP303DID field {expected_field!r} kind {spec.kind.name}; expected {expected_kind}."
            )

    def test_swift_slot_is_11_bytes_at_offset_12(self) -> None:
        """SWIFT/BIC (ISO-9362) is 8 or 11 chars; the slot is sized for the
        longer 11-char form. Starts immediately after the 11-byte identifier
        header ``<T303DID00>``."""
        segment = _dp303did()
        by_field_id = {s.field_id: s for s in segment.specs}
        swift = by_field_id["DP303DID_F005_DEVOLUCI_N_SWIFT_BIC"]
        assert swift.offset == 12
        assert swift.length == 11

    def test_iban_slot_is_34_bytes_at_offset_23(self) -> None:
        """IBAN (ISO-13616) is up to 34 chars; the slot starts immediately
        after the 11-byte SWIFT. Wave-138's normalisation E2E test depends
        on this offset and length being stable."""
        segment = _dp303did()
        by_field_id = {s.field_id: s for s in segment.specs}
        iban = by_field_id["DP303DID_F006_DOMICILIACI_N_DEVOLUCI_N_IBA"]
        assert iban.offset == 23
        assert iban.length == 34

    def test_sepa_marker_is_1_byte_numeric_at_offset_194(self) -> None:
        """The SEPA marker is a 1-byte flag set to '1' when Kent supplies
        an IBAN (wave-101 builder logic). Its NUMERIC kind means it pads
        with '0' by default — no IBAN → no SEPA declaration."""
        segment = _dp303did()
        by_field_id = {s.field_id: s for s in segment.specs}
        marker = by_field_id["DP303DID_F011_DEVOLUCI_N_MARCA_SEPA"]
        assert marker.offset == 194
        assert marker.length == 1
        assert marker.kind.name == "NUMERIC"

    def test_dp303did_segment_starts_at_absolute_byte_7153(self) -> None:
        """Sanity: DP303DID is the 7th segment in ENVELOPE, starting at
        cumulative byte 7153 per wave-142. An absolute-offset reader (like
        the wave-101 export test) uses 7153 + intra-segment offset."""
        cumulative = 0
        for seg in ENVELOPE:
            if seg.segment_id == "DP303DID":
                assert cumulative == 7153
                return
            cumulative += seg.total_length
        pytest.fail("DP303DID not found in envelope")
