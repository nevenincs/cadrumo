"""Isolated storage with one password-custodied profile whose runtime admits the test's commands.

Commands that read or write a profile submit registered operations to the
runtime. A test world whose profile cannot sign in is refused as runtime
unavailable before the behaviour under test, so these worlds register the
profile with genuine password custody and bind it to :func:`invoke_cached_cli`.
The runtime is joined when the first command runs: a suite that serves its own
exact profile from a native worker binds that profile instead and never starts
this one, so two runtimes never contend for one runtime door in a test.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import ExitStack, contextmanager, nullcontext
from pathlib import Path
from typing import Unpack
from uuid import UUID

import pytest
from click.testing import Result

from ....adapters.persistence.profile.tests.profile_registration import register_cli_profile
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....core.config import override_settings
from .cli_runner import ClickInvokeKwargs, bind_profile_cli
from .portable_human_cli_runtime import PortableHumanCliRuntime, portable_human_cli_runtime

__all__ = ["operator_profile_bound_to_cli", "runtime_profile_backend_fixture"]

#: The label of a world's operator profile when the suite names none.
_OPERATOR_LABEL = "operator"


class _RuntimeJoinedOnFirstCommand:
    """Join one registered profile's runtime when its first command runs, until the scope ends."""

    def __init__(self, stack: ExitStack, storage_root: Path, profile_id: UUID, label: str) -> None:
        self._stack = stack
        self._storage_root = storage_root
        self._profile_id = profile_id
        self._label = label
        self._runtime: PortableHumanCliRuntime | None = None

    def invoke(self, args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
        """Run one command as the profile's operator."""
        if self._runtime is None:
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
    if prepare is not None:
        prepare()
    with ExitStack() as stack:
        stack.enter_context(bind_profile_cli(_RuntimeJoinedOnFirstCommand(stack, storage_root, profile_id, label)))
        yield profile_id


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
