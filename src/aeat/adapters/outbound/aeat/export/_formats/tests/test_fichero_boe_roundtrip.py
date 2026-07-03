"""Modelo 130 golden-SHA fichero-BOE round-trip test."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path

import pytest

from .......core import Period
from ._fichero_boe_roundtrip_support import (
    _M130_AGRARIAN_VOLUME_CASILLA,
    _M130_AGRARIAN_WITHHELD_CASILLA,
    _M130_GASTOS_CASILLA,
    _M130_HOME_DEDUCTION_CASILLA,
    _M130_INGRESOS_CASILLA,
    _M130_PAGOS_FRACCIONADOS_CASILLA,
    _M130_PRIOR_RETURN_CASILLA,
    _M130_RETENCIONES_CASILLA,
    _money_bytes,
    _schema_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

# Source authority: AEAT Diseño de Registros DR 13001, Orden HAP/258/2015,
# version 1.2, updated March 2019 ("ejercicios 2019 y siguientes").
_M130_GOLDEN_SHA256 = "feaffb81b89ce8b897066ac0383d31e4bfd45a15c526b650f711a89f25fe0120"
_PAGE_START = 328


def test_modelo_130_golden_sha_fichero_boe(tmp_path: Path) -> None:
    """Modelo 130 serialises to a byte-exact 946-byte fichero-BOE."""
    from .......application.filing import (
        ModeloDraftStatus,
        ModeloOperatorProfile,
        build_draft,
        export_draft,
    )

    provider = _schema_provider("130")
    draft = build_draft(
        modelo="130",
        period=Period.from_year_and_code(2026, "1T"),
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Golden test",
        ),
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("10000.00"),
            _M130_GASTOS_CASILLA: Decimal("4000.00"),
            _M130_PAGOS_FRACCIONADOS_CASILLA: Decimal("0"),
            _M130_RETENCIONES_CASILLA: Decimal("0"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-pagos-fraccionados-anteriores": Decimal("0"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
        },
        schema_provider=provider,
    )
    draft = draft.model_copy(update={"status": ModeloDraftStatus.APROBADO})

    output = tmp_path / "modelo-130.txt"
    receipt = export_draft(
        draft,
        output_path=output,
        headers={
            "declaration_type": "I",
            "surnames": "GARCIA LOPEZ",
            "name": "JUAN",
            "program_version": "A001",
            "presenter_nif": "12345678Z",
        },
        schema_provider=provider,
    )
    payload = output.read_bytes()

    def _page(offset: int, length: int) -> bytes:
        s = _PAGE_START + offset - 1
        return payload[s : s + length]

    assert len(payload) == 946, f"expected 946-byte fichero-BOE; got {len(payload)}"
    assert _page(1, 2) == b"<T"
    assert _page(3, 3) == b"130"
    assert _page(6, 2) == b"01"
    assert _page(8, 4) == b"000>"

    assert _page(12, 1) == b" ", "complementaria indicator must be blank for ordinary declaration"
    assert _page(13, 1) == b"I"
    assert _page(14, 9) == b"12345678Z"
    assert _page(23, 12) == b"GARCIA LOPEZ"
    assert _page(83, 4) == b"JUAN"
    assert _page(103, 4) == b"2026"
    assert _page(107, 2) == b"1T"

    assert _page(109, 17) == _money_bytes(Decimal("10000.00"), signed=False)
    assert _page(126, 17) == _money_bytes(Decimal("4000.00"), signed=False)
    assert _page(143, 17) == _money_bytes(Decimal("6000.00"), signed=True)
    assert _page(160, 17) == _money_bytes(Decimal("1200.00"), signed=False)
    assert _page(415, 17) == _money_bytes(Decimal("1200.00"), signed=True)

    assert _page(432, 1) == b" ", "declaracion-complementaria must be blank for ordinary declaration"
    assert _page(433, 13) == b" " * 13, "previous receipt must be blank for first declaration"
    assert _page(589, 12) == b"</T13001000>"
    assert payload[-18:] == b"</T130020261T0000>"

    digest = hashlib.sha256(payload).hexdigest()
    assert digest == _M130_GOLDEN_SHA256, (
        f"Modelo 130 fichero-BOE SHA mismatch.\n"
        f"  Expected: {_M130_GOLDEN_SHA256}\n"
        f"  Got:      {digest}\n"
        "Any change to the Modelo 130 export layout that alters byte output must be re-grounded against DR 13001."
    )
    assert receipt.byte_size == 946
    assert receipt.file_sha256 == _M130_GOLDEN_SHA256
