"""Receipt-only register capture remains bound to the selected filing row."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from ......core.period import Period
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ..._playwright import BrowserContext, Page
from .. import declarations as module
from ..declarations_schema import Declaracion
from ..errors import SedeNavigationError
from .declarations_register_test_support import offline_aeat_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["none", "missing", "quarter", "receipt"])
async def test_receipt_capture_rechecks_exact_register_row(monkeypatch: pytest.MonkeyPatch, change: str) -> None:
    selected = Declaracion(
        modelo="303",
        ejercicio=2024,
        period=Period.from_year_and_code(2024, "1T"),
        expediente_id="202430300010001A",
        estado="ALTA",
        presented_at=datetime(2024, 4, 20, tzinfo=UTC),
        justificante_link_text="Ver",
        justificante_cell_index=9,
    )
    current = selected
    if change == "quarter":
        current = selected.model_copy(update={"period": Period.from_year_and_code(2024, "2T")})
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
    monkeypatch.setattr(module, "_registry_snapshot_for_declaration", lambda *args, **kwargs: object())
    monkeypatch.setattr(module, "_read_guard_policy_from_snapshot", lambda snapshot: module.READ_GUARD_POLICY)
    monkeypatch.setattr(module, "_drive_search", search)
    monkeypatch.setattr(
        module, "_register_rows_from_snapshot", lambda *args, **kwargs: () if change == "missing" else (current,)
    )
    monkeypatch.setattr(module, "_row_locator_for_expediente", lambda *args, **kwargs: "exact-row")
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
