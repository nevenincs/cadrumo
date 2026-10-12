"""Isolated storage with one password-custodied profile whose runtime admits the test's commands.

Commands that read or write a profile submit registered operations to the
runtime. A test world whose profile cannot sign in is refused as runtime
unavailable before the behaviour under test, so these worlds register the
profile with genuine password custody and bind it to :func:`invoke_cached_cli`.
A command first runs as given, and the runtime is joined only when one is
refused for want of it: a command that never reaches the runtime prints what it
always printed, and a suite that serves its own exact profile from a native
worker binds that profile instead and never starts this one, so two runtimes
never contend for one runtime door in a test.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import ExitStack, contextmanager, nullcontext
from pathlib import Path
from typing import Unpack
from uuid import UUID

import pytest
from click.testing import Result

from ....adapters.persistence.profile.tests.profile_registration import register_cli_profile
from ....adapters.persistence.storage.bucket.directory_layout import bucket_paths
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....adapters.persistence.storage.runtime import inspect_storage_runtime
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_profile_storage_root
from ....application.user_profile.login_session import authenticate_profile_for_invocation
from ....application.workflow.profile_bucket_scan import read_profile_bucket_by_id
from ....core.config import load_settings, override_settings
from ....core.paths import effective_storage_root
from ....core.storage_taxonomy import StorageCategory
from ....core.storage_taxonomy_locations import storage_location
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....tests.storage_scope import storage_overrides
from .cli_runner import ClickInvokeKwargs, ProfileCliInvoker, bind_profile_cli, invoke_unbound_cli
from .portable_human_cli_runtime import PortableHumanCliRuntime, portable_human_cli_runtime
from .profile_password_cli import chooses_own_credential_source, refused_for_want_of_an_operator

__all__ = [
    "live_session_operator",
    "operator_profile_bound_to_cli",
    "runtime_cli_profile",
    "runtime_profile_backend_fixture",
    "runtime_seeded_profile_backend_fixture",
]

#: The label of a world's operator profile when the suite names none.
_OPERATOR_LABEL = "operator"
#: The storage root an isolated world opens beneath its directory.
_STORAGE_ROOT_NAME = "cadrumo-storage"


class _RuntimeJoinedOnFirstCommand:
    """Join one registered profile's runtime when a command first needs it, until the scope ends."""

    def __init__(self, stack: ExitStack, storage_root: Path, profile_id: UUID, label: str) -> None:
        self._stack = stack
        self._storage_root = storage_root
        self._profile_id = profile_id
        self._label = label
        self._runtime: PortableHumanCliRuntime | None = None

    def invoke(self, args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
        """Run one command as the profile's operator; one that names its own credentials runs as given."""
        if chooses_own_credential_source(args):
            return invoke_unbound_cli(args, **kwargs)
        if self._runtime is None:
            # Until a command needs the operator, commands run exactly as given:
            # one that never reaches the runtime prints what it always printed.
            first = invoke_unbound_cli(args, **kwargs)
            if not refused_for_want_of_an_operator(first):
                return first
            self._runtime = self._stack.enter_context(
                portable_human_cli_runtime(
                    storage_root=self._storage_root, profile_id=self._profile_id, label=self._label
                )
            )
        return self._runtime.invoke(args, **kwargs)


@contextmanager
def operator_profile_bound_to_cli(
    *,
    storage_root: Path,
    label: str = _OPERATOR_LABEL,
    facts: Mapping[str, str] | None = None,
    complete: bool = True,
    prepare: Callable[[], None] | None = None,
) -> Iterator[UUID]:
    """Register one password-custodied profile and run every command as its operator.

    Registration leaves the profile's session live in this process for the
    test's own setup reads and writes; ``prepare`` runs inside it before any
    command does.
    """
    profile_id = UUID(register_cli_profile(label=label, facts=facts, complete=complete, log_in=False))
    try:
        if prepare is not None:
            prepare()
        with ExitStack() as stack:
            stack.enter_context(bind_profile_cli(_RuntimeJoinedOnFirstCommand(stack, storage_root, profile_id, label)))
            yield profile_id
    finally:
        # The registration's session belongs to this world; no later test inherits it.
        close_active_bucket_session()


@contextmanager
def runtime_cli_profile(
    *,
    tmp_path: Path,
    label: str = _OPERATOR_LABEL,
    facts: Mapping[str, str] | None = None,
) -> Iterator[TestRuntimeProfile]:
    """Isolate a CLI world around one password-custodied profile whose operator runs every command.

    The command-line counterpart of the storage package's runtime profile: the
    directories CLI work-unit commands read from settings are isolated beside
    the storage root, and the profile is registered with genuine password
    custody so its runtime admits the test's commands. Its session stays live
    in this process for the test's own setup reads and writes, which address
    the profile by the yielded ``bucket_id``.
    """
    overrides = storage_overrides(
        tmp_path,
        StorageCategory.RUNS,
        StorageCategory.DRAFTS,
        StorageCategory.TOKENS,
        StorageCategory.FINANCIAL_TRANSACTIONS,
        StorageCategory.INVOICES,
    )
    for location in overrides.values():
        location.mkdir(parents=True, exist_ok=True)
    with (
        _isolated_world(tmp_path, overrides) as storage_root,
        operator_profile_bound_to_cli(storage_root=storage_root, label=label, facts=facts) as profile_id,
    ):
        settings = load_settings()
        yield TestRuntimeProfile(
            storage_root=storage_root,
            bucket_id=str(profile_id),
            paths=bucket_paths(storage_root, str(profile_id)),
            settings=settings,
            runtime=inspect_storage_runtime(settings),
            repository=secure_object_repository_for_active_bucket(),
        )


def runtime_profile_backend_fixture(
    *,
    autouse: bool = True,
    name: str = "_isolated_backend",
    settings_overrides: Mapping[str, object] | Callable[[Path], Mapping[str, object]] | None = None,
    profile_overrides: Mapping[str, str] | None = None,
    display_name: str | None = None,
) -> Callable[..., Iterator[None]]:
    """Build a fixture isolating storage around one operator profile that commands reach through a runtime.

    The axes are those of the storage package's active-profile world: settings
    pinned before the storage root opens (a directory override is provisioned,
    because the command line validates and never creates it), extra profile
    facts, and the profile's label. The SQL engine is disposed on both sides
    so no connection crosses tests.
    """

    @pytest.fixture(name=name, autouse=autouse)
    def _runtime_profile_backend(tmp_path: Path) -> Iterator[None]:
        if settings_overrides is None:
            overrides: Mapping[str, object] = {}
        elif isinstance(settings_overrides, Mapping):
            overrides = dict(settings_overrides)
        else:
            overrides = settings_overrides(tmp_path)
        for field_name, value in overrides.items():
            if field_name.endswith("_dir") and isinstance(value, Path):
                value.mkdir(parents=True, exist_ok=True)
        dispose_engine()
        try:
            with (
                override_settings(**overrides) if overrides else nullcontext(),
                isolated_profile_storage_root(tmp_path=tmp_path) as storage_root,
                operator_profile_bound_to_cli(
                    storage_root=storage_root,
                    label=display_name or _OPERATOR_LABEL,
                    facts=profile_overrides,
                ),
            ):
                yield
        finally:
            dispose_engine()

    return _runtime_profile_backend


@contextmanager
def _isolated_world(root: Path, settings_overrides: Mapping[str, object] | None) -> Iterator[Path]:
    dispose_engine()
    try:
        with (
            override_settings(**settings_overrides) if settings_overrides else nullcontext(),
            isolated_profile_storage_root(tmp_path=root) as storage_root,
        ):
            yield storage_root
    finally:
        dispose_engine()


@contextmanager
def _signed_in_copy_bound_to_cli(storage_root: Path, label: str) -> Iterator[None]:
    """Unlock a copied world's profile with its password, as its operator would, and bind it."""
    passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    with bundled_indexed_authority().operation() as operation:
        login = authenticate_profile_for_invocation(
            name=label,
            passphrase_callback=lambda: passphrase,
            profile_decode_context=operation.profile_decode_context(),
        )
    try:
        with ExitStack() as stack:
            joiner = _RuntimeJoinedOnFirstCommand(stack, storage_root, UUID(login.bucket_id), label)
            stack.enter_context(bind_profile_cli(joiner))
            yield
    finally:
        close_active_bucket_session()


def _runtime_installation_state(directory: str, names: list[str]) -> set[str]:
    """Leave out the runtime coordination directory of a copied storage root."""
    coordination = storage_location(StorageCategory.RUNTIME_COORDINATION).relative_path().name
    return {coordination} if coordination in names and Path(directory).name == _STORAGE_ROOT_NAME else set()


def runtime_seeded_profile_backend_fixture(
    *,
    seed: Callable[[], None],
    label: str = _OPERATOR_LABEL,
    settings_overrides: Mapping[str, object] | None = None,
    profile_overrides: Mapping[str, str] | None = None,
    autouse: bool = True,
    name: str = "_isolated_backend",
    origin_name: str = "_isolated_backend_origin",
) -> tuple[Callable[..., Iterator[Path]], Callable[..., Iterator[None]]]:
    """Build the (origin, per-test) pair of a seed-once world whose commands reach a runtime.

    ``seed`` runs once per module as the operator of a password-custodied
    profile, so the commands it runs are admitted like any other. Each test
    receives a filesystem copy of the settled world, including its custody
    material, unlocks the copy's profile with its password and runs its
    commands as that profile's operator. As in the storage package's seed-once
    factory, a module binding two worlds states a distinct ``name`` and
    ``origin_name`` for each.
    """

    @pytest.fixture(name=origin_name, scope="module")
    def _seeded_origin(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
        root = tmp_path_factory.mktemp("seeded-origin")
        with (
            _isolated_world(root, settings_overrides) as storage_root,
            operator_profile_bound_to_cli(storage_root=storage_root, label=label, facts=profile_overrides),
        ):
            seed()
        yield root

    @pytest.fixture(name=name, autouse=autouse)
    def _copied_backend(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[None]:
        origin = request.getfixturevalue(origin_name)
        assert isinstance(origin, Path)
        clone = tmp_path / "seeded-world"
        # The runtime installation record names the origin root's physical
        # identity; a copy is another root, which installs its own on first use.
        shutil.copytree(origin, clone, ignore=_runtime_installation_state)
        with (
            _isolated_world(clone, settings_overrides) as storage_root,
            _signed_in_copy_bound_to_cli(storage_root, label),
        ):
            yield

    return _seeded_origin, _copied_backend


def live_session_operator(stack: ExitStack, bucket_id: str) -> ProfileCliInvoker | None:
    """Return the operator of a committed profile whose session is live, joined to ``stack`` on first command."""
    pointer = read_profile_bucket_by_id(bucket_id)
    if pointer is None:
        return None
    return _RuntimeJoinedOnFirstCommand(stack, effective_storage_root(), UUID(pointer.bucket_id), str(pointer.label))
