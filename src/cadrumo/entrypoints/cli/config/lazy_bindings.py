"""Import-light handler binding for configuration command specifications."""

from collections.abc import Mapping

from cadrumo_client.commands.shared_contracts import DeferredTarget, LazyBinding


def lazy_handler(table: Mapping[str, str], module: str, name: str) -> LazyBinding:
    """Bind a handler relative to the configuration command package."""
    return LazyBinding.available(DeferredTarget(table[module], name, __package__))
