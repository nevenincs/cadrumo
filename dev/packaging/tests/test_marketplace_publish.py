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

from cadrumo.core import scan_directory
from dev._paths import REPO_ROOT, UTF_8

from ..marketplace_publish import (
    _SUPERSESSION_REPORT,
    MarketplacePublishError,
    SupersessionVerdict,
    assert_supersession_complete,
    merge_marketplace_index,
    publish_cohort_plugins,
    superseded_names,
)
from ..marketplace_publish import _read_cohort_index as read_cohort_index

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_UTF_8: Final[str] = UTF_8
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
        for path in scan_directory(marketplace, recursive=True)
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
        for path in scan_directory(marketplace, recursive=True)
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


def _superseding_cohort(tmp_path: Path, *, name: str, retires: list[str], body: str = "new") -> Path:
    """A cohort that claims ``name`` and declares ``retires`` superseded."""
    cohort = tmp_path / f"cohort-{name}-supersedes"
    _write_index(
        cohort,
        {
            "name": "neve",
            "description": "account marketplace",
            "owner": {"name": "publisher"},
            "supersedes": retires,
            "plugins": [{"name": name, "source": f"./plugins/{name}"}],
        },
    )
    _write_plugin(cohort, name, body=body)
    return cohort


def test_a_rename_claims_the_new_name_and_retires_the_old_one(tmp_path: Path) -> None:
    """One publication, never a state where both identities are live.

    The retired entry carries no recorded publisher because it predates
    ownership tracking, which is exactly the claimable case: under the unchanged
    rule this cohort could already overwrite it wholesale, so retiring it grants
    no authority the tool did not have.
    """
    marketplace = tmp_path / "marketplace"
    _write_index(
        marketplace,
        {
            "name": "neve",
            "description": "old identity",
            "owner": {"name": "publisher"},
            "plugins": [{"name": "aeat", "source": "./plugins/aeat"}],
        },
    )
    _write_plugin(marketplace, "aeat", body="old")

    publish_cohort_plugins(
        marketplace=marketplace, cohort=_superseding_cohort(tmp_path, name="cadrumo", retires=["aeat"])
    )

    names = [entry["name"] for entry in _read_index(marketplace)["plugins"]]
    assert names == ["cadrumo"], "the retired identity must not remain live alongside the new one"
    assert not (marketplace / "plugins" / "aeat").exists(), "the retired subtree must go with its entry"
    assert (marketplace / "plugins" / "cadrumo" / "marker.txt").read_text(encoding=_UTF_8) == "new"


def test_a_siblings_plugin_can_never_be_superseded(tmp_path: Path) -> None:
    """The guard that exists because a wholesale replacement deleted every sibling.

    Supersession must not become the delete authority that incident produced, so
    a name another product recorded itself as publishing is refused outright.
    """
    marketplace = tmp_path / "marketplace"
    _write_index(
        marketplace,
        {
            "name": "neve",
            "description": "account marketplace",
            "owner": {"name": "publisher"},
            "plugins": [{"name": "vaultspec", "source": "./plugins/vaultspec", "published_by": "vaultspec"}],
        },
    )
    _write_plugin(marketplace, "vaultspec", body="sibling")

    with pytest.raises(MarketplacePublishError, match="published by another product"):
        publish_cohort_plugins(
            marketplace=marketplace,
            cohort=_superseding_cohort(tmp_path, name="cadrumo", retires=["vaultspec"]),
        )
    assert (marketplace / "plugins" / "vaultspec" / "marker.txt").read_text(encoding=_UTF_8) == "sibling"
    assert [entry["name"] for entry in _read_index(marketplace)["plugins"]] == ["vaultspec"]


def test_superseding_is_idempotent_once_the_entry_is_gone(tmp_path: Path) -> None:
    """The declaration ships in every later cohort, so it must re-run cleanly.

    This is why supersession is declared rather than executed once by hand: a
    replay finds nothing to retire and says so by doing nothing, while the
    declaration keeps refusing any later attempt to resurrect the name.
    """
    marketplace = tmp_path / "marketplace"
    _write_index(
        marketplace,
        {"name": "neve", "description": "d", "owner": {"name": "publisher"}, "plugins": []},
    )
    cohort = _superseding_cohort(tmp_path, name="cadrumo", retires=["aeat"])
    publish_cohort_plugins(marketplace=marketplace, cohort=cohort)
    publish_cohort_plugins(marketplace=marketplace, cohort=cohort)
    assert [entry["name"] for entry in _read_index(marketplace)["plugins"]] == ["cadrumo"]


