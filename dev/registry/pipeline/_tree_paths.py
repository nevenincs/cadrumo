"""Path guards the generated-tree pipeline applies before it reads or writes.

Two checks, each duplicated between sibling pipeline modules before this module
existed: the check path and the validation path both refused a link-like or
missing location, and the check path and the publication path both asked whether
one location sits inside another. Duplicated guards are worse than duplicated
computation. A drifting sum is a wrong number; a drifting guard means one route
into the tree refuses a symlink and another does not, and the route that does
not is the one an attacker or an accident reaches through.

They stay private to this package. The shipped `link_safety` module owns the
question of what a link IS, and these compose it into the two refusals this
pipeline makes; a dev-side guard does not belong in the product's core.
"""

from __future__ import annotations

from pathlib import Path

from cadrumo.core.link_safety import is_link_like
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

__all__ = ["contains", "require_existing_non_link"]


def require_existing_non_link(path: Path, *, subject: str) -> None:
    """Refuse a link-like or absent ``path``, naming ``subject`` in the refusal."""
    if is_link_like(path):
        raise RegistryValidationError(f"{subject} must not be a link: {path}")
    if not path.exists():
        raise RegistryValidationError(f"{subject} is missing: {path}")


def contains(parent: Path, child: Path) -> bool:
    """Return whether ``child`` sits inside ``parent``."""
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True
