"""Contract tests for the CLI-side ``_resolve_id`` wrapper.

Pins that every ``TransactionIdPrefixError`` raised by the domain
resolver surfaces as a ``tr()``-rendered ``typer.BadParameter`` via
``_bad``, rather than leaking the raw Python exception text. Each of
the four refusal paths (empty, non-hex, not-found, collision) carries
its own locale key.
"""

from __future__ import annotations

import pytest
import typer

from ._ledger import _resolve_id

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


class _StubRepo:
    def __init__(self, ids: tuple[str, ...]) -> None:
        self._ids = ids
        self.bucket_id = "bucket-a"

    def load(self):
        from types import SimpleNamespace

        return SimpleNamespace(
            transactions={tx_id: SimpleNamespace(transaction_id=tx_id) for tx_id in self._ids},
            values=lambda: tuple(SimpleNamespace(transaction_id=tx_id) for tx_id in self._ids),
        )


def _bucket_ids_patch(monkeypatch: pytest.MonkeyPatch, ids: tuple[str, ...]) -> None:
    monkeypatch.setattr(
        "aeat.entrypoints.cli._ledger._bucket_transaction_ids",
        lambda repo: ids,
    )


def test_resolve_id_renders_empty_prefix_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    _bucket_ids_patch(monkeypatch, ("a" * 64,))
    repo = _StubRepo(("a" * 64,))
    with pytest.raises(typer.BadParameter) as info:
        _resolve_id(repo, "")
    rendered = str(info.value.message)
    assert "empty" in rendered.lower()


def test_resolve_id_renders_non_hex_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    _bucket_ids_patch(monkeypatch, ("a" * 64,))
    repo = _StubRepo(("a" * 64,))
    with pytest.raises(typer.BadParameter) as info:
        _resolve_id(repo, "zzz")
    rendered = str(info.value.message)
    assert "zzz" in rendered
    # tr-rendered message mentions the hex alphabet.
    assert "hex" in rendered.lower() or "0-9" in rendered


def test_resolve_id_renders_not_found_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    _bucket_ids_patch(monkeypatch, ("a" * 64,))
    repo = _StubRepo(("a" * 64,))
    with pytest.raises(typer.BadParameter) as info:
        _resolve_id(repo, "bcd")
    rendered = str(info.value.message)
    assert "bcd" in rendered


def test_resolve_id_renders_collision_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    ids = ("ab" + "0" * 62, "ab" + "1" * 62)
    _bucket_ids_patch(monkeypatch, ids)
    repo = _StubRepo(ids)
    with pytest.raises(typer.BadParameter) as info:
        _resolve_id(repo, "ab")
    rendered = str(info.value.message)
    assert "ab" in rendered
    # Both candidate ids must be present so the operator can lengthen
    # the prefix.
    assert ids[0] in rendered
    assert ids[1] in rendered


def test_resolve_id_passes_through_full_match(monkeypatch: pytest.MonkeyPatch) -> None:
    target = "a" * 64
    _bucket_ids_patch(monkeypatch, (target,))
    repo = _StubRepo((target,))
    assert _resolve_id(repo, target) == target


def test_resolve_id_passes_through_unique_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    target = "abcdef" + "0" * 58
    _bucket_ids_patch(monkeypatch, (target,))
    repo = _StubRepo((target,))
    assert _resolve_id(repo, "abc") == target