def test_claiming_and_superseding_one_name_is_refused(tmp_path: Path) -> None:
    """The two verbs disagree; preferring either silently is worse than refusing."""
    marketplace = tmp_path / "marketplace"
    _write_index(marketplace, {"name": "neve", "description": "d", "owner": {"name": "p"}, "plugins": []})
    with pytest.raises(MarketplacePublishError, match="both declares and supersedes"):
        publish_cohort_plugins(
            marketplace=marketplace,
            cohort=_superseding_cohort(tmp_path, name="cadrumo", retires=["cadrumo"]),
        )


def test_a_malformed_supersedes_declaration_refuses(tmp_path: Path) -> None:
    """A declaration that cannot be read must not be read as "retire nothing"."""
    marketplace = tmp_path / "marketplace"
    _write_index(marketplace, {"name": "neve", "description": "d", "owner": {"name": "p"}, "plugins": []})
    cohort = _superseding_cohort(tmp_path, name="cadrumo", retires=[])
    index = _read_index(cohort)
    index["supersedes"] = "aeat"
    _write_index(cohort, index)
    with pytest.raises(MarketplacePublishError, match="list of non-empty plugin names"):
        publish_cohort_plugins(marketplace=marketplace, cohort=cohort)


def test_the_shipped_cohort_manifest_retires_the_former_product_identity() -> None:
    """The declaration must actually ship, or the mechanism protects nothing.

    The live marketplace still carries the pre-rename identity, and its entry
    records no publisher, so any product could claim that name today. This is
    the declaration that retires it on the first publication and keeps refusing
    its resurrection on every later one.
    """
    scaffold = REPO_ROOT / "packaging" / "marketplace"
    index = read_cohort_index(scaffold)
    assert superseded_names(index) == frozenset({"aeat"})
    declared = {entry["name"] for entry in index["plugins"]}
    assert "aeat" not in declared, "the retired identity must not also be claimed"
    assert "cadrumo" in declared

    # The declaration must NOT sit in the served manifest. `claude plugin
    # validate --strict` rejects the unknown field and Claude Code ignores it at
    # load, so moving it back there would trade a live retirement for a red gate.
    served = json.loads((scaffold / _INDEX).read_text(encoding=_UTF_8))
    assert "supersedes" not in served


def test_the_generated_cohort_declares_the_retirement_not_only_the_scaffold(tmp_path: Path) -> None:
    """The artifact that publishes must carry the declaration, not its sibling.

    The scaffold above is a checked-in copy; what a release actually pushes is
    the marketplace tree the generator emits into the cohort bundle. Asserting
    only the scaffold leaves the two free to diverge, and a divergence there is
    silent: the publisher would read an empty retirement set, the preflight would
    return early having nothing to verify, and the retired identity would survive
    every publication with no gate reporting anything.
    """
    from cadrumo_harness import materialise_marketplace

    generated = tmp_path / "generated-marketplace"
    materialise_marketplace(generated)
    assert superseded_names(read_cohort_index(generated)) == frozenset({"aeat"})
    assert "supersedes" not in json.loads((generated / _INDEX).read_text(encoding=_UTF_8))


def test_declaring_the_retirement_in_both_homes_is_refused(tmp_path: Path) -> None:
    """Two homes are ambiguous, and silently preferring one hides a lost retirement."""
    cohort = _superseding_cohort(tmp_path, name="cadrumo", retires=["aeat"])
    sidecar = cohort / ".claude-plugin" / "supersedes.json"
    sidecar.write_text(json.dumps({"supersedes": ["aeat"]}) + "\n", encoding=_UTF_8)
    with pytest.raises(MarketplacePublishError, match="the sidecar is the only home"):
        read_cohort_index(cohort)


