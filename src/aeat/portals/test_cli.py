"""Unit tests for :mod:`aeat.portals._cli`."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from ._cli import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


_runner = CliRunner()


def _unwrap_result(output: str):
    return json.loads(output)["result"]


def _invoke(*args: str) -> tuple[int, str]:
    result = _runner.invoke(app, list(args))
    return result.exit_code, result.stdout


def test_list_json_emits_all_entries() -> None:
    """``list --json`` emits 42 entries."""
    code, out = _invoke("list", "--json")
    assert code == 0, out
    payload = _unwrap_result(out)
    assert len(payload) == 42


def test_list_filter_by_category() -> None:
    """``list --category auth --json`` emits only AUTH portals."""
    code, out = _invoke("list", "--category", "auth", "--json")
    assert code == 0, out
    payload = _unwrap_result(out)
    assert len(payload) == 8
    assert all(e["category"] == "auth" for e in payload)


def test_list_filter_by_modelo() -> None:
    """``list --modelo 303 --json`` returns FILING + BORRADOR for 303."""
    code, out = _invoke("list", "--modelo", "303", "--json")
    assert code == 0, out
    payload = _unwrap_result(out)
    related = {e["portal"] for e in payload}
    assert "portal_m303_iva_autoliquidacion" in related
    assert "portal_pre303_ayuda" in related


def test_list_active_only() -> None:
    """``list --active-only --json`` excludes the retired M037 entry."""
    code, out = _invoke("list", "--active-only", "--json")
    assert code == 0, out
    payload = _unwrap_result(out)
    portals = {e["portal"] for e in payload}
    assert "portal_m037_censal_simplificada" not in portals


def test_list_filter_flags_combined() -> None:
    """Filters compose: ``--category filing --modelo 303`` is the presentation portal."""
    code, out = _invoke("list", "--category", "filing", "--modelo", "303", "--json")
    assert code == 0, out
    payload = _unwrap_result(out)
    assert len(payload) == 1
    assert payload[0]["portal"] == "portal_m303_iva_autoliquidacion"


def test_list_is_deterministic_and_sorted() -> None:
    """Output is sorted by portal value and deterministic across two calls."""
    _, out1 = _invoke("list", "--json")
    _, out2 = _invoke("list", "--json")
    assert out1 == out2
    payload = _unwrap_result(out1)
    values = [e["portal"] for e in payload]
    assert values == sorted(values)


def test_show_existing_portal_json() -> None:
    """``show --json`` emits the single entry."""
    code, out = _invoke("show", "portal_sede_root", "--json")
    assert code == 0, out
    payload = _unwrap_result(out)
    assert payload["portal"] == "portal_sede_root"


def test_show_unknown_portal_errors() -> None:
    """Unknown portal raises a BadParameter (non-zero exit)."""
    code, _ = _invoke("show", "portal_does_not_exist", "--json")
    assert code != 0


def test_for_modelo_json() -> None:
    """``for-modelo 303 --json`` emits the known two entries."""
    code, out = _invoke("for-modelo", "303", "--json")
    assert code == 0, out
    payload = _unwrap_result(out)
    portals = {e["portal"] for e in payload}
    assert portals == {"portal_m303_iva_autoliquidacion", "portal_pre303_ayuda"}


def test_for_modelo_unknown_code_errors() -> None:
    """Unknown modelo code causes non-zero exit."""
    code, _ = _invoke("for-modelo", "999", "--json")
    assert code != 0


def test_list_unknown_modelo_filter_errors() -> None:
    """``list --modelo 999`` is rejected."""
    code, _ = _invoke("list", "--modelo", "999", "--json")
    assert code != 0
