from __future__ import annotations

from pathlib import Path

import pytest

from ..validation_verdict_cache import (
    VERDICT_CACHE_DIR_ENV,
    is_validated,
    record_validated,
    validation_verdict_scope,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _rows(root: Path) -> tuple[tuple[str, int, int, str], ...]:
    return (
        (str(root / "legal" / "a.toml"), 10, 1, "legal-a"),
        (str(root / "modelos" / "303" / "manifest.toml"), 20, 2, "m303"),
        (str(root / "modelos" / "303" / "revisions" / "2024" / "revision.toml"), 30, 3, "m303-2024"),
        (str(root / "modelos" / "100.toml"), 40, 4, "m100"),
        (str(root / "modelos"), 0, 5, ""),
    )


def _scope(root: Path, rows: tuple[tuple[str, int, int, str], ...], *, compiler: str = "code"):
    return validation_verdict_scope(
        registry_root=root,
        registry_identity_digest="tree",
        fingerprints=rows,
        source_receipt="evidence",
        compiler_identity_digest=compiler,
    )


def test_scope_keys_each_modelo_by_its_own_rows_and_everything_shared(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    scope = _scope(root, _rows(root))

    assert set(scope.modelo_keys) == {"303", "100"}
    assert scope.modelo_key("999") is None

    edited_303 = tuple((p, s, m, "changed" if d == "m303-2024" else d) for p, s, m, d in _rows(root))
    edited = _scope(root, edited_303)
    assert edited.modelo_key("303") != scope.modelo_key("303")
    assert edited.modelo_key("100") == scope.modelo_key("100")

    edited_legal = tuple((p, s, m, "changed" if d == "legal-a" else d) for p, s, m, d in _rows(root))
    shared = _scope(root, edited_legal)
    assert shared.modelo_key("303") != scope.modelo_key("303")
    assert shared.modelo_key("100") != scope.modelo_key("100")

    recompiled = _scope(root, _rows(root), compiler="other-code")
    assert recompiled.registry_key != scope.registry_key
    assert recompiled.modelo_key("303") != scope.modelo_key("303")


def test_only_a_recorded_clean_verdict_is_served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VERDICT_CACHE_DIR_ENV, str(tmp_path / "verdicts"))
    assert not is_validated("abc")

    record_validated("abc", subject="registry")
    assert is_validated("abc")
    assert not is_validated("abd")

    (tmp_path / "verdicts" / "verdict_abc.json").write_text("not json", encoding="utf-8")
    assert not is_validated("abc")
