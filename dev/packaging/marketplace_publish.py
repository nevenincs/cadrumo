"""Publish a release cohort's plugin tree into an account-scoped marketplace.

The Claude plugin marketplace this project publishes to is account-scoped: it is
named for the publishing account, not for this product, and is expected to serve
sibling products published under the same account. A release therefore must
replace only the plugin subtrees its own cohort declares and merge its entries
into the marketplace index by plugin name.

The earlier publish step replaced the marketplace's tracked tree wholesale. That
is correct only while exactly one product is served: against a shared
marketplace it silently deletes every sibling product's plugin on the next
release of any one product. This module is the narrowed replacement.

Publishing the same cohort twice leaves the tree byte-identical, so the caller's
"nothing staged, nothing to push" check is the one that decides whether a commit
happens. A refusal leaves the tree untouched: the whole cohort is validated
before anything is mutated, so a cohort whose second plugin is malformed does not
leave the first already replaced.

Ownership is recorded on each index entry, so a cohort cannot take over a plugin
name a different product already published. Without that, the wholesale deletion
this module replaced would simply return by another route — as a targeted
overwrite of exactly one sibling rather than all of them.

Known limitation: concurrent publication is not serialised here. Two products
releasing into one marketplace can interleave clone and push, making the second
push a non-fast-forward that fails the release. That is a designed-in condition
under a shared marketplace rather than an edge case, and the remedy belongs in
the caller — a repository-level concurrency group serialising marketplace
publication across products, or a re-clone-and-reapply retry on a rejected push.
This module is safe under that retry because it is a pure function of the
marketplace tree and the cohort.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Final

_UTF_8: Final[str] = "utf-8"
_INDEX_RELATIVE: Final[Path] = Path(".claude-plugin") / "marketplace.json"


class MarketplacePublishError(RuntimeError):
    """A cohort or marketplace tree that cannot be published safely."""


def _read_index(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding=_UTF_8))
    except json.JSONDecodeError as exc:  # pragma: no cover - corrupt input
        raise MarketplacePublishError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise MarketplacePublishError(f"{path} must contain a JSON object")
    return document


def _declared_plugins(index: dict[str, Any], *, source: Path) -> list[dict[str, Any]]:
    plugins = index.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        raise MarketplacePublishError(f"{source} declares no plugins")
    for entry in plugins:
        if not isinstance(entry, dict) or "name" not in entry or "source" not in entry:
            raise MarketplacePublishError(f"{source} has a plugin entry without a name and source: {entry!r}")
    return plugins


def _plugin_relative_path(entry: dict[str, Any]) -> Path:
    """Return the in-tree path for a plugin entry, refusing an escaping source.

    A marketplace index is data the publish job copies onto a real repository, so
    a ``source`` that climbs out of the tree (``../``) or is absolute would let a
    malformed cohort write outside the marketplace checkout. Both are refused
    rather than normalised.
    """
    source = entry["source"]
    if not isinstance(source, str) or not source.startswith("./"):
        raise MarketplacePublishError(f"plugin {entry['name']!r} source must be a './'-relative path, got {source!r}")
    relative = Path(source[2:])
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise MarketplacePublishError(f"plugin {entry['name']!r} source escapes the marketplace tree: {source!r}")
    return relative


def _publishing_product(index: dict[str, Any]) -> str:
    """Return the product this cohort publishes under, used as the ownership key.

    A marketplace index does not name its publisher, so the cohort's own
    marketplace manifest supplies it. Falling back to the sole declared plugin
    name keeps a single-plugin cohort working without extra ceremony.
    """
    product = index.get("published_by")
    if isinstance(product, str) and product:
        return product
    plugins = index.get("plugins")
    if isinstance(plugins, list) and len(plugins) == 1 and isinstance(plugins[0], dict):
        name = plugins[0].get("name")
        if isinstance(name, str) and name:
            return name
    raise MarketplacePublishError(
        "cohort marketplace index must declare 'published_by' when it publishes more than one plugin, "
        "so a sibling product's entry cannot be taken over by name collision"
    )


def superseded_names(index: dict[str, Any]) -> frozenset[str]:
    """Return the plugin names this cohort declares it retires.

    Supersession is DECLARED by the cohort rather than held as a delete list in
    the tool, for two reasons. A standing delete authority decoupled from any
    release is the shape of the incident that made the ownership rule necessary.
    And a declaration ships in every later cohort, so retirement becomes an
    enforced invariant rather than a one-time act: a replay, an old manifest, or
    a stranger claiming the abandoned name is refused again, whereas a hand
    deletion is forgotten the moment it completes.
    """
    raw = index.get("supersedes")
    if raw is None:
        return frozenset()
    if not isinstance(raw, list) or not all(isinstance(name, str) and name for name in raw):
        raise MarketplacePublishError(
            "cohort marketplace index 'supersedes' must be a list of non-empty plugin names",
        )
    return frozenset(raw)


def merge_marketplace_index(
    *,
    cohort_index: dict[str, Any],
    existing_index: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge a cohort's marketplace index over the published one.

    Account-level metadata (name, description, owner) is taken from the cohort,
    which ships the account's canonical marketplace manifest. The plugin list
    keeps every published entry the cohort does not itself name, so a sibling
    product's registration survives this product's release. Entries are sorted by
    name so the pushed document is stable regardless of merge order.

    Each entry carries ``published_by``. A cohort may replace an entry it
    published and is refused an entry another product published, so taking over
    a sibling's plugin by declaring its name is not silently possible. An entry
    with no recorded publisher predates ownership tracking and is treated as
    claimable, since refusing it would deadlock the first release that adopts it.
    """
    declared = _declared_plugins(cohort_index, source=Path("cohort"))
    product = _publishing_product(cohort_index)
    owned = {entry["name"] for entry in declared}
    superseded = superseded_names(cohort_index)
    published = (existing_index or {}).get("plugins", [])

    # A name cannot be both claimed and retired by one cohort: the two verbs
    # disagree about what the published tree should end up holding, and silently
    # preferring either is worse than refusing.
    contradiction = sorted(owned & superseded)
    if contradiction:
        raise MarketplacePublishError(
            f"cohort for {product!r} both declares and supersedes plugin(s) {contradiction}; "
            "a rename claims the new name and retires the old one, never the same name twice"
        )

    stolen = sorted(
        str(entry["name"])
        for entry in published
        if isinstance(entry, dict)
        and entry.get("name") in owned
        and isinstance(entry.get("published_by"), str)
        and entry["published_by"] != product
    )
    if stolen:
        raise MarketplacePublishError(
            f"cohort for {product!r} declares plugin(s) {stolen} already published by another product; "
            "refusing to overwrite a sibling's plugin tree and index entry"
        )

    # Supersession obeys the ownership rule UNCHANGED. A cohort may retire a
    # name it published, or one with no recorded publisher, which is exactly the
    # set it could already claim and overwrite wholesale. It may not retire a
    # sibling's, so the guard that exists because a wholesale replacement once
    # deleted every sibling is not weakened by one bit -- same bounds, one more
    # verb.
    not_ours = sorted(
        str(entry["name"])
        for entry in published
        if isinstance(entry, dict)
        and entry.get("name") in superseded
        and isinstance(entry.get("published_by"), str)
        and entry["published_by"] != product
    )
    if not_ours:
        raise MarketplacePublishError(
            f"cohort for {product!r} supersedes plugin(s) {not_ours} published by another product; "
            "retiring a sibling's plugin is the deletion this guard exists to prevent"
        )

    attributed = [{**entry, "published_by": product} for entry in declared]
    retained = [
        entry
        for entry in published
        if isinstance(entry, dict) and entry.get("name") not in owned and entry.get("name") not in superseded
    ]
    document = dict(cohort_index)
    document["plugins"] = sorted([*attributed, *retained], key=lambda entry: str(entry["name"]))
    return document


