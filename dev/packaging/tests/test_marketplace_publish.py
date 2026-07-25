"""Real-filesystem tests for the account-scoped marketplace publish step.

Every test drives the real publish function against real on-disk trees — no
mocks, no patched filesystem. The property under test is the one the
account-scoped topology depends on: a release of one product must replace its
own plugin subtree and leave every sibling product's plugin, and every untracked
top-level file, exactly as it was.

The sibling-survival test is the anti-regression proof for the wholesale tree
replacement this module replaced: run against that earlier behaviour it fails,
because the sibling plugin and its index entry were both deleted.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest

from dev.packaging.marketplace_publish import (
    MarketplacePublishError,
    merge_marketplace_index,
    publish_cohort_plugins,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_UTF_8: Final[str] = "utf-8"
_INDEX: Final[Path] = Path(".claude-plugin") / "marketplace.json"


def _write_index(root: Path, document: dict[str, Any]) -> None:
    path = root / _INDEX
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding=_UTF_8)


def _write_plugin(root: Path, name: str, *, body: str) -> None:
    tree = root / "plugins" / name / ".claude-plugin"
    tree.mkdir(parents=True, exist_ok=True)
    (tree / "plugin.json").write_text(json.dumps({"name": name}), encoding=_UTF_8)
    (root / "plugins" / name / "marker.txt").write_text(body, encoding=_UTF_8)


def _read_index(root: Path) -> dict[str, Any]:
    return json.loads((root / _INDEX).read_text(encoding=_UTF_8))


def _cohort(tmp_path: Path, *, name: str, body: str) -> Path:
    cohort = tmp_path / f"cohort-{name}"
    _write_index(
        cohort,
        {
            "name": "neve",
            "description": "account marketplace",
            "owner": {"name": "publisher"},
            "plugins": [{"name": name, "source": f"./plugins/{name}"}],
        },
    )
    _write_plugin(cohort, name, body=body)
    return cohort


def test_publishing_one_product_leaves_a_sibling_plugin_and_its_index_entry_intact(tmp_path: Path) -> None:
    """A release of one product must not delete a sibling product's plugin."""
    marketplace = tmp_path / "marketplace"
    _write_index(
        marketplace,
        {
            "name": "neve",
            "description": "stale description",
            "owner": {"name": "publisher"},
            "plugins": [
                {"name": "cadrumo", "source": "./plugins/cadrumo"},
                {"name": "vaultspec", "source": "./plugins/vaultspec"},
            ],
        },
    )
    _write_plugin(marketplace, "cadrumo", body="old cadrumo")
    _write_plugin(marketplace, "vaultspec", body="sibling product")
    (marketplace / "README.md").write_text("account marketplace readme", encoding=_UTF_8)

    published = publish_cohort_plugins(
        marketplace=marketplace,
        cohort=_cohort(tmp_path, name="cadrumo", body="new cadrumo"),
    )

    assert published == ("cadrumo",)
    # This product's tree is replaced.
    assert (marketplace / "plugins" / "cadrumo" / "marker.txt").read_text(encoding=_UTF_8) == "new cadrumo"
    # The sibling's tree, its index entry, and unrelated top-level files survive.
    assert (marketplace / "plugins" / "vaultspec" / "marker.txt").read_text(encoding=_UTF_8) == "sibling product"
    assert (marketplace / "README.md").read_text(encoding=_UTF_8) == "account marketplace readme"
    entries = {entry["name"]: entry["source"] for entry in _read_index(marketplace)["plugins"]}
    assert entries == {"cadrumo": "./plugins/cadrumo", "vaultspec": "./plugins/vaultspec"}
    # Account-level metadata is refreshed from the cohort.
    assert _read_index(marketplace)["description"] == "account marketplace"


def test_publishing_into_an_empty_marketplace_creates_the_index_and_tree(tmp_path: Path) -> None:
    """A first release into a bare marketplace creates both the tree and the index."""
    marketplace = tmp_path / "empty"
    marketplace.mkdir()

    published = publish_cohort_plugins(
        marketplace=marketplace,
        cohort=_cohort(tmp_path, name="cadrumo", body="first release"),
    )

    assert published == ("cadrumo",)
    assert (marketplace / "plugins" / "cadrumo" / "marker.txt").read_text(encoding=_UTF_8) == "first release"
    assert [entry["name"] for entry in _read_index(marketplace)["plugins"]] == ["cadrumo"]


def test_republishing_the_same_cohort_is_byte_identical(tmp_path: Path) -> None:
    """Idempotence is what lets the caller decide to push on a real diff only."""
    marketplace = tmp_path / "marketplace"
    marketplace.mkdir()
    cohort = _cohort(tmp_path, name="cadrumo", body="same bytes")

    publish_cohort_plugins(marketplace=marketplace, cohort=cohort)
    first = (marketplace / _INDEX).read_bytes()
    first_marker = (marketplace / "plugins" / "cadrumo" / "marker.txt").read_bytes()

    publish_cohort_plugins(marketplace=marketplace, cohort=cohort)

    assert (marketplace / _INDEX).read_bytes() == first
    assert (marketplace / "plugins" / "cadrumo" / "marker.txt").read_bytes() == first_marker


