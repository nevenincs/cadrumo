"""Unit tests for :mod:`aeat.domain.portals._cli`."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from ._cli import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


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
    """``list --modelo 130 --json`` returns the registry-linked portal."""
    code, out = _invoke("list", "--modelo", "130", "--json")
    assert code == 0, out
    payload = _unwrap_result(out)
    related = {e["portal"] for e in payload}
    assert related == {"portal_m130_pago_fraccionado_ed"}


def test_list_active_only() -> None:
    """``list --active-only --json`` excludes the retired M037 entry."""
    code, out = _invoke("list", "--active-only", "--json")
    assert code == 0, out
    payload = _unwrap_result(out)
    portals = {e["portal"] for e in payload}
    assert "portal_m037_censal_simplificada" not in portals


def test_list_filter_flags_combined() -> None:
    """Filters compose over registry-backed modelo linkage."""
    code, out = _invoke("list", "--category", "filing", "--modelo", "130", "--json")
    assert code == 0, out
    payload = _unwrap_result(out)
    assert len(payload) == 1
    assert payload[0]["portal"] == "portal_m130_pago_fraccionado_ed"


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
    """``for-modelo 130 --json`` emits the registry-linked entry."""
    code, out = _invoke("for-modelo", "130", "--json")
    assert code == 0, out
    payload = _unwrap_result(out)
    portals = {e["portal"] for e in payload}
    assert portals == {"portal_m130_pago_fraccionado_ed"}


def test_for_modelo_without_portal_returns_empty_result() -> None:
    """A valid identifier without portal metadata returns no entries."""
    code, out = _invoke("for-modelo", "999", "--json")
    assert code == 0
    assert _unwrap_result(out) == []


def test_list_modelo_filter_without_portal_returns_empty_result() -> None:
    """``list --modelo 999`` returns no entries."""
    code, out = _invoke("list", "--modelo", "999", "--json")
    assert code == 0
    assert _unwrap_result(out) == []