def publish_cohort_plugins(*, marketplace: Path, cohort: Path) -> tuple[str, ...]:
    """Replace the cohort's own plugin subtrees in ``marketplace`` and merge the index.

    Returns the names of the plugins this cohort published, in sorted order.
    Every path in the marketplace that the cohort does not declare — a sibling
    plugin, a README, a LICENSE — is left exactly as it was.
    """
    cohort_index_path = cohort / _INDEX_RELATIVE
    if not cohort_index_path.is_file():
        raise MarketplacePublishError(f"cohort marketplace index missing: {cohort_index_path}")
    cohort_index = _read_index(cohort_index_path)
    declared = _declared_plugins(cohort_index, source=cohort_index_path)

    # Validate the WHOLE cohort before touching the marketplace. Validating
    # inside the mutation loop left a refusal on the Nth plugin with plugins
    # 1..N-1 already replaced and the index unmerged -- a torn tree that is
    # neither the old state nor the new one.
    planned: list[tuple[Path, Path]] = []
    for entry in declared:
        relative = _plugin_relative_path(entry)
        source_tree = cohort / relative
        if not source_tree.is_dir():
            raise MarketplacePublishError(f"cohort plugin {entry['name']!r} has no tree at {source_tree}")
        planned.append((relative, source_tree))

    # The index merge is the other refusal path (an ownership collision), so it
    # is computed before any mutation too.
    published_index_path = marketplace / _INDEX_RELATIVE
    existing = _read_index(published_index_path) if published_index_path.is_file() else None
    merged = merge_marketplace_index(cohort_index=cohort_index, existing_index=existing)

    # Superseded subtrees are resolved from the PUBLISHED index, before any
    # mutation, for the same reason the merge is: the entry names its own path,
    # and once the index is rewritten that path is gone.
    retiring: list[Path] = []
    for name in sorted(superseded_names(cohort_index)):
        entry = next(
            (
                item
                for item in (existing or {}).get("plugins", [])
                if isinstance(item, dict) and item.get("name") == name
            ),
            None,
        )
        if entry is None:
            continue
        retiring.append(_plugin_relative_path(entry))

    # Everything below this line is mutation, and nothing below it can refuse.
    for relative, source_tree in planned:
        target = marketplace / relative
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_tree, target)

    for relative in retiring:
        retired = marketplace / relative
        if retired.is_dir():
            shutil.rmtree(retired)

    published_index_path.parent.mkdir(parents=True, exist_ok=True)
    published_index_path.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
        encoding=_UTF_8,
    )
    return tuple(sorted(str(entry["name"]) for entry in declared))