def test_a_stale_file_inside_this_products_plugin_tree_is_removed(tmp_path: Path) -> None:
    """The owned subtree is replaced, not merged, so a dropped file really goes."""
    marketplace = tmp_path / "marketplace"
    _write_index(
        marketplace,
        {"name": "neve", "plugins": [{"name": "cadrumo", "source": "./plugins/cadrumo"}]},
    )
    _write_plugin(marketplace, "cadrumo", body="old")
    (marketplace / "plugins" / "cadrumo" / "retired-skill.md").write_text("gone", encoding=_UTF_8)

    publish_cohort_plugins(
        marketplace=marketplace,
        cohort=_cohort(tmp_path, name="cadrumo", body="new"),
    )

    assert not (marketplace / "plugins" / "cadrumo" / "retired-skill.md").exists()


def test_a_plugin_source_escaping_the_tree_is_refused(tmp_path: Path) -> None:
    """A `../` source would write outside the marketplace checkout; refuse it."""
    marketplace = tmp_path / "marketplace"
    marketplace.mkdir()
    cohort = tmp_path / "escaping"
    _write_index(
        cohort,
        {"name": "neve", "plugins": [{"name": "cadrumo", "source": "./../outside"}]},
    )

    with pytest.raises(MarketplacePublishError, match="escapes the marketplace tree"):
        publish_cohort_plugins(marketplace=marketplace, cohort=cohort)


def test_a_cohort_declaring_no_plugins_is_refused(tmp_path: Path) -> None:
    """An empty plugin list would publish nothing while reporting success."""
    marketplace = tmp_path / "marketplace"
    marketplace.mkdir()
    cohort = tmp_path / "empty-cohort"
    _write_index(cohort, {"name": "neve", "plugins": []})

    with pytest.raises(MarketplacePublishError, match="declares no plugins"):
        publish_cohort_plugins(marketplace=marketplace, cohort=cohort)


def test_a_declared_plugin_with_no_tree_is_refused(tmp_path: Path) -> None:
    """An index entry with no tree would register a plugin that cannot resolve."""
    marketplace = tmp_path / "marketplace"
    marketplace.mkdir()
    cohort = tmp_path / "indexed-only"
    _write_index(
        cohort,
        {"name": "neve", "plugins": [{"name": "cadrumo", "source": "./plugins/cadrumo"}]},
    )

    with pytest.raises(MarketplacePublishError, match="has no tree at"):
        publish_cohort_plugins(marketplace=marketplace, cohort=cohort)


def _multi_cohort(tmp_path: Path, *, product: str, plugins: dict[str, str], with_trees: set[str]) -> Path:
    """Build a cohort declaring several plugins, materialising only ``with_trees``."""
    cohort = tmp_path / f"cohort-multi-{product}"
    _write_index(
        cohort,
        {
            "name": "neve",
            "description": "account marketplace",
            "published_by": product,
            "plugins": [{"name": name, "source": f"./plugins/{name}"} for name in plugins],
        },
    )
    for name, body in plugins.items():
        if name in with_trees:
            _write_plugin(cohort, name, body=body)
    return cohort


def test_a_multi_plugin_cohort_that_refuses_partway_mutates_nothing(tmp_path: Path) -> None:
    """A refusal must leave the marketplace byte-identical, not half-published.

    Validation used to run inside the mutation loop, so a cohort whose second
    plugin had no tree refused only after the first had been replaced and left
    the index unmerged -- a state that is neither the old one nor the new one.
    """
    marketplace = tmp_path / "marketplace"
    _write_index(
        marketplace,
        {
            "name": "neve",
            "plugins": [{"name": "cadrumo", "source": "./plugins/cadrumo", "published_by": "cadrumo"}],
        },
    )
    _write_plugin(marketplace, "cadrumo", body="published cadrumo")
    before = {
        path.relative_to(marketplace).as_posix(): path.read_bytes()
        for path in sorted(marketplace.rglob("*"))
        if path.is_file()
    }

    cohort = _multi_cohort(
        tmp_path,
        product="cadrumo",
        plugins={"cadrumo": "new cadrumo", "cadrumo-extra": "never materialised"},
        with_trees={"cadrumo"},
    )

    with pytest.raises(MarketplacePublishError, match="has no tree at"):
        publish_cohort_plugins(marketplace=marketplace, cohort=cohort)

    after = {
        path.relative_to(marketplace).as_posix(): path.read_bytes()
        for path in sorted(marketplace.rglob("*"))
        if path.is_file()
    }
    assert after == before, "a refused publish mutated the marketplace tree"


