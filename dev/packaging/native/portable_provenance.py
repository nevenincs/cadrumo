"""Keep the build host's locations out of the shipped package manifest.

A package is built from a source checkout and an agent project that live wherever the
builder keeps them. The manifest records which inputs and tools built the package, but a
shipped file must not name those locations, so an absolute path inside the checkout is
recorded relative to it and the agent project's own location is not recorded at all.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


def _relative_text(text: str, checkout: Path) -> str:
    for flavour in (PureWindowsPath, PurePosixPath):
        candidate = flavour(text)
        if candidate.is_absolute():
            try:
                return candidate.relative_to(flavour(checkout)).as_posix()
            except ValueError:
                continue
    return text


def checkout_relative(value: Any, checkout: Path) -> Any:
    """Rewrite every absolute path inside ``checkout`` found in ``value`` as a relative POSIX path."""
    if isinstance(value, str):
        return _relative_text(value, checkout)
    if isinstance(value, Mapping):
        return {key: checkout_relative(item, checkout) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, bytes):
        return [checkout_relative(item, checkout) for item in value]
    return value


def without_source(agent: Mapping[str, object]) -> dict[str, object]:
    """The bundled agent's record without the location of the project it was built from."""
    return {key: value for key, value in agent.items() if key != "source"}


def shipped_provenance(provenance: Mapping[str, object] | None, checkout: Path) -> dict[str, Any]:
    """The build provenance as the package manifest records it."""
    shipped: dict[str, Any] = checkout_relative(dict(provenance or {}), checkout)
    agent = shipped.get("agent")
    if isinstance(agent, dict):
        shipped["agent"] = without_source(agent)
    return shipped
