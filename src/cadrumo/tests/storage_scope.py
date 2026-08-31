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

Three forms, by where the location is needed:

- :func:`storage_overrides` -- kwargs to splat into
  :func:`~core.config.override_settings`. The common case.
- :func:`storage_env_overrides` -- the same thing keyed by environment
  variable, for a test handing an environment to a subprocess.
- :func:`relocated_storage_path` -- one resolved path, for when the location
  is wanted before the ``Settings`` exists or after it goes out of scope.

Hand the kwargs to :func:`~core.config.override_settings`, never to the
``Settings`` constructor. ``Settings(**mapping)`` type-checks as a splat onto
pydantic-settings' own ``_env_file``-style parameters and buries the call in
hundreds of diagnostics; the context manager takes ``**overrides: object`` and
stays clean. Measured at 414 diagnostics on one file before the switch.

Three shapes look like they want these helpers and do not. Each was found by
reading a real site, and re-pointing any of them removes something:

- **A propagated value.** ``store = other_settings.cadrumo_secret_store_dir``
  passed back as ``cadrumo_secret_store_dir=store`` names the field but writes
  no literal: the test is deliberately reusing a location it did not choose,
  and relocating it breaks the reuse.
- **An asserted string.** ``assert "CADRUMO_SECRET_STORE_DIR" in help_text``
  checks that a surface *documents* the variable. The literal is the subject.
- **Synthetic fixture data.** A field name or leaf appearing inside a recorded
  argument or a golden payload resolves nothing.

A fourth case is a deliberate exception rather than a false positive: a test
whose subject is an operator collapsing two members onto ONE directory cannot
use these at all, because the declared subpaths are distinct by construction.
Spell those literals out and say why, or the test silently stops exercising
the aliasing it exists for.

See Also:
    :func:`~core.storage_path`
        Resolver for where a category actually lives, override included.
    :func:`~core.config.override_settings`
        The context manager these overrides are handed to.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.errors.hierarchy import CoreValidationError
from ..core.storage_taxonomy import StorageCategory, StorageOverridePolicy, StorageScope
from ..core.storage_taxonomy_locations import STORAGE_TAXONOMY

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["relocated_storage_path", "storage_env_overrides", "storage_overrides"]


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


def relocated_storage_path(anchor: Path, category: StorageCategory) -> Path:
    """Return where :func:`storage_overrides` puts ``category`` under ``anchor``.

    For the common shape where a test needs the location as well as the
    override -- it seeds files there before entering the block, or asserts on
    it after leaving. Resolving through :func:`~core.storage_path` covers
    neither: it needs a ``Settings`` the test has not built yet, or one that
    has already gone out of scope.

    Both this and :func:`storage_overrides` read the one declaration, so a
    caller using them together cannot end up with a path and an override that
    disagree.

    Args:
        anchor: Directory to relocate beneath, ordinarily a test's ``tmp_path``.
        category: A root-scoped, operator-overridable member.

    Returns:
        The absolute path the matching override would put ``category`` at.

    Raises:
        CoreValidationError: For anything :func:`storage_overrides` refuses.
    """
    return next(iter(storage_overrides(anchor, category).values()))


def storage_env_overrides(anchor: Path, *categories: StorageCategory) -> dict[str, str]:
    """Return the environment-variable form of :func:`storage_overrides`.

    For a test that hands an environment to a subprocess rather than entering
    an :func:`~core.config.override_settings` block. Same guarantee: neither
    the variable name nor the leaf directory is written at the call site.

    The name comes from :meth:`~core.config.Settings.env_var_names`, not from
    uppercasing the field and hoping. A field whose environment source has
    been severed is still a field, so uppercasing it yields a plausible
    variable that reaches nothing -- the subprocess would silently run against
    the real location. That case is refused here instead.

    Args:
        anchor: Directory to relocate beneath, ordinarily a test's ``tmp_path``.
        categories: Root-scoped, operator-overridable members to relocate.

    Returns:
        Environment variable names mapped to stringified paths, ready to merge
        into a subprocess environment.

    Raises:
        CoreValidationError: For anything :func:`storage_overrides` refuses, or
            when a member's field is not reachable from the environment.
    """
    from ..core.config import Settings

    reachable = Settings.env_var_names()
    environment: dict[str, str] = {}
    for field, path in storage_overrides(anchor, *categories).items():
        name = field.upper()
        if name not in reachable:
            raise CoreValidationError(
                f"settings field {field!r} is not reachable from the environment, so setting "
                f"{name!r} would relocate nothing; override it through Settings instead.",
            )
        environment[name] = str(path)
    return environment
