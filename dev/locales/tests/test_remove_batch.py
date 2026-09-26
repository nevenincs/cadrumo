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

Every verb here runs against a synthetic sharded catalogue in ``tmp_path``. A
probe leaf written into the shipped catalogue is visible to every catalogue
gate running beside it, and a teardown that fails leaves it there.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.entrypoints.cli.tests.cli_runner import invoke_typer_app

from .._paths import LOCALES_DIR
from ..cli import app
from ..manager import LocaleManager, LocaleNode

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_KEY = "modelo.schema.999.revision.2024.casilla.zztestprobe.help"
_ABSENT = "modelo.schema.999.revision.2024.casilla.zznotthere.help"
_SHARD = Path("es") / "modelo" / "schema" / "999.yml"


def _manager(root: Path) -> LocaleManager:
    return LocaleManager(root / "src", root / "locales")


def _casillas(root: Path) -> dict[str, LocaleNode]:
    cursor: LocaleNode = _manager(root).load_locale(root / "locales" / _SHARD)
    for part in ("modelo", "schema", "999", "revision", "2024", "casilla"):
        if not isinstance(cursor, dict):
            raise AssertionError(f"catalogue path ended before {part!r}")
        cursor = cursor[part]
    if not isinstance(cursor, dict):
        raise AssertionError("catalogue casilla node is not a mapping")
    return cursor


def _run(root: Path, *args: str) -> Result:
    return invoke_typer_app(app, list(args), obj=_manager(root))


@pytest.fixture
def probe(tmp_path: Path) -> Path:
    """A sharded catalogue holding one real leaf and the throwaway probe leaf."""
    (tmp_path / "src").mkdir()
    shard = tmp_path / "locales" / _SHARD
    shard.parent.mkdir(parents=True)
    shard.write_text(
        "modelo:\n  schema:\n    '999':\n      revision:\n        '2024':\n"
        "          casilla:\n            '01':\n              label: 'Base imponible'\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "set.json"
    manifest.write_text(json.dumps({"es": {_KEY: None}}), encoding="utf-8")
    assert _run(tmp_path, "set-batch", str(manifest)).exit_code == 0
    assert "zztestprobe" in _casillas(tmp_path)
    return tmp_path


def test_the_batch_verbs_write_the_catalogue_they_are_given(probe: Path) -> None:
    """The probe lands in the injected catalogue and the shipped tree never holds its modelo."""
    assert not (LOCALES_DIR / _SHARD).exists()
    assert "01" in _casillas(probe)


def test_a_present_key_is_removed(probe: Path) -> None:
    """The ordinary path: one pass, one process, the leaf gone."""
    manifest = probe / "remove.json"
    manifest.write_text(json.dumps({"es": [_KEY]}), encoding="utf-8")

    result = _run(probe, "remove-batch", str(manifest))

    assert result.exit_code == 0, result.output
    assert "zztestprobe" not in _casillas(probe)


def test_an_absent_key_refuses_and_removes_nothing(probe: Path) -> None:
    """A key that is not there must not read as a successful deletion.

    The present key in the same manifest stays PUT: refusing after deleting
    half the batch would leave the caller worse off than refusing outright,
    and they would have to diff the catalogue to find out which half.
    """
    manifest = probe / "mixed.json"
    manifest.write_text(json.dumps({"es": [_KEY, _ABSENT]}), encoding="utf-8")

    result = _run(probe, "remove-batch", str(manifest))

    assert result.exit_code != 0
    assert "zznotthere" in result.output
    assert "zztestprobe" in _casillas(probe), "a refused batch must not have deleted anything"


def test_ignore_missing_applies_the_rest_and_names_what_it_skipped(probe: Path) -> None:
    """Re-running a manifest is legitimate; pretending it was complete is not."""
    manifest = probe / "mixed.json"
    manifest.write_text(json.dumps({"es": [_KEY, _ABSENT]}), encoding="utf-8")

    result = _run(probe, "remove-batch", str(manifest), "--ignore-missing")

    assert result.exit_code == 0, result.output
    assert "skipped 1" in result.output
    assert "zztestprobe" not in _casillas(probe)
