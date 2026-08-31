"""A field's placeholder default must state the same subpath the taxonomy does.

Every root-derived settings field carries a relative default that the
derivation validator replaces with an absolute path under the storage root.
That makes the placeholder look inconsequential -- and it is, right up until
someone reads it. Two of them had already drifted (`llm-cache` against
`cache/llm-cache`, `status-cache` against `cache/status-cache`) and nothing
noticed, because the value that drifted is the one nothing consults.

It is still a second declaration of a subpath the taxonomy owns. Pinning it
means the duplicate cannot disagree, which is the most that can be said for a
duplicate that has to exist: pydantic requires a default, and deriving it from
the taxonomy would close an import cycle, since the taxonomy is typed against
Settings.
"""

from __future__ import annotations

import pytest

from ..storage_taxonomy import ROOT_DERIVED_STORAGE_FIELDS, STORAGE_FIELD_CATEGORIES, storage_location
from ..config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_every_root_derived_default_matches_its_declared_subpath() -> None:
    """The placeholder and the declaration name one location, not two."""
    assert ROOT_DERIVED_STORAGE_FIELDS, "the derived-field set must be non-empty, or this asserts nothing"

    disagreements: list[str] = []
    for field_name in ROOT_DERIVED_STORAGE_FIELDS:
        info = Settings.model_fields.get(field_name)
        if info is None or not hasattr(info.default, "as_posix"):
            continue
        declared = storage_location(STORAGE_FIELD_CATEGORIES[field_name]).subpath
        placeholder = info.default.as_posix()
        if placeholder != declared:
            disagreements.append(f"{field_name}: default={placeholder!r} taxonomy={declared!r}")

    assert not disagreements, "settings defaults disagreeing with the taxonomy:\n" + "\n".join(disagreements)


def test_the_comparison_reaches_real_defaults() -> None:
    """Positive control.

    The loop skips fields whose default is not a path, so a change that made
    every default non-path would empty it and leave the test green while
    comparing nothing.
    """
    compared = [
        field_name
        for field_name in ROOT_DERIVED_STORAGE_FIELDS
        if hasattr(getattr(Settings.model_fields.get(field_name), "default", None), "as_posix")
    ]
    assert len(compared) > 10, (
        f"only {len(compared)} defaults were path-valued; the parity test is comparing almost nothing"
    )
