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

Both operations are idempotent: publishing the same cohort twice leaves the tree
byte-identical, so the caller's "nothing staged, nothing to push" check is the
one that decides whether a commit happens.
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
    """
    declared = _declared_plugins(cohort_index, source=Path("cohort"))
    owned = {entry["name"] for entry in declared}
    published = (existing_index or {}).get("plugins", [])
    retained = [entry for entry in published if isinstance(entry, dict) and entry.get("name") not in owned]
    document = dict(cohort_index)
    document["plugins"] = sorted([*declared, *retained], key=lambda entry: str(entry["name"]))
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

    for entry in declared:
        relative = _plugin_relative_path(entry)
        source_tree = cohort / relative
        if not source_tree.is_dir():
            raise MarketplacePublishError(f"cohort plugin {entry['name']!r} has no tree at {source_tree}")
        target = marketplace / relative
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_tree, target)

    published_index_path = marketplace / _INDEX_RELATIVE
    existing = _read_index(published_index_path) if published_index_path.is_file() else None
    merged = merge_marketplace_index(cohort_index=cohort_index, existing_index=existing)
    published_index_path.parent.mkdir(parents=True, exist_ok=True)
    published_index_path.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
        encoding=_UTF_8,
    )
    return tuple(sorted(str(entry["name"]) for entry in declared))


def main(argv: list[str] | None = None) -> int:
    """Publish a cohort's plugin trees into a marketplace checkout, refusing instructively."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marketplace", required=True, type=Path, help="checkout of the marketplace repository")
    parser.add_argument("--cohort", required=True, type=Path, help="unpacked marketplace tree from the release cohort")
    args = parser.parse_args(argv)
    try:
        published = publish_cohort_plugins(marketplace=args.marketplace, cohort=args.cohort)
    except MarketplacePublishError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    print(f"published plugins: {', '.join(published)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
