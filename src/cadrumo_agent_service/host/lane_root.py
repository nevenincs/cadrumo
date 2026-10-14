"""The mark that admits a storage root to the development agent lane.

The lane runs only on a root that was created empty for it and marked. The mark
is one JSON file at the root, ``.cadrumo-agent-lane.json``::

    {"schema": 1, "kind": "cadrumo.agent_development_lane", "root": "<canonical root>"}

It names the canonical path of the root it was written into, so a mark copied
into another root does not admit it. The per-user installed default root is
never admitted, marked or not.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cadrumo.core.storage_environment import host_installed_default_root

LANE_MARK_NAME: Final = ".cadrumo-agent-lane.json"
LANE_MARK_KIND: Final = "cadrumo.agent_development_lane"


class _LaneMark(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    version: int = Field(alias="schema")
    kind: str
    root: str


def _canonical(path: Path) -> Path:
    return Path(os.path.normcase(path.resolve(strict=True)))


def write_lane_mark(root: Path) -> Path:
    """Mark an existing, empty storage root for the development agent lane and return the mark's path.

    A root that already holds anything is refused, so an in-use profile store
    can never be turned into a lane root.
    """
    canonical = _canonical(root)
    if any(canonical.iterdir()):
        raise ValueError("a lane root must be empty when it is marked")
    if canonical == _canonical_default_root():
        raise ValueError("the per-user default root is never a lane root")
    mark = canonical / LANE_MARK_NAME
    document = {"schema": 1, "kind": LANE_MARK_KIND, "root": str(canonical)}
    with mark.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(document, sort_keys=True))
    return mark


def is_marked_lane_root(root: Path) -> bool:
    """Whether ``root`` carries a mark written for exactly this root and is not the per-user default."""
    try:
        canonical = _canonical(root)
        if canonical == _canonical_default_root():
            return False
        mark = _LaneMark.model_validate_json((canonical / LANE_MARK_NAME).read_bytes())
    except (OSError, ValueError, ValidationError):
        return False
    return mark.version == 1 and mark.kind == LANE_MARK_KIND and Path(os.path.normcase(mark.root)) == canonical


def _canonical_default_root() -> Path | None:
    try:
        return _canonical(host_installed_default_root(os.environ))
    except (OSError, ValueError):
        return None
