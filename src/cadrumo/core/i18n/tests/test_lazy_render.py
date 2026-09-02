"""Targeted unit tests for lazy shard loading, routing, and dual-tier fallback."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from .. import tr
from .._lazy_catalogue import LazyLocaleCatalogue
from ..render import override_locales_root
from ..routing import route_key_to_shard

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_route_key_to_shard_taxonomy() -> None:
    """Verify deterministic routing from dotted keys to relative shard paths."""
    assert route_key_to_shard("modelo.schema.303.casilla.01.label") == Path("modelo/schema/303.yml")
    assert route_key_to_shard("modelo.schema.100.general.title") == Path("modelo/schema/100.yml")
    assert route_key_to_shard("modelo.intro.description") == Path("modelo/general.yml")
    assert route_key_to_shard("cli.root.app_help") == Path("cli.yml")
    assert route_key_to_shard("errors.connection_refused") == Path("errors.yml")
    assert route_key_to_shard("wizard.setup.step1") == Path("wizard.yml")
    assert route_key_to_shard("application.runtime.version") == Path("application.yml")
    assert route_key_to_shard("flows.auth.login") == Path("flows.yml")
    assert route_key_to_shard("docs.reference.usage") == Path("docs.yml")
    assert route_key_to_shard("profile.active.name") == Path("profile.yml")
    assert route_key_to_shard("adapters.aeat.endpoint") == Path("adapters.yml")
    assert route_key_to_shard("unrecognized.root.key") == Path("common.yml")


def test_lazy_catalogue_targeted_loading() -> None:
    """Verify that only the requested shard is parsed and cached."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        es_dir = tmp / "es"
        (es_dir / "cli").parent.mkdir(parents=True)
        (es_dir / "cli.yml").write_text("cli:\n  root:\n    app_help: 'Spanish Help'\n", encoding="utf-8")

        schema_dir = es_dir / "modelo" / "schema"
        schema_dir.mkdir(parents=True)
        (schema_dir / "303.yml").write_text(
            "modelo:\n  schema:\n    '303':\n      casilla:\n        '01':\n          label: 'IVA Devengado'\n",
            encoding="utf-8",
        )
        (schema_dir / "100.yml").write_text(
            "modelo:\n  schema:\n    '100':\n      casilla:\n        '01':\n          label: 'IRPF Base'\n",
            encoding="utf-8",
        )

        catalogue = LazyLocaleCatalogue("es", shard_dir=es_dir)

        # Before any access, nothing is loaded
        assert len(catalogue._loaded_shards) == 0

        # Accessing a CLI key should load only cli.yml
        val = catalogue["cli.root.app_help"]
        assert val == "Spanish Help"
        assert Path("cli.yml") in catalogue._loaded_shards
        assert Path("modelo/schema/303.yml") not in catalogue._loaded_shards
        assert Path("modelo/schema/100.yml") not in catalogue._loaded_shards

        # Accessing M303 loads 303.yml, leaving 100.yml unparsed
        val_303 = catalogue["modelo.schema.303.casilla.01.label"]
        assert val_303 == "IVA Devengado"
        assert Path("modelo/schema/303.yml") in catalogue._loaded_shards
        assert Path("modelo/schema/100.yml") not in catalogue._loaded_shards


def test_lazy_catalogue_missing_key_behavior() -> None:
    """Verify that absent keys raise KeyError or return None/default via get()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        es_dir = tmp / "es"
        es_dir.mkdir(parents=True)
        (es_dir / "cli.yml").write_text("cli:\n  root:\n    app_help: 'Sharded Help'\n", encoding="utf-8")

        catalogue = LazyLocaleCatalogue("es", shard_dir=es_dir)

        assert catalogue["cli.root.app_help"] == "Sharded Help"
        assert catalogue.get("cli.root.nonexistent") is None
        assert catalogue.get("cli.root.nonexistent", "default") == "default"
        with pytest.raises(KeyError):
            _ = catalogue["cli.root.nonexistent"]


def test_override_locales_root_with_shards() -> None:
    """Verify override_locales_root works seamlessly with sharded directory trees."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        en_dir = tmp / "en"
        en_dir.mkdir(parents=True)
        (en_dir / "cli.yml").write_text("cli:\n  test:\n    msg: 'English message'\n", encoding="utf-8")

        with override_locales_root(tmp):
            rendered = tr("cli.test.msg", locale="en")
            assert rendered == "English message"
