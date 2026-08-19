"""Unit tests for LocaleManager operating over domain- and Modelo-sharded catalogues."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ..manager import LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_sharded_load_locale_merges_all_shards() -> None:
    """Verify load_locale deep-merges all shard files in a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        locales_dir = tmp / "locales"
        es_dir = locales_dir / "es"
        (es_dir / "cli").parent.mkdir(parents=True)
        (es_dir / "cli.yml").write_text("cli:\n  root:\n    help: 'Ayuda CLI'\n", encoding="utf-8")

        schema_dir = es_dir / "modelo" / "schema"
        schema_dir.mkdir(parents=True)
        (schema_dir / "303.yml").write_text(
            "modelo:\n  schema:\n    '303':\n      casilla:\n        '01':\n          label: 'IVA'\n",
            encoding="utf-8",
        )

        manager = LocaleManager(src_dir=tmp, locales_dir=locales_dir)
        loaded = manager.load_locale(es_dir)

        assert "cli" in loaded
        assert "modelo" in loaded
        assert loaded["cli"]["root"]["help"] == "Ayuda CLI"
        assert loaded["modelo"]["schema"]["303"]["casilla"]["01"]["label"] == "IVA"


def test_sharded_set_and_remove_locale_value() -> None:
    """Verify set_locale_value writes to targeted shard and remove_locale_value removes from targeted shard."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        locales_dir = tmp / "locales"
        es_dir = locales_dir / "es"
        es_dir.mkdir(parents=True)

        manager = LocaleManager(src_dir=tmp, locales_dir=locales_dir)

        # Set a CLI key -> routes to cli.yml
        target1 = manager.set_locale_value("es", "cli.menu.exit", "Salir")
        assert target1 == es_dir / "cli.yml"
        assert target1.is_file()

        # Set a Modelo 303 key -> routes to modelo/schema/303.yml
        target2 = manager.set_locale_value("es", "modelo.schema.303.casilla.05.label", "Cuota")
        assert target2 == es_dir / "modelo" / "schema" / "303.yml"
        assert target2.is_file()

        # Check loaded data
        loaded = manager.load_locale(es_dir)
        assert loaded["cli"]["menu"]["exit"] == "Salir"
        assert loaded["modelo"]["schema"]["303"]["casilla"]["05"]["label"] == "Cuota"

        # Remove the CLI key
        removed_target = manager.remove_locale_value("es", "cli.menu.exit")
        assert removed_target == es_dir / "cli.yml"

        loaded_after = manager.load_locale(es_dir)
        assert "cli" not in loaded_after or not loaded_after["cli"]


def test_sharded_scaffold_partitions_keys() -> None:
    """Verify scaffold partitions codebase keys across domain shards."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        src_dir = tmp / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text(
            "from cadrumo.core.i18n import tr\n"
            'tr("cli.cmd.start")\n'
            'tr("modelo.schema.303.casilla.01.label")\n'
            'tr("other.unclassified.key")\n',
            encoding="utf-8",
        )

        locales_dir = tmp / "locales"
        es_dir = locales_dir / "es"
        es_dir.mkdir(parents=True)

        manager = LocaleManager(src_dir=src_dir, locales_dir=locales_dir)
        manager._codebase_keys = frozenset(
            {"cli.cmd.start", "modelo.schema.303.casilla.01.label", "other.unclassified.key"},
        )
        # Pre-seed values
        manager.set_locale_value("es", "cli.cmd.start", "Iniciar")
        manager.set_locale_value("es", "modelo.schema.303.casilla.01.label", "Base")
        manager.set_locale_value("es", "other.unclassified.key", "Otro")

        manager.scaffold()

        assert (es_dir / "cli.yml").is_file()
        assert (es_dir / "modelo" / "schema" / "303.yml").is_file()
        assert (es_dir / "common.yml").is_file()

        loaded = manager.load_locale(es_dir)
        assert loaded["cli"]["cmd"]["start"] == "Iniciar"
        assert loaded["modelo"]["schema"]["303"]["casilla"]["01"]["label"] == "Base"
        assert loaded["other"]["unclassified"]["key"] == "Otro"