def _published_marketplace(tmp_path: Path, *, plugins: list[dict[str, Any]], **index: Any) -> Path:
    marketplace = tmp_path / "verified"
    document: dict[str, Any] = {
        "name": "neve",
        "description": "account marketplace",
        "owner": {"name": "publisher"},
        "plugins": plugins,
    }
    document.update(index)
    _write_index(marketplace, document)
    return marketplace


def test_the_preflight_passes_once_the_retired_identity_is_gone(tmp_path: Path) -> None:
    """The permit case, or the refusals below prove nothing."""
    marketplace = _published_marketplace(tmp_path, plugins=[{"name": "cadrumo", "source": "./plugins/cadrumo"}])
    assert_supersession_complete(
        marketplace=marketplace,
        cohort=_superseding_cohort(tmp_path, name="cadrumo", retires=["aeat"]),
    )


def test_the_preflight_refuses_while_the_retired_entry_is_live(tmp_path: Path) -> None:
    """Two identities for one product must never both be published."""
    marketplace = _published_marketplace(
        tmp_path,
        plugins=[{"name": "cadrumo", "source": "./plugins/cadrumo"}, {"name": "aeat", "source": "./plugins/aeat"}],
    )
    with pytest.raises(MarketplacePublishError, match="still live in the marketplace index"):
        assert_supersession_complete(
            marketplace=marketplace,
            cohort=_superseding_cohort(tmp_path, name="cadrumo", retires=["aeat"]),
        )


def test_the_preflight_refuses_an_unreferenced_retired_tree(tmp_path: Path) -> None:
    """A tree with no index entry is still fetchable by direct path.

    Dropping the entry but leaving the directory looks clean in the index and
    still serves the old identity to anyone who knows the path.
    """
    marketplace = _published_marketplace(tmp_path, plugins=[{"name": "cadrumo", "source": "./plugins/cadrumo"}])
    _write_plugin(marketplace, "aeat", body="orphaned")
    with pytest.raises(MarketplacePublishError, match="remain on disk without an index entry"):
        assert_supersession_complete(
            marketplace=marketplace,
            cohort=_superseding_cohort(tmp_path, name="cadrumo", retires=["aeat"]),
        )


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        pytest.param({"description": "install aeat@neve to file your taxes"}, "description", id="description-handle"),
        pytest.param({"description": "served from ./plugins/aeat"}, "description", id="description-path"),
        pytest.param({"owner": {"name": "AEAT tax assistant project"}}, "owner.name", id="owner-name"),
    ],
)
def test_the_preflight_refuses_metadata_that_still_names_the_retired_identity(
    overrides: dict[str, Any],
    fragment: str,
    tmp_path: Path,
) -> None:
    """A half-renamed marketplace cannot tell a reader which half is true."""
    marketplace = _published_marketplace(
        tmp_path,
        plugins=[{"name": "cadrumo", "source": "./plugins/cadrumo"}],
        **overrides,
    )
    with pytest.raises(MarketplacePublishError, match=fragment):
        assert_supersession_complete(
            marketplace=marketplace,
            cohort=_superseding_cohort(tmp_path, name="cadrumo", retires=["aeat"]),
        )


def test_naming_the_tax_authority_in_prose_is_not_a_stale_identity(tmp_path: Path) -> None:
    """The retired plugin name is also the tax authority's name, and prose may say it.

    This is the case that makes the guard usable rather than a permanent outage.
    The shipped marketplace description says the assistant is "read-only toward
    AEAT" in English and "frente a la AEAT" in Spanish, which is required copy
    about the authority, not residue of the retired plugin identity. A substring
    test cannot tell those apart and would refuse every publication forever,
    which reads as the guard working while nothing can ever ship.
    """
    marketplace = _published_marketplace(
        tmp_path,
        plugins=[{"name": "cadrumo", "source": "./plugins/cadrumo"}],
        description="Cadrumo: read-only toward AEAT, it never files. Español: frente a la AEAT.",
    )
    assert_supersession_complete(
        marketplace=marketplace,
        cohort=_superseding_cohort(tmp_path, name="cadrumo", retires=["aeat"]),
    )


