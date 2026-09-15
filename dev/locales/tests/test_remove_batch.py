"""The batch removal verb, and the silent no-op it exists to refuse.

Deleting N locale keys through the single-key ``remove`` verb costs N
interpreter starts. That is the reason this verb exists, but it is not the
reason it is shaped the way it is.

``LocaleManager.remove_locale_values`` silently ignores a key it cannot find in
a sharded catalogue -- the shipped shape. So a manifest with a typo, a stale
list, or one that has already been applied reports success having done nothing,
which is the failure mode that makes a caller believe work happened. The verb
refuses an absent key by default and names it; ``--ignore-missing`` is the
explicit opt-in for a re-run, and it still says what it skipped.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ..cli import app
from ..manager import LocaleManager, LocaleNode

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_KEY = "modelo.schema.200.revision.2024.casilla.zztestprobe.help"
_ABSENT = "modelo.schema.200.revision.2024.casilla.zznotthere.help"
_CATALOGUE = Path("src/cadrumo/locales/es/modelo/schema/200.yml")


def _casillas() -> dict[str, LocaleNode]:
    cursor: LocaleNode = LocaleManager(Path("src"), Path("src/cadrumo/locales")).load_locale(_CATALOGUE)
    for part in ("modelo", "schema", "200", "revision", "2024", "casilla"):
        if not isinstance(cursor, dict):
            raise AssertionError(f"catalogue path ended before {part!r}")
        cursor = cursor[part]
    if not isinstance(cursor, dict):
        raise AssertionError("catalogue casilla node is not a mapping")
    return cursor


@pytest.fixture
def probe(tmp_path: Path) -> Iterator[Path]:
    """Write one throwaway leaf, and remove it again however the test ends."""
    runner = CliRunner()
    manifest = tmp_path / "set.json"
    manifest.write_text(json.dumps({"es": {_KEY: None}}), encoding="utf-8")
    assert runner.invoke(app, ["set-batch", str(manifest)]).exit_code == 0
    assert "zztestprobe" in _casillas()
    yield tmp_path
    if "zztestprobe" in _casillas():
        cleanup = tmp_path / "cleanup.json"
        cleanup.write_text(json.dumps({"es": [_KEY]}), encoding="utf-8")
        runner.invoke(app, ["remove-batch", str(cleanup)])


def test_a_present_key_is_removed(probe: Path) -> None:
    """The ordinary path: one pass, one process, the leaf gone."""
    manifest = probe / "remove.json"
    manifest.write_text(json.dumps({"es": [_KEY]}), encoding="utf-8")

    result = CliRunner().invoke(app, ["remove-batch", str(manifest)])

    assert result.exit_code == 0, result.output
    assert "zztestprobe" not in _casillas()


def test_an_absent_key_refuses_and_removes_nothing(probe: Path) -> None:
    """A key that is not there must not read as a successful deletion.

    The present key in the same manifest stays PUT: refusing after deleting
    half the batch would leave the caller worse off than refusing outright,
    and they would have to diff the catalogue to find out which half.
    """
    manifest = probe / "mixed.json"
    manifest.write_text(json.dumps({"es": [_KEY, _ABSENT]}), encoding="utf-8")

    result = CliRunner().invoke(app, ["remove-batch", str(manifest)])

    assert result.exit_code != 0
    assert "zznotthere" in result.output
    assert "zztestprobe" in _casillas(), "a refused batch must not have deleted anything"


def test_ignore_missing_applies_the_rest_and_names_what_it_skipped(probe: Path) -> None:
    """Re-running a manifest is legitimate; pretending it was complete is not."""
    manifest = probe / "mixed.json"
    manifest.write_text(json.dumps({"es": [_KEY, _ABSENT]}), encoding="utf-8")

    result = CliRunner().invoke(app, ["remove-batch", str(manifest), "--ignore-missing"])

    assert result.exit_code == 0, result.output
    assert "skipped 1" in result.output
    assert "zztestprobe" not in _casillas()
