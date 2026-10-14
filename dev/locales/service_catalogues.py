"""Transfer service-owned catalogues through the canonical guarded locale writer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dev._paths import REPO_ROOT

from ._paths import LOCALES_DIR
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
            service: dict[str, Any] = _parse_locale(destination_guard.read_text(target)) if target.exists() else {}
            if not target.exists():
                destination_guard.observe(target)
            for shard in sorted((source / locale).rglob("*.yml")):
                document = _parse_locale(source_guard.read_text(shard))
                changed = False
                for namespace, family in SERVICE_FAMILIES:
                    children = document.get(namespace)
                    if not isinstance(children, dict) or family not in children:
                        continue
                    value = children.pop(family)
                    siblings = service.setdefault(namespace, {})
                    if family in siblings and siblings[family] != value:
                        raise ValueError(f"Conflicting service catalogue: {locale}:{namespace}.{family}")
                    siblings[family] = value
                    changed = True
                for key in SERVICE_KEYS:
                    namespace, section, leaf = key.split(".")
                    group = document.get(namespace)
                    children = group.get(section) if isinstance(group, dict) else None
                    if not isinstance(children, dict) or leaf not in children:
                        continue
                    value = children.pop(leaf)
                    siblings = service.setdefault(namespace, {}).setdefault(section, {})
                    if leaf in siblings and siblings[leaf] != value:
                        raise ValueError(f"Conflicting service catalogue: {locale}:{key}")
                    siblings[leaf] = value
                    changed = True
                if changed:
                    _rewrite_locale_mapping(source_guard, shard, document)
            _rewrite_locale_mapping(destination_guard, target, service)


if __name__ == "__main__":
    transfer_service_catalogues()