def assert_supersession_complete(*, marketplace: Path, cohort: Path) -> None:
    """Refuse while a retired identity, or its metadata, is still live.

    Fail-closed and re-run on every release, not only the one that retires the
    name. Supersession that is merely *performed* can be undone by a replay, a
    stale manifest, or a stranger claiming the abandoned name; supersession that
    is *verified* stays true. This is the difference between a state and an
    invariant.

    Account metadata is checked with the entries because the identity flip is
    one event: a marketplace whose plugin list says the new name while its
    description still advertises the old one is half-renamed, and a reader
    cannot tell which half is authoritative.
    """
    cohort_index = _read_index(cohort / _INDEX_RELATIVE)
    retired = superseded_names(cohort_index)
    if not retired:
        return

    published_index_path = marketplace / _INDEX_RELATIVE
    if not published_index_path.is_file():
        return
    published = _read_index(published_index_path)

    live = sorted(
        str(entry["name"])
        for entry in published.get("plugins", [])
        if isinstance(entry, dict) and entry.get("name") in retired
    )
    if live:
        raise MarketplacePublishError(
            f"retired plugin identity {live} is still live in the marketplace index; "
            "two identities for one product must never both be published",
        )

    surviving_trees = sorted(name for name in retired if (marketplace / "plugins" / name).is_dir())
    if surviving_trees:
        raise MarketplacePublishError(
            f"retired plugin tree(s) {surviving_trees} remain on disk without an index entry; "
            "an unreferenced tree is still fetchable and still advertises the old identity",
        )

    stale_metadata = sorted(
        field for field in ("description",) if any(name in str(published.get(field, "")).lower() for name in retired)
    )
    owner = published.get("owner")
    if isinstance(owner, dict) and any(name in str(owner.get("name", "")).lower() for name in retired):
        stale_metadata.append("owner.name")
    if stale_metadata:
        raise MarketplacePublishError(
            f"marketplace {sorted(stale_metadata)} still names the retired identity; "
            "the rename is one event, so metadata and entries retire together",
        )


def main(argv: list[str] | None = None) -> int:
    """Publish a cohort's plugin trees into a marketplace checkout, refusing instructively."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marketplace", required=True, type=Path, help="checkout of the marketplace repository")
    parser.add_argument("--cohort", required=True, type=Path, help="unpacked marketplace tree from the release cohort")
    parser.add_argument(
        "--verify-supersession",
        action="store_true",
        help="check only that no retired identity survives, publishing nothing",
    )
    args = parser.parse_args(argv)
    if args.verify_supersession:
        try:
            assert_supersession_complete(marketplace=args.marketplace, cohort=args.cohort)
        except MarketplacePublishError as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 1
        print("no retired plugin identity survives in the marketplace")
        return 0
    try:
        published = publish_cohort_plugins(marketplace=args.marketplace, cohort=args.cohort)
    except MarketplacePublishError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    print(f"published plugins: {', '.join(published)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
