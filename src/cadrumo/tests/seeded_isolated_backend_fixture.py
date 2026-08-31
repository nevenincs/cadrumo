"""Seed a world once per file, then hand each test its own copy.

The sibling :func:`~cadrumo.tests.active_profile_isolated_backend_fixture.active_profile_isolated_backend_fixture`
gives every test a freshly seeded world. Where the seeding is expensive -- a
ledger corpus import runs a full CLI invocation per file and an encrypted write
per row -- a suite of ten tests pays that ten times to reach a starting state
every one of them shares.

Module scope is the obvious fix and the wrong one for most of these suites:
they classify, split, merge and remove, so a shared world lets one test's
mutation reach the next. This factory keeps the isolation exactly as it is --
every test still gets its own storage root, and no mutation can escape it --
and removes only the repetition, by seeding once and giving each test a
filesystem copy.

Measured on the four-CSV ledger corpus (514 rows): seeding costs 5.97s per
test, copying costs 1.61s, both including the same world-open and read. The
copy itself is 0.04s; the remainder is opening the world, which the per-test
fixture already pays today.

The copy takes the whole ``tmp_path``, not just the bucket tree: the secret
substrate is a SIBLING of the storage root (the production custody split), so
copying only ``cadrumo-storage`` would leave the keys behind. It is taken after
the origin's context has exited, so the bytes on disk are what a reopen
actually faces -- session keys reaped, engine disposed.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, nullcontext
from pathlib import Path

import pytest

from ..adapters.persistence.storage.sql.engine import dispose_engine
from ..core.config import override_settings
from .active_profile_isolated_backend_fixture import DEFAULT_BUCKET_ID
from .profile_capsule import open_test_profile_session
from .secure_sql import isolated_profile_storage_root
from .user_profile import register_minimal_profile

__all__ = ["seeded_isolated_backend_fixture"]


def seeded_isolated_backend_fixture(
    *,
    seed: Callable[[], None],
    bucket_id: str = DEFAULT_BUCKET_ID,
    autouse: bool = True,
    name: str = "_isolated_backend",
    origin_name: str = "_isolated_backend_origin",
    settings_overrides: Mapping[str, object] | None = None,
    profile_overrides: Mapping[str, str] | None = None,
    display_name: str | None = None,
) -> tuple[Callable[..., Iterator[Path]], Callable[..., Iterator[None]]]:
    """Build the (origin, per-test) fixture pair for a seed-once suite.

    ``seed`` runs once per module, inside the opened world, after the profile
    is registered. It receives nothing and returns nothing: anything a test
    needs from the seeded state it must read back from the world, because the
    seeding no longer happens in the test's own process context.

    Returns both fixtures because pytest resolves fixtures by module-level
    name; the consuming module binds both::

        _seeded_origin, live_fx_seeded_backend = seeded_isolated_backend_fixture(seed=_import_corpus)
        __all__ = ["_seeded_origin", "live_fx_seeded_backend"]

    ``name`` and ``origin_name`` are the two pytest fixture names this returns,
    and they are stated rather than derived one from the other. A module using
    this factory twice must give BOTH a distinct value, or the second origin
    silently shadows the first -- which is the hazard the derivation was
    guarding, now visible in the signature instead of implied by it.

    Derivation also made the effective name unstateable to the static fixture
    census: it defers a bare parameter, because the call site supplies that,
    but ``f"{name}_origin"`` is neither a literal nor a parameter, so the
    ownership manifest could not name a fixture pytest really registers.
    """

    @contextmanager
    def _open_world(root: Path) -> Iterator[None]:
        dispose_engine()
        overrides = override_settings(**settings_overrides) if settings_overrides else nullcontext()
        with (
            overrides,
            isolated_profile_storage_root(tmp_path=root),
            open_test_profile_session(bucket_id),
        ):
            try:
                yield
            finally:
                dispose_engine()

    @pytest.fixture(name=origin_name, scope="module")
    def _seeded_origin(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
        root = tmp_path_factory.mktemp("seeded-origin")
        with _open_world(root):
            register_minimal_profile(
                profile_id=bucket_id,
                display_name=display_name,
                overrides=profile_overrides,
            )
            seed()
        # Yielded with the world CLOSED, so every copy is taken from settled
        # bytes rather than from a root with a live engine attached to it.
        yield root

    @pytest.fixture(name=name, autouse=autouse)
    def _copied_backend(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[None]:
        origin = request.getfixturevalue(origin_name)
        assert isinstance(origin, Path)
        clone = tmp_path / "seeded-world"
        shutil.copytree(origin, clone)
        with _open_world(clone):
            yield

    return _seeded_origin, _copied_backend
