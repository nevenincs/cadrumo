"""Relocate declared storage categories under a test's own scratch anchor.

A test that needs one storage category somewhere harmless has, until now, had
to name two things the taxonomy already owns: the settings field that carries
the location, and the leaf directory name. Both restated by hand, at every
call site, with nothing checking either. The cost is measurable rather than
theoretical -- ``isolated_cli_runtime_profile`` pinned
``cadrumo_financial_txs_dir`` to a directory it called ``txs`` while the
declared subpath for that category is ``financial/transactions``, and no gate
noticed, because a test that only round-trips its own override is consistent
with any name at all.

This module closes both restatements. A caller names the *category* and the
anchor to put it under; the settings field and the subpath are read from
:data:`~core.STORAGE_TAXONOMY`. A category renamed at the declaration moves
every isolation site with it, and a call site can no longer disagree with the
taxonomy about where a category lives, because it no longer says.

The anchor is a caller-supplied scratch directory, deliberately not the storage
root: the fixtures that keep a category *outside* the root they isolate -- the
secret substrate is the standing case, sibling rather than nested, matching
production custody -- need to express that separation, and an accessor bound to
the root cannot. Relocating a category the operator may not override is refused
rather than silently honoured, so a test cannot pin a layout production
guarantees is fixed.

See Also:
    :func:`~core.storage_path`
        Resolver for where a category actually lives, override included.
    :func:`~core.config.override_settings`
        The context manager these overrides are handed to.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core import STORAGE_TAXONOMY, StorageCategory, StorageOverridePolicy, StorageScope
from ..core.errors import CoreValidationError

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["storage_overrides"]


def storage_overrides(anchor: Path, *categories: StorageCategory) -> dict[str, Path]:
    """Return :func:`override_settings` kwargs putting each category under ``anchor``.

    Each category contributes one entry: its declared settings field mapped to
    ``anchor`` joined with its declared subpath. Neither the field name nor the
    subpath is written at the call site, so neither can drift from the
    declaration.

    Args:
        anchor: Directory to relocate beneath, ordinarily a test's ``tmp_path``.
            Nothing is created; the returned paths are values for settings.
        categories: Root-scoped, operator-overridable members to relocate.

    Returns:
        Settings field names mapped to their relocated paths, ready to splat
        into :func:`~core.config.override_settings`.

    Raises:
        CoreValidationError: When no category is given, when one is not
            root-scoped, when one declares no settings field, or when one is
            declared fixed layout and so cannot be relocated at all.
    """
    if not categories:
        raise CoreValidationError(
            "storage_overrides needs at least one category; a call that relocates nothing "
            "is a call site that meant to name one and did not.",
        )

    overrides: dict[str, Path] = {}
    for category in categories:
        location = STORAGE_TAXONOMY[category]
        if location.scope is not StorageScope.ROOT:
            raise CoreValidationError(
                f"storage category {category.value!r} is {location.scope.value} and is "
                "provisioned per bucket by the bucket lifecycle, not by a settings override.",
            )
        if location.override_policy is StorageOverridePolicy.FIXED:
            raise CoreValidationError(
                f"storage category {category.value!r} is declared fixed layout and must not be "
                "relocated; isolate it by overriding the storage root instead.",
            )
        if location.settings_field is None:
            raise CoreValidationError(
                f"storage category {category.value!r} declares no settings field, so there is nothing to override.",
            )
        overrides[location.settings_field] = anchor / location.relative_path()
    return overrides
