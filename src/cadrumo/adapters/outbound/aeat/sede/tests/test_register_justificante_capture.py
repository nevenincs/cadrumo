"""Receipt-only register capture remains bound to the selected filing row."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from ......application.live.expedientes_ports import ExpedientesDeclaration
from ......core.period import Period
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ......domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...playwright import BrowserContext, Page
from .. import declarations as module
from ..errors import SedeNavigationError
from .declarations_register_test_support import offline_aeat_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_YEAR = filing_year_envelope().horizon


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["none", "missing", "quarter", "receipt"])
async def test_receipt_capture_rechecks_exact_register_row(monkeypatch: pytest.MonkeyPatch, change: str) -> None:
    selected = ExpedientesDeclaration(
        modelo="303",
        ejercicio=_YEAR,
        period=Period.from_year_and_code(_YEAR, "1T"),
        expediente_id="202430300010001A",
        estado="ALTA",
        presented_at=datetime(_YEAR, 4, 20, tzinfo=UTC),
        justificante_link_text="Ver",
        justificante_cell_index=9,
    )
    current = selected
    if change == "quarter":
        current = selected.model_copy(update={"period": Period.from_year_and_code(_YEAR, "2T")})
    elif change == "receipt":
        current = selected.model_copy(update={"justificante_link_text": None})
    calls: list[dict[str, object]] = []

    async def content() -> str:
        return "register"

    async def search(*args: object, **kwargs: object) -> bool:
        return True

    async def download(**kwargs: object) -> tuple[str, bytes]:
        calls.append(kwargs)
        return "artefact", b"receipt"

    page = SimpleNamespace(content=content)
    monkeypatch.setattr(module, "registry_snapshot_for_declaration", lambda *args, **kwargs: object())
    monkeypatch.setattr(module, "read_guard_policy_from_snapshot", lambda snapshot: module.READ_GUARD_POLICY)
    monkeypatch.setattr(module, "drive_search", search)
    monkeypatch.setattr(
        module, "register_rows_from_snapshot", lambda *args, **kwargs: () if change == "missing" else (current,)
    )
    monkeypatch.setattr(module, "row_locator_for_expediente", lambda *args, **kwargs: "exact-row")
    monkeypatch.setattr(module, "capture_row_pdf_artefact", download)
    register = module.DeclaracionesRegisterSession(
        offline_aeat_session(),
        cast(Page, page),
        cast(BrowserContext, object()),
        operation=cast(PinnedAuthorityOperation, object()),
    )
    if change != "none":
        with pytest.raises(SedeNavigationError, match="selected period"):
            await register.capture_justificante(selected)
        assert calls == []
    else:
        assert await register.capture_justificante(selected) == ("artefact", b"receipt")
        assert len(calls) == 1
        assert calls[0]["declaration"] is current
        assert calls[0]["cell_index"] == 9
        assert calls[0]["kind"] == "justificante_pdf"
