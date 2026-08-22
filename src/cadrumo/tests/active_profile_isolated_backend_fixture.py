"""Canonical isolated-storage-plus-active-profile fixture for test suites.

Seeded through a detached ``WorkflowState``, never a repository read: the
capsule publishes by an atomic no-replace rename onto ``buckets/<profile-id>``,
which a workflow-state repository construction would otherwise materialise
first and collide with.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import nullcontext
from pathlib import Path

import pytest

from ..adapters.persistence.storage import dispose_engine
from ..core.config import override_settings
from .profile_capsule import open_test_profile_session
from .secure_sql import isolated_profile_storage_root
from .user_profile import register_minimal_profile

#: The bucket id most callers of this fixture share.
DEFAULT_BUCKET_ID = "11111111-1111-4111-8111-111111111111"


def _seeded_world(
    *,
    bucket_id: str,
    dispose_engine_around: bool,
    settings_overrides: Mapping[str, object] | Callable[[Path], Mapping[str, object]] | None,
    profile_overrides: Mapping[str, str] | None,
    display_name: str | None,
) -> Callable[[Path], Iterator[None]]:
    """Return the seeding body both fixture factories drive.

    Hoisted out of the factories rather than closed over inside one, so the
    function-scoped and module-scoped variants can be separate factories -- each
    with exactly ONE nested fixture -- while still sharing this body verbatim.
    Splitting the factories without sharing this would have duplicated the world
    setup, which is the thing that must not diverge between the two scopes.
    """

    def _seeded(root: Path) -> Iterator[None]:
        if dispose_engine_around:
            dispose_engine()
        resolved_overrides = settings_overrides(root) if callable(settings_overrides) else settings_overrides
        settings_cm = override_settings(**resolved_overrides) if resolved_overrides else nullcontext()
        with (
            settings_cm,
            isolated_profile_storage_root(tmp_path=root),
            open_test_profile_session(bucket_id),
        ):
            if dispose_engine_around:
                try:
                    register_minimal_profile(
                        profile_id=bucket_id,
                        display_name=display_name,
                        overrides=profile_overrides,
                    )
                    yield
                finally:
                    dispose_engine()
            else:
                register_minimal_profile(
                    profile_id=bucket_id,
                    display_name=display_name,
                    overrides=profile_overrides,
                )
                yield

    return _seeded


def active_profile_isolated_backend_fixture(
    *,
    bucket_id: str = DEFAULT_BUCKET_ID,
    autouse: bool = True,
    name: str = "_isolated_backend",
    dispose_engine_around: bool = False,
    settings_overrides: Mapping[str, object] | Callable[[Path], Mapping[str, object]] | None = None,
    profile_overrides: Mapping[str, str] | None = None,
    display_name: str | None = None,
) -> Callable[..., Iterator[None]]:
    """Build a fixture isolating storage and opening a seeded profile session.

    The same body was written independently at several sites -- some autouse,
    some explicitly requested, most sharing the default bucket id but at
    least one pinned to its own -- so ``bucket_id``, ``autouse`` and ``name``
    stay per-caller while only the body is shared.

    ``dispose_engine_around`` is a second independently-varying axis found at
    another cluster of sites: they need the SQL engine disposed both before
    the isolated storage root opens (so a prior test's connection cannot leak
    into it) and in a ``finally`` after the yield (so this test's connection
    cannot leak into the next). Default ``False`` preserves every existing
    caller's behaviour unchanged.

    ``settings_overrides`` is a third axis: some sites additionally pin a
    Settings field ``isolated_profile_storage_root`` does not itself set (most
    commonly ``cadrumo_output_language``, also ``cadrumo_live_state_dir``).
    Applied via :func:`~cadrumo.core.config.override_settings` OUTSIDE (before)
    ``isolated_profile_storage_root`` in the with-tuple, matching the majority
    of the sites this replaces -- ``isolated_profile_storage_root`` layers its
    own ``cadrumo_local_storage_root`` override on top without disturbing
    fields the caller already set, so the two compose regardless of which
    field each touches. Default ``None`` preserves every existing caller's
    behaviour unchanged. Pass a callable (``lambda tmp_path: {...}``) instead
    of a plain mapping when an override value must derive from the per-test
    ``tmp_path`` (e.g. ``cadrumo_live_state_dir=tmp_path / "probe-live-state"``),
    since a plain mapping is captured once at fixture-construction time.

    ``profile_overrides`` is a fourth axis: a small number of sites need a
    non-default profile fact (e.g. ``identity.tax_id``) stamped on the seeded
    profile, passed straight through to
    :func:`~cadrumo.tests.user_profile.register_minimal_profile`. Default
    ``None`` preserves every existing caller's behaviour unchanged.

    ``display_name`` is a fifth axis, also a straight passthrough to
    :func:`~cadrumo.tests.user_profile.register_minimal_profile`. Default
    ``None`` preserves every existing caller's behaviour unchanged.

    A module-scoped variant lives in
    :func:`module_scoped_profile_isolated_backend_fixture` rather than behind a
    ``scope`` argument here. One factory returning a different nested fixture
    per argument cannot be resolved by the static fixture census, and that
    refusal blocked the ownership manifest's verification AND its
    regeneration.

    """

    seeded = _seeded_world(
        bucket_id=bucket_id,
        dispose_engine_around=dispose_engine_around,
        settings_overrides=settings_overrides,
        profile_overrides=profile_overrides,
        display_name=display_name,
    )

    @pytest.fixture(name=name, autouse=autouse)
    def _active_profile_isolated_backend(tmp_path: Path) -> Iterator[None]:
        yield from seeded(tmp_path)

    return _active_profile_isolated_backend


def module_scoped_profile_isolated_backend_fixture(
    *,
    bucket_id: str = DEFAULT_BUCKET_ID,
    autouse: bool = True,
    name: str = "_isolated_backend",
    dispose_engine_around: bool = False,
    settings_overrides: Mapping[str, object] | Callable[[Path], Mapping[str, object]] | None = None,
    profile_overrides: Mapping[str, str] | None = None,
    display_name: str | None = None,
) -> Callable[..., Iterator[None]]:
    """The same seeded world as the sibling above, built once per MODULE.

    A separate factory rather than a ``scope`` argument on one. Selecting the
    scope inside a single factory meant it returned a DIFFERENT nested fixture
    per call, and the decorator a binding inherits was therefore chosen at the
    call site -- which the static fixture census cannot resolve. It refused,
    and that refusal blocked BOTH the ownership manifest's verification and its
    regeneration, so the committed manifest drifted with nothing able to report
    it. One factory, one closure, one resolvable answer.

    Opting in is a claim about the suite, not a speed knob: one mutating test
    in a module-scoped file leaks into every test after it. Only use this where
    the whole file reads, and hoist shared seeding into a fixture of the same
    scope. A module-scoped fixture cannot depend on the function-scoped
    ``tmp_path``, so this variant draws its root from ``tmp_path_factory``.
    """
    seeded = _seeded_world(
        bucket_id=bucket_id,
        dispose_engine_around=dispose_engine_around,
        settings_overrides=settings_overrides,
        profile_overrides=profile_overrides,
        display_name=display_name,
    )

    @pytest.fixture(name=name, autouse=autouse, scope="module")
    def _module_scoped_backend(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
        yield from seeded(tmp_path_factory.mktemp(name.lstrip("_")))

    return _module_scoped_backend


__all__ = [
    "DEFAULT_BUCKET_ID",
    "active_profile_isolated_backend_fixture",
    "module_scoped_profile_isolated_backend_fixture",
]
