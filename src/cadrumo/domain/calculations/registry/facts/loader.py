"""Strict TOML parsing for one-file-per-concept governed facts."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from .....core.directory_scan import scan_directory
from .....core.toml import freeze_toml, read_toml
from ..errors import RegistryLoadError
from .schema import GovernedFact

__all__ = ["load_governed_fact_file", "load_governed_facts"]


_FACT_FILENAME = re.compile(r"^[0-9]{4}-[a-z0-9]+(?:-[a-z0-9]+)*\.toml$")


def load_governed_fact_file(path: Path) -> GovernedFact:
    """Parse one numbered TOML fragment containing exactly one ``[fact]`` table.

    The numeric filename prefix is validated as review ordering metadata only;
    the parsed ``fact_id`` remains the sole semantic identity.

    Raises:
        RegistryLoadError: If the filename, TOML document, or governed-fact
            schema is invalid.
    """
    source_path = path.resolve()
    if _FACT_FILENAME.fullmatch(source_path.name) is None:
        raise RegistryLoadError(
            f"{source_path}: governed fact filename must match NNNN-<stable-slug>.toml",
        )
    data = freeze_toml(read_toml(source_path, error_factory=RegistryLoadError))
    if set(data) != {"fact"}:
        raise RegistryLoadError(f"{source_path}: governed fact file must declare exactly one [fact] table")
    table = data["fact"]
    if not isinstance(table, Mapping):
        raise RegistryLoadError(f"{source_path}: [fact] must be a table")
    try:
        return GovernedFact.model_validate(table)
    except ValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid governed fact: {exc}") from exc


def load_governed_facts(facts_dir: Path) -> tuple[GovernedFact, ...]:
    """Parse a facts directory in deterministic filename order.

    Duplicate semantic identities are refused even when their numbered
    filenames differ. An absent directory yields an empty tuple; directory
    ownership and provider enrollment are enforced by the authority layer.

    Raises:
        RegistryLoadError: If a fragment is invalid or repeats a ``fact_id``.
    """
    resolved = facts_dir.resolve()
    if not resolved.is_dir():
        return ()
    facts: list[GovernedFact] = []
    source_by_fact_id: dict[str, Path] = {}
    for path in scan_directory(resolved, pattern="*.toml"):
        fact = load_governed_fact_file(path)
        previous = source_by_fact_id.get(fact.fact_id)
        if previous is not None:
            raise RegistryLoadError(
                f"{path}: governed fact {fact.fact_id!r} is already declared by {previous}",
            )
        source_by_fact_id[fact.fact_id] = path
        facts.append(fact)
    return tuple(facts)
