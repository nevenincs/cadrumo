"""Keep the build host's locations out of the shipped package manifest.

A package is built from a source checkout and an agent project that live wherever the
builder keeps them, with tools that often sit under the builder's own home directory.
The manifest records which inputs and tools built the package, but a shipped file must
not name those locations: an absolute path inside the checkout is recorded relative to
it, a path inside the builder's home directory is recorded relative to ``~`` so it names
no account, and the agent project's own location is not recorded at all.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

HOME_PREFIX = "~"
"""Stands for the builder's home directory in a shipped path."""


def _relative_text(text: str, base: Path, prefix: str = "") -> str:
    for flavour in (PureWindowsPath, PurePosixPath):
        candidate = flavour(text)
        if candidate.is_absolute():
            try:
                relative = candidate.relative_to(flavour(base)).as_posix()
            except ValueError:
                continue
            return f"{prefix}/{relative}" if prefix else relative
    return text


def _rewritten(value: Any, base: Path, prefix: str) -> Any:
    if isinstance(value, str):
        return _relative_text(value, base, prefix)
    if isinstance(value, Mapping):
        return {key: _rewritten(item, base, prefix) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, bytes):
        return [_rewritten(item, base, prefix) for item in value]
    return value


def checkout_relative(value: Any, checkout: Path) -> Any:
    """Rewrite every absolute path inside ``checkout`` found in ``value`` as a relative POSIX path."""
    return _rewritten(value, checkout, "")


def host_independent(value: Any, checkout: Path, home: Path | None = None) -> Any:
    """Rewrite ``value`` so it names neither the checkout nor the builder's home directory.

    A path inside the checkout becomes checkout-relative; any other path inside ``home``
    (the running account's home directory when not given) becomes ``~/<relative>``.
    """
    home = home if home is not None else Path.home()
    return _rewritten(checkout_relative(value, checkout), home, HOME_PREFIX)


def without_source(agent: Mapping[str, object]) -> dict[str, object]:
    """The bundled agent's record without the location of the project it was built from."""
    return {key: value for key, value in agent.items() if key != "source"}


def shipped_provenance(
    provenance: Mapping[str, object] | None, checkout: Path, home: Path | None = None
) -> dict[str, Any]:
    """The build provenance as the package manifest records it."""
    shipped: dict[str, Any] = host_independent(dict(provenance or {}), checkout, home)
    agent = shipped.get("agent")
    if isinstance(agent, dict):
        shipped["agent"] = without_source(agent)
    return shipped
