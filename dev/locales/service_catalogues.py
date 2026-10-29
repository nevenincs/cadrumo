"""Transfer service-owned catalogues through the canonical guarded locale writer."""

from __future__ import annotations

from pathlib import Path

from dev._paths import REPO_ROOT

from ._paths import LOCALES_DIR
from .locale_nodes import LocaleNode
from .locale_yaml import _parse_locale, _rewrite_locale_mapping
from .write_guard import catalogue_write_guard

SERVICE_LOCALES_DIR = REPO_ROOT / "src/cadrumo_agent_service/locales"
SERVICE_FAMILIES = (("desktop", "agent"), ("desktop", "providers"), ("ui", "agent"), ("ui", "providers"))
SERVICE_KEYS = ("desktop.pane.agent", "desktop.pane.maximize_agent", "desktop.rail.agent")


def transfer_service_catalogues(source: Path = LOCALES_DIR, destination: Path = SERVICE_LOCALES_DIR) -> None:
    """Preserve every authored translation while moving its package ownership."""
    with catalogue_write_guard(source) as source_guard, catalogue_write_guard(destination) as destination_guard:
        for locale in ("en", "es", "ca", "hu"):
            target = destination / f"{locale}.yml"
            service: dict[str, LocaleNode] = (
                _parse_locale(destination_guard.read_text(target)) if target.exists() else {}
            )
            if not target.exists():
                destination_guard.observe(target)
            for shard in sorted((source / locale).rglob("*.yml")):
                document = _parse_locale(source_guard.read_text(shard))
                changed = _transfer_families(document, service, locale)
                changed = _transfer_keys(document, service, locale) or changed
                if changed:
                    _rewrite_locale_mapping(source_guard, shard, document)
            _rewrite_locale_mapping(destination_guard, target, service)


def _transfer_families(document: dict[str, LocaleNode], service: dict[str, LocaleNode], locale: str) -> bool:
    """Transfer the declared service copy while refusing conflicting translations."""
    changed = False
    for namespace, family in SERVICE_FAMILIES:
        children = document.get(namespace)
        if not isinstance(children, dict) or family not in children:
            continue
        value = children.pop(family)
        siblings = _catalogue_group(service, namespace)
        if family in siblings and siblings[family] != value:
            raise ValueError(f"Conflicting service catalogue: {locale}:{namespace}.{family}")
        siblings[family] = value
        changed = True
    return changed


def _transfer_keys(document: dict[str, LocaleNode], service: dict[str, LocaleNode], locale: str) -> bool:
    """Transfer the declared service copy while refusing conflicting translations."""
    changed = False
    for key in SERVICE_KEYS:
        namespace, section, leaf = key.split(".")
        group = document.get(namespace)
        children = group.get(section) if isinstance(group, dict) else None
        if not isinstance(children, dict) or leaf not in children:
            continue
        value = children.pop(leaf)
        siblings = _catalogue_group(_catalogue_group(service, namespace), section)
        if leaf in siblings and siblings[leaf] != value:
            raise ValueError(f"Conflicting service catalogue: {locale}:{key}")
        siblings[leaf] = value
        changed = True
    return changed


def _catalogue_group(document: dict[str, LocaleNode], name: str) -> dict[str, LocaleNode]:
    """Open a nested catalogue mapping without accepting a scalar as a namespace."""
    value = document.setdefault(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"Catalogue namespace is not a mapping: {name}")
    return value


if __name__ == "__main__":
    transfer_service_catalogues()