def test_a_well_formed_multi_plugin_cohort_publishes_every_plugin(tmp_path: Path) -> None:
    """The multi-plugin path must actually work, not merely fail safely."""
    marketplace = tmp_path / "marketplace"
    marketplace.mkdir()
    cohort = _multi_cohort(
        tmp_path,
        product="suite",
        plugins={"alpha": "alpha body", "beta": "beta body"},
        with_trees={"alpha", "beta"},
    )

    published = publish_cohort_plugins(marketplace=marketplace, cohort=cohort)

    assert published == ("alpha", "beta")
    assert (marketplace / "plugins" / "alpha" / "marker.txt").read_text(encoding=_UTF_8) == "alpha body"
    assert (marketplace / "plugins" / "beta" / "marker.txt").read_text(encoding=_UTF_8) == "beta body"


def test_a_cohort_cannot_take_over_a_plugin_another_product_published(tmp_path: Path) -> None:
    """Name collision is the sibling-deletion bug by another route, and must refuse.

    Narrowing the wholesale replacement stopped a release deleting every
    sibling plugin. It did not stop a release deleting exactly one, by
    declaring the name that sibling already owns.
    """
    marketplace = tmp_path / "marketplace"
    _write_index(
        marketplace,
        {
            "name": "neve",
            "plugins": [{"name": "shared", "source": "./plugins/shared", "published_by": "vaultspec"}],
        },
    )
    _write_plugin(marketplace, "shared", body="vaultspec owns this")

    cohort = _multi_cohort(
        tmp_path,
        product="cadrumo",
        plugins={"shared": "cadrumo tries to take it"},
        with_trees={"shared"},
    )

    with pytest.raises(MarketplacePublishError, match="already published by another product"):
        publish_cohort_plugins(marketplace=marketplace, cohort=cohort)

    # The sibling's bytes and its attribution both survive the refusal.
    assert (marketplace / "plugins" / "shared" / "marker.txt").read_text(encoding=_UTF_8) == "vaultspec owns this"
    assert _read_index(marketplace)["plugins"][0]["published_by"] == "vaultspec"


def test_a_product_may_republish_its_own_plugin(tmp_path: Path) -> None:
    """Ownership must not block the ordinary case of a product releasing again."""
    marketplace = tmp_path / "marketplace"
    _write_index(
        marketplace,
        {
            "name": "neve",
            "plugins": [{"name": "cadrumo", "source": "./plugins/cadrumo", "published_by": "cadrumo"}],
        },
    )
    _write_plugin(marketplace, "cadrumo", body="old")

    publish_cohort_plugins(
        marketplace=marketplace,
        cohort=_cohort(tmp_path, name="cadrumo", body="new"),
    )

    assert (marketplace / "plugins" / "cadrumo" / "marker.txt").read_text(encoding=_UTF_8) == "new"


def test_an_unattributed_published_entry_is_claimable(tmp_path: Path) -> None:
    """An entry predating ownership tracking must not deadlock the release adopting it."""
    marketplace = tmp_path / "marketplace"
    _write_index(
        marketplace,
        {"name": "neve", "plugins": [{"name": "cadrumo", "source": "./plugins/cadrumo"}]},
    )
    _write_plugin(marketplace, "cadrumo", body="legacy")

    publish_cohort_plugins(
        marketplace=marketplace,
        cohort=_cohort(tmp_path, name="cadrumo", body="adopted"),
    )

    entry = _read_index(marketplace)["plugins"][0]
    assert entry["published_by"] == "cadrumo"
    assert (marketplace / "plugins" / "cadrumo" / "marker.txt").read_text(encoding=_UTF_8) == "adopted"


def test_a_multi_plugin_cohort_must_declare_its_publisher(tmp_path: Path) -> None:
    """Ownership cannot be inferred from a multi-plugin cohort, so it must be declared."""
    marketplace = tmp_path / "marketplace"
    marketplace.mkdir()
    cohort = tmp_path / "unattributed"
    _write_index(
        cohort,
        {
            "name": "neve",
            "plugins": [
                {"name": "alpha", "source": "./plugins/alpha"},
                {"name": "beta", "source": "./plugins/beta"},
            ],
        },
    )
    _write_plugin(cohort, "alpha", body="a")
    _write_plugin(cohort, "beta", body="b")

    with pytest.raises(MarketplacePublishError, match="published_by"):
        publish_cohort_plugins(marketplace=marketplace, cohort=cohort)


def test_merge_replaces_an_entry_the_cohort_renames_rather_than_duplicating_it() -> None:
    """A cohort entry wins over its own published entry, and is stamped with its owner."""
    merged = merge_marketplace_index(
        cohort_index={
            "name": "neve",
            "plugins": [{"name": "cadrumo", "source": "./plugins/cadrumo", "version": "0.3.0"}],
        },
        existing_index={
            "name": "neve",
            "plugins": [{"name": "cadrumo", "source": "./plugins/cadrumo", "version": "0.2.1"}],
        },
    )

    assert merged["plugins"] == [
        {
            "name": "cadrumo",
            "source": "./plugins/cadrumo",
            "version": "0.3.0",
            "published_by": "cadrumo",
        }
    ]
