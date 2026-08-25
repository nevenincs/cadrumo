"""Canonical empty-storage-root fixtures for profile-bootstrap test flows."""

from collections.abc import Callable, Iterator, Mapping
from contextlib import nullcontext
from pathlib import Path

import pytest

from ..adapters.persistence.storage import dispose_engine
from ..core.config import override_settings
from .profile_capsule import open_test_profile_session
from .secure_sql import isolated_profile_storage_root


@pytest.fixture(name="profile_storage_root")
def profile_storage_root_fixture(tmp_path: Path) -> Iterator[Path]:
    """Provide a real, empty per-bucket storage root with file-backed custody."""

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


def isolated_profile_storage_fixture(
    *,
    autouse: bool = True,
    name: str = "_isolated_storage",
    dispose_engine_around: bool = False,
    settings_overrides: Mapping[str, object] | Callable[[Path], Mapping[str, object]] | None = None,
) -> Callable[..., Iterator[None]]:
    """Build a bare isolation fixture that yields no value.

    A distinct contract from :func:`profile_storage_root_fixture` above: that
    sibling hands its caller the storage root path for further use, while
    this one exists purely for its side effect -- isolating the profile
    storage root -- and yields nothing. The same three-line body was written
    twice under two names for that reason, once autouse and once explicitly
    requested via ``usefixtures``; ``autouse`` and ``name`` stay per-caller so
    reach is still declared where it applies, only the body is shared.

    ``dispose_engine_around`` and ``settings_overrides`` mirror the identically-
    named parameters on
    :func:`~cadrumo.tests.active_profile_isolated_backend_fixture.active_profile_isolated_backend_fixture`:
    a small cluster of no-active-profile sites also needs the SQL engine
    disposed before the isolated root opens and in a ``finally`` after it
    closes, and/or an additional Settings field pinned. Both default to
    ``False``/``None`` and preserve every existing caller's behaviour
    unchanged. Pass a callable for a ``tmp_path``-derived override value.
    """

    @pytest.fixture(name=name, autouse=autouse)
    def _isolated_profile_storage(tmp_path: Path) -> Iterator[None]:
        if dispose_engine_around:
            dispose_engine()
        if settings_overrides is None:
            resolved_overrides: dict[str, object] = {}
        elif isinstance(settings_overrides, Mapping):
            resolved_overrides = dict(settings_overrides)
        else:
            resolved_overrides = dict(settings_overrides(tmp_path))
        settings_cm = override_settings(**resolved_overrides) if resolved_overrides else nullcontext()
        with settings_cm, isolated_profile_storage_root(tmp_path=tmp_path):
            if dispose_engine_around:
                try:
                    yield
                finally:
                    dispose_engine()
            else:
                yield

    return _isolated_profile_storage


def bucket_session_storage_fixture(
    bucket_id: str,
    *,
    autouse: bool = True,
    name: str = "_isolated_backend",
) -> Callable[..., Iterator[None]]:
    """Build an isolation fixture that also holds an active bucket session.

    A third contract beside the two above: this one opens an isolated storage
    root AND an active master-key session bound to ``bucket_id``, which is what
    a test needs when the code under test writes encrypted rows -- workflow
    state, certificate sources, credential selections -- rather than only
    reading. Without the session those writes cannot reach the profile bucket
    being created.

    ``bucket_id`` is required, never defaulted. Four suites wrote this body out
    for themselves and pair up by the bucket each closes over, so the value is
    the only thing distinguishing them and inventing a default would silently
    merge suites onto one master-key session.

    Args:
        bucket_id: The profile bucket this caller's session is bound to.
        autouse: Whether the fixture applies without being requested.
        name: The fixture name pytest discovers.

    Returns:
        A fixture function to bind at module level under ``name``.
    """

    @pytest.fixture(name=name, autouse=autouse)
    def _bucket_session_storage(tmp_path: Path) -> Iterator[None]:
        with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(bucket_id):
            yield

    return _bucket_session_storage


__all__ = [
    "bucket_session_storage_fixture",
    "isolated_profile_storage_fixture",
    "profile_storage_root_fixture",
]
