"""Name the variable the developer's key for a provider is read from: the one the repository declares.

The agent names its providers for their products (``claude``, ``codex``), while
the repository's environment template declares one key per vendor, under the
vendor's name (``CADRUMO_LLM_ANTHROPIC_API_KEY``). A provider lane's default
endpoint names its vendor, so the vendor's name is taken from that host and the
product's name is tried after it; a name counts only when the template declares
it, so no second spelling of a key is ever invented.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlsplit

_DECLARED = re.compile(r"^(CADRUMO_LLM_[A-Z0-9_]+_API_KEY)=", re.MULTILINE)


def declared_key_variables(template: Path) -> frozenset[str]:
    """The provider key variables the environment template declares."""
    text = template.read_text(encoding="utf-8")
    return frozenset(str(match.group(1)) for match in _DECLARED.finditer(text))


def _variable(name: str) -> str:
    return "CADRUMO_LLM_" + re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_") + "_API_KEY"


def candidate_key_variables(provider: str, default_base_url: str | None) -> list[str]:
    """The names to try for ``provider``'s key: its endpoint's vendor first, then the provider itself."""
    names: list[str] = []
    host = urlsplit(default_base_url or "").hostname or ""
    labels = [label for label in host.split(".") if label]
    if len(labels) >= 2:
        names.append(_variable(labels[-2]))
    names.append(_variable(provider))
    return list(dict.fromkeys(names))


def provider_key_variable(provider: str, default_base_url: str | None, declared: Iterable[str]) -> str | None:
    """The declared variable that holds ``provider``'s key, or ``None`` when the template declares none."""
    known = frozenset(declared)
    return next((name for name in candidate_key_variables(provider, default_base_url) if name in known), None)