def test_the_real_generated_description_survives_the_preflight(tmp_path: Path) -> None:
    """The guard must permit the description this product actually publishes.

    The case above is hand-written and could drift from the shipped copy. This one
    runs the preflight against the generator's own bilingual description, so the
    guard is proven against the exact bytes a release pushes rather than a
    paraphrase of them.
    """
    from cadrumo_harness import materialise_marketplace

    cohort = tmp_path / "generated-cohort"
    materialise_marketplace(cohort)
    shipped = json.loads((cohort / _INDEX).read_text(encoding=_UTF_8))
    marketplace = _published_marketplace(
        tmp_path,
        plugins=[{"name": "cadrumo", "source": "./plugins/cadrumo"}],
        description=shipped["description"],
        owner=shipped["owner"],
    )
    assert_supersession_complete(marketplace=marketplace, cohort=cohort)


def test_a_cohort_that_retires_nothing_is_not_checked(tmp_path: Path) -> None:
    """The preflight is scoped to declared retirements, not a general scan."""
    marketplace = _published_marketplace(
        tmp_path,
        plugins=[{"name": "cadrumo", "source": "./plugins/cadrumo"}, {"name": "aeat", "source": "./plugins/aeat"}],
    )
    assert_supersession_complete(marketplace=marketplace, cohort=_cohort(tmp_path, name="cadrumo", body="x"))


def test_the_preflight_reports_that_a_verified_run_actually_checked_something(tmp_path: Path) -> None:
    """A permit says WHICH question it answered, not merely that it did not refuse."""
    marketplace = _published_marketplace(tmp_path, plugins=[{"name": "cadrumo", "source": "./plugins/cadrumo"}])

    verdict = assert_supersession_complete(
        marketplace=marketplace,
        cohort=_superseding_cohort(tmp_path, name="cadrumo", retires=["aeat"]),
    )

    assert verdict is SupersessionVerdict.VERIFIED


def test_a_marketplace_that_does_not_exist_is_refused_rather_than_reported_clean(tmp_path: Path) -> None:
    """A wrong path leaves the invariant UNVERIFIED, which is not the same as satisfied.

    The verb takes the marketplace as an operator-supplied path, so pointing it
    somewhere wrong is an ordinary mistake. It previously returned silently and
    the CLI printed that no retired identity survives -- a confident claim about
    an index it had never opened.
    """
    with pytest.raises(MarketplacePublishError, match="UNVERIFIED"):
        assert_supersession_complete(
            marketplace=tmp_path / "no-such-checkout",
            cohort=_superseding_cohort(tmp_path, name="cadrumo", retires=["aeat"]),
        )


def test_a_marketplace_with_no_published_index_is_reported_as_not_checked(tmp_path: Path) -> None:
    """A first release has nothing published to contradict, and says so.

    Distinct from the refusal above: the checkout exists, there is simply no
    index yet. Both used to return the same silent success.
    """
    marketplace = tmp_path / "empty-checkout"
    marketplace.mkdir()

    verdict = assert_supersession_complete(
        marketplace=marketplace,
        cohort=_superseding_cohort(tmp_path, name="cadrumo", retires=["aeat"]),
    )

    assert verdict is SupersessionVerdict.NOTHING_PUBLISHED


def test_every_verdict_reports_a_distinct_line_and_only_one_claims_the_invariant() -> None:
    """The operator-visible half: three outcomes must not read as one.

    A verdict added later without a report line would raise here rather than
    silently reusing another outcome's wording.
    """
    lines = {verdict: _SUPERSESSION_REPORT[verdict] for verdict in SupersessionVerdict}

    assert len(set(lines.values())) == len(SupersessionVerdict)
    assert not lines[SupersessionVerdict.VERIFIED].startswith("NOT CHECKED")
    for verdict in (SupersessionVerdict.NOTHING_RETIRED, SupersessionVerdict.NOTHING_PUBLISHED):
        assert lines[verdict].startswith("NOT CHECKED"), (
            f"{verdict} reports as though the invariant was established: {lines[verdict]!r}"
        )
