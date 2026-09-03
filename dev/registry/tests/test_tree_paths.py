"""The two path refusals the generated-tree pipeline makes before it touches a location.

Both were duplicated between sibling pipeline modules until they were given one
home. A duplicated guard is worse than a duplicated calculation: a drifting sum
is a wrong number, while a drifting guard leaves one route into the tree
refusing a link and another accepting it, and the accepting route is the one an
accident arrives through. That is the reason these are worth proving rather than
reading.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..pipeline._tree_paths import contains, require_existing_non_link

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_a_real_directory_passes(tmp_path: Path) -> None:
    """The permitting case, so the refusals below are not vacuous."""
    require_existing_non_link(tmp_path, subject="export root")


def test_a_missing_path_is_refused_by_name(tmp_path: Path) -> None:
    """Absence is refused, and the refusal names what was missing.

    The subject is in the message because these guards run over several
    locations in one publication, and "is missing" without a subject leaves the
    reader to guess which.
    """
    with pytest.raises(RegistryValidationError, match="export root is missing"):
        require_existing_non_link(tmp_path / "absent", subject="export root")


def test_a_symlink_is_refused_even_though_it_exists(tmp_path: Path) -> None:
    """The branch that matters: a link resolves, so existence alone admits it.

    A guard checking only `exists()` would accept a link pointing anywhere,
    which is how a publication writes outside the tree it believes it is in.
    The order is load-bearing too - the link check runs first, so a link is
    refused as a link rather than reported as present.
    """
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)

    with pytest.raises(RegistryValidationError, match="export root must not be a link"):
        require_existing_non_link(link, subject="export root")


def test_containment_answers_both_ways(tmp_path: Path) -> None:
    """Inside is true, outside is false, and a sibling is not inside."""
    parent = tmp_path / "parent"
    child = parent / "revisions" / "2025"
    sibling = tmp_path / "elsewhere"

    assert contains(parent, child)
    assert contains(parent, parent)
    assert not contains(parent, sibling)
    assert not contains(child, parent), "a parent is not inside its own child"
